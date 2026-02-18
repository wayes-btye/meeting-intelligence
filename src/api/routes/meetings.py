"""Meeting endpoints: list, detail, and extraction views."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.models import ExtractResponse, MeetingDetail, MeetingSummary, SourceChunk
from src.ingestion.storage import get_supabase_client

router = APIRouter()


@router.get("/api/meetings", response_model=list[MeetingSummary])
async def list_meetings() -> list[MeetingSummary]:
    """List all meetings ordered by creation date (newest first)."""
    client = get_supabase_client()
    result = client.table("meetings").select("*").order("created_at", desc=True).execute()

    meetings: list[MeetingSummary] = []
    for m in result.data:
        # Get chunk count
        chunks = (
            client.table("chunks").select("id", count="exact").eq("meeting_id", m["id"]).execute()
        )
        meetings.append(
            MeetingSummary(
                id=m["id"],
                title=m["title"],
                source_file=m.get("source_file"),
                transcript_format=m.get("transcript_format"),
                num_speakers=m.get("num_speakers"),
                created_at=m.get("created_at"),
                chunk_count=chunks.count or 0,
            )
        )
    return meetings


@router.get("/api/meetings/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(meeting_id: str) -> MeetingDetail:
    """Get full meeting details including chunks and extracted items."""
    client = get_supabase_client()
    result = client.table("meetings").select("*").eq("id", meeting_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    m = result.data[0]

    # Get chunks
    chunks_result = (
        client.table("chunks")
        .select("*")
        .eq("meeting_id", meeting_id)
        .order("chunk_index")
        .execute()
    )

    # Get extracted items
    items_result = (
        client.table("extracted_items").select("*").eq("meeting_id", meeting_id).execute()
    )

    return MeetingDetail(
        id=m["id"],
        title=m["title"],
        source_file=m.get("source_file"),
        transcript_format=m.get("transcript_format"),
        num_speakers=m.get("num_speakers"),
        created_at=m.get("created_at"),
        raw_transcript=m.get("raw_transcript"),
        summary=m.get("summary"),
        chunks=[
            SourceChunk(
                content=c["content"],
                speaker=c.get("speaker"),
                start_time=c.get("start_time"),
                end_time=c.get("end_time"),
            )
            for c in chunks_result.data
        ],
        extracted_items=items_result.data,
    )


@router.get("/api/meetings/{meeting_id}/extract", response_model=ExtractResponse)
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
        raise HTTPException(status_code=400, detail="Meeting has no transcript to extract from")

    from src.extraction.extractor import extract_and_store

    items = extract_and_store(meeting_id, transcript)

    return ExtractResponse(
        meeting_id=meeting_id,
        items_extracted=len(items),
        action_items=[i for i in items if i.item_type == "action_item"],
        decisions=[i for i in items if i.item_type == "decision"],
        topics=[i for i in items if i.item_type == "topic"],
    )
