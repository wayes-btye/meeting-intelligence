"""Search implementations: semantic and hybrid retrieval."""

from __future__ import annotations

from typing import Any, cast

from openai import OpenAI

from src.config import settings
from src.ingestion.storage import get_supabase_client
from src.pipeline_config import RetrievalStrategy


def _enrich_with_meeting_titles(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add meeting_title to each chunk by fetching meeting metadata."""
    if not chunks:
        return chunks
    meeting_ids = list({c["meeting_id"] for c in chunks if c.get("meeting_id")})
    client = get_supabase_client()
    result = client.table("meetings").select("id,title").in_("id", meeting_ids).execute()
    title_map = {r["id"]: r["title"] for r in cast(list[dict[str, Any]], result.data)}
    for chunk in chunks:
        chunk["meeting_title"] = title_map.get(chunk.get("meeting_id", ""))
    return chunks


def _get_user_meeting_ids(user_id: str) -> list[str]:
    """Return a list of meeting IDs belonging to ``user_id``."""
    client = get_supabase_client()
    result = client.table("meetings").select("id").eq("user_id", user_id).execute()
    return [r["id"] for r in cast(list[dict[str, Any]], result.data)]


def get_query_embedding(query: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate an embedding vector for the given query string."""
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(input=[query], model=model)
    return response.data[0].embedding


def semantic_search(
    query: str,
    match_count: int = 10,
    meeting_id: str | None = None,
    strategy: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Pure vector similarity search using match_chunks function.

    Args:
        query: The search query.
        match_count: Maximum number of results to return.
        meeting_id: Optional meeting ID to filter results.
        strategy: Optional chunking strategy filter.
        user_id: If provided, restricts results to this user's meetings. (#71)
    """
    embedding = get_query_embedding(query)
    client = get_supabase_client()

    # Resolve the allowed meeting IDs for this user before calling the RPC.
    # Fetch extra results when filtering so we still return enough after pruning.
    allowed_ids: list[str] | None = None
    if user_id:
        allowed_ids = _get_user_meeting_ids(user_id)
        if not allowed_ids:
            return []

    fetch_count = match_count * 3 if (user_id and not meeting_id) else match_count

    result = client.rpc(
        "match_chunks",
        {
            "query_embedding": embedding,
            "match_count": fetch_count,
            "filter_meeting_id": meeting_id,
            "filter_strategy": strategy,
        },
    ).execute()
    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    chunks = cast(list[dict[str, Any]], result.data)

    # Python-side user_id filter (same pattern as hybrid_search meeting_id filter)
    if allowed_ids is not None:
        chunks = [c for c in chunks if c.get("meeting_id") in allowed_ids]

    return _enrich_with_meeting_titles(chunks[:match_count])


def hybrid_search(
    query: str,
    match_count: int = 10,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    meeting_id: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Combined vector + full-text search.

    Args:
        query: The search query text.
        match_count: Maximum number of results to return.
        vector_weight: Weight for semantic similarity score.
        text_weight: Weight for keyword match score.
        meeting_id: Optional meeting ID to filter results. Applied as a
            Python-side post-filter since the Supabase RPC function may
            not support this parameter.
        user_id: If provided, restricts results to this user's meetings. (#71)
    """
    # Resolve the allowed meeting IDs for this user before calling the RPC.
    allowed_ids: list[str] | None = None
    if user_id:
        allowed_ids = _get_user_meeting_ids(user_id)
        if not allowed_ids:
            return []

    # Fetch extra results when filtering so we still return enough after pruning
    needs_filter = bool(meeting_id or allowed_ids)
    fetch_count = match_count * 3 if needs_filter else match_count

    embedding = get_query_embedding(query)
    client = get_supabase_client()
    result = client.rpc(
        "hybrid_search",
        {
            "query_embedding": embedding,
            "query_text": query,
            "match_count": fetch_count,
            "vector_weight": vector_weight,
            "text_weight": text_weight,
        },
    ).execute()

    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    data: list[dict[str, Any]] = cast(list[dict[str, Any]], result.data)

    # Python-side meeting_id filter (the SQL function may not support it)
    if meeting_id:
        data = [r for r in data if r.get("meeting_id") == meeting_id]

    # Python-side user_id filter: keep only chunks from this user's meetings
    if allowed_ids is not None:
        data = [r for r in data if r.get("meeting_id") in allowed_ids]

    return _enrich_with_meeting_titles(data[:match_count])


def search(
    query: str,
    retrieval_strategy: str | RetrievalStrategy = RetrievalStrategy.HYBRID,
    match_count: int = 10,
    meeting_id: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the appropriate search strategy.

    Args:
        query: The user's question.
        retrieval_strategy: ``"semantic"`` or ``"hybrid"`` (string or enum).
        match_count: Maximum number of chunks to return.
        meeting_id: Optional meeting ID filter.
        user_id: If provided, restricts results to this user's meetings. (#71)

    Returns:
        List of matching chunk dicts.
    """
    if isinstance(retrieval_strategy, str):
        retrieval_strategy = RetrievalStrategy(retrieval_strategy)

    if retrieval_strategy is RetrievalStrategy.SEMANTIC:
        return semantic_search(
            query, match_count=match_count, meeting_id=meeting_id, user_id=user_id
        )
    return hybrid_search(query, match_count=match_count, meeting_id=meeting_id, user_id=user_id)
