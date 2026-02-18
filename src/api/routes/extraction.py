"""Extraction endpoint: trigger structured extraction for a meeting."""

from __future__ import annotations

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

    if not result.data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    m = result.data[0]
    transcript = m.get("raw_transcript")
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Meeting has no transcript to extract from",
        )

    from src.extraction.extractor import extract_and_store

    items = extract_and_store(meeting_id, transcript)

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
