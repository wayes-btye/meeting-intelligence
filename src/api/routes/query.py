"""Query endpoint: retrieve context and generate answers, with structured routing."""

from __future__ import annotations

from anthropic import APIStatusError
from fastapi import APIRouter, HTTPException

from src.api.models import QueryRequest, QueryResponse
from src.retrieval.generation import generate_answer
from src.retrieval.router import (
    QueryType,
    classify_query,
    format_structured_response,
    lookup_extracted_items,
)
from src.retrieval.search import search

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Answer a question using structured lookup or RAG over meeting transcripts.

    The query router classifies the question:
    - Structured queries (action items, decisions, topics) -> direct DB lookup
    - Open-ended queries -> RAG pipeline (embed, search, generate)
    """
    routed = classify_query(request.question)

    if routed.query_type is QueryType.STRUCTURED:
        items = lookup_extracted_items(
            meeting_id=request.meeting_id,
            item_type=routed.item_type,
        )
        answer = format_structured_response(items, routed.item_type)
        return QueryResponse(
            answer=answer,
            sources=[],
            model=None,
            usage=None,
        )

    # Open-ended: use existing RAG pipeline
    chunks = search(
        request.question,
        retrieval_strategy=request.strategy,
        meeting_id=request.meeting_id,
    )

    if not chunks:
        return QueryResponse(
            answer="No relevant meeting content found for your question.",
            sources=[],
        )

    # Generate answer with Claude
    try:
        result = generate_answer(request.question, chunks)
    except APIStatusError as exc:
        # Claude API overloaded (529) or other upstream error — return 503 so the
        # browser receives a proper JSON response with CORS headers intact.
        # Issue #30-adjacent: unhandled Anthropic errors bypass CORS middleware.
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc.message}") from exc

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        model=result.get("model"),
        usage=result.get("usage"),
    )
