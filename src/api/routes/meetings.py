"""Meeting endpoints: list, detail, and extraction views."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException
from postgrest import CountMethod

from src.api.models import MeetingDetail, MeetingSummary, SourceChunk
from src.ingestion.storage import get_supabase_client

router = APIRouter()


@router.get("/api/meetings", response_model=list[MeetingSummary])
async def list_meetings() -> list[MeetingSummary]:
    """List all meetings ordered by creation date (newest first)."""
    client = get_supabase_client()
    result = client.table("meetings").select("*").order("created_at", desc=True).execute()

    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    rows = cast(list[dict[str, Any]], result.data)
    meetings: list[MeetingSummary] = []
    for m in rows:
        # Get chunk count
        chunks = (
            client.table("chunks")
            .select("id", count=CountMethod.exact)
            .eq("meeting_id", m["id"])
            .execute()
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

    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    detail_rows = cast(list[dict[str, Any]], result.data)
    if not detail_rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    m = detail_rows[0]

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
            for c in cast(list[dict[str, Any]], chunks_result.data)
        ],
        extracted_items=cast(list[dict[str, Any]], items_result.data),
    )


# Extraction is handled exclusively by POST /api/meetings/{meeting_id}/extract
# in src/api/routes/extraction.py (Issue #25: duplicate GET removed from here).
