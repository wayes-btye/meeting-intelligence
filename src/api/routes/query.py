"""Query endpoint: retrieve context and generate answers."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.models import QueryRequest, QueryResponse
from src.retrieval.generation import generate_answer
from src.retrieval.search import hybrid_search, semantic_search

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Answer a question using RAG over meeting transcripts."""
    # Retrieve relevant chunks
    if request.strategy == "semantic":
        chunks = semantic_search(
            request.question,
            meeting_id=request.meeting_id,
        )
    else:
        chunks = hybrid_search(request.question)

    if not chunks:
        return QueryResponse(
            answer="No relevant meeting content found for your question.",
            sources=[],
        )

    # Generate answer with Claude
    result = generate_answer(request.question, chunks)

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        model=result.get("model"),
        usage=result.get("usage"),
    )
