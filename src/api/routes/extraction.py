"""Extraction endpoint: trigger structured extraction for a meeting."""

from __future__ import annotations

from typing import Any, cast

from anthropic import APIStatusError
from fastapi import APIRouter, HTTPException

from src.api.models import ExtractedItemResponse, ExtractResponse
from src.ingestion.storage import get_supabase_client

router = APIRouter()


@router.post("/api/meetings/{meeting_id}/extract", response_model=ExtractResponse)
async def extract_meeting(meeting_id: str) -> ExtractResponse:
    """Trigger structured extraction for a meeting.

    Extracts action items, decisions, and key topics from the meeting
    transcript using Claude and stores the results in the extracted_items table.
    """
    client = get_supabase_client()
    result = client.table("meetings").select("*").eq("id", meeting_id).execute()

    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    rows = cast(list[dict[str, Any]], result.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    m = rows[0]
    transcript = m.get("raw_transcript")
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Meeting has no transcript to extract from",
        )

    from src.extraction.extractor import extract_and_store

    try:
        items = extract_and_store(meeting_id, str(transcript))
    except APIStatusError as exc:
        # Claude API overloaded (529) or other upstream error — return 503 so the
        # browser receives a proper JSON response with CORS headers intact.
        # Issue #30-adjacent: unhandled Anthropic errors bypass CORS middleware.
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc.message}") from exc

    return ExtractResponse(
        meeting_id=meeting_id,
        items_extracted=len(items),
        action_items=[
            ExtractedItemResponse(
                item_type=i.item_type,
                content=i.content,
                assignee=i.assignee,
                due_date=i.due_date,
                speaker=i.speaker,
                confidence=i.confidence,
            )
            for i in items
            if i.item_type == "action_item"
        ],
        decisions=[
            ExtractedItemResponse(
                item_type=i.item_type,
                content=i.content,
                assignee=i.assignee,
                due_date=i.due_date,
                speaker=i.speaker,
                confidence=i.confidence,
            )
            for i in items
            if i.item_type == "decision"
        ],
        topics=[
            ExtractedItemResponse(
                item_type=i.item_type,
                content=i.content,
                assignee=i.assignee,
                due_date=i.due_date,
                speaker=i.speaker,
                confidence=i.confidence,
            )
            for i in items
            if i.item_type == "topic"
        ],
    )
