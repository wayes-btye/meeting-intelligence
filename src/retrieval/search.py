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
) -> list[dict[str, Any]]:
    """Pure vector similarity search using match_chunks function."""
    embedding = get_query_embedding(query)
    client = get_supabase_client()
    result = client.rpc(
        "match_chunks",
        {
            "query_embedding": embedding,
            "match_count": match_count,
            "filter_meeting_id": meeting_id,
            "filter_strategy": strategy,
        },
    ).execute()
    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    chunks = cast(list[dict[str, Any]], result.data)
    return _enrich_with_meeting_titles(chunks)


def hybrid_search(
    query: str,
    match_count: int = 10,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    meeting_id: str | None = None,
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
    """
    # Fetch extra results when filtering so we still return enough after pruning
    fetch_count = match_count * 3 if meeting_id else match_count

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

    return _enrich_with_meeting_titles(data[:match_count])


def search(
    query: str,
    retrieval_strategy: str | RetrievalStrategy = RetrievalStrategy.HYBRID,
    match_count: int = 10,
    meeting_id: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the appropriate search strategy.

    Args:
        query: The user's question.
        retrieval_strategy: ``"semantic"`` or ``"hybrid"`` (string or enum).
        match_count: Maximum number of chunks to return.
        meeting_id: Optional meeting ID filter.

    Returns:
        List of matching chunk dicts.
    """
    if isinstance(retrieval_strategy, str):
        retrieval_strategy = RetrievalStrategy(retrieval_strategy)

    if retrieval_strategy is RetrievalStrategy.SEMANTIC:
        return semantic_search(query, match_count=match_count, meeting_id=meeting_id)
    return hybrid_search(query, match_count=match_count, meeting_id=meeting_id)
