"""Search implementations: semantic and hybrid retrieval."""

from __future__ import annotations

import os

from openai import OpenAI

from supabase import create_client

from src.pipeline_config import RetrievalStrategy


def get_supabase_client():
    """Create and return a Supabase client from environment variables."""
    return create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_KEY", ""),
    )


def get_query_embedding(query: str, model: str = "text-embedding-3-small") -> list[float]:
    """Generate an embedding vector for the given query string."""
    client = OpenAI()
    response = client.embeddings.create(input=[query], model=model)
    return response.data[0].embedding


def semantic_search(
    query: str,
    match_count: int = 10,
    meeting_id: str | None = None,
    strategy: str | None = None,
) -> list[dict]:
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
    return result.data


def hybrid_search(
    query: str,
    match_count: int = 10,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
) -> list[dict]:
    """Combined vector + full-text search."""
    embedding = get_query_embedding(query)
    client = get_supabase_client()
    result = client.rpc(
        "hybrid_search",
        {
            "query_embedding": embedding,
            "query_text": query,
            "match_count": match_count,
            "vector_weight": vector_weight,
            "text_weight": text_weight,
        },
    ).execute()
    return result.data


def search(
    query: str,
    retrieval_strategy: str | RetrievalStrategy = RetrievalStrategy.HYBRID,
    match_count: int = 10,
    meeting_id: str | None = None,
) -> list[dict]:
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
    return hybrid_search(query, match_count=match_count)
