"""Meeting endpoints: list, detail, and extraction views."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from postgrest import CountMethod

from src.api.auth import get_current_user_id
from src.api.models import MeetingDetail, MeetingSummary, SourceChunk
from src.ingestion.storage import get_supabase_client

router = APIRouter()


@router.get("/api/meetings", response_model=list[MeetingSummary])
async def list_meetings(
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> list[MeetingSummary]:
    """List meetings belonging to the authenticated user, newest first."""
    client = get_supabase_client()
    result = (
        client.table("meetings")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

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
async def get_meeting(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MeetingDetail:
    """Get full meeting details. Returns 404 if not found or not owned by caller."""
    client = get_supabase_client()
    result = client.table("meetings").select("*").eq("id", meeting_id).execute()

    # Supabase .data is typed as JSON (broad union); cast to concrete type. (#30)
    detail_rows = cast(list[dict[str, Any]], result.data)
    if not detail_rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    m = detail_rows[0]

    # Raise 404 (not 403) to avoid revealing whether the meeting exists. (#71)
    if m.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Meeting not found")

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


@router.delete("/api/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Delete a meeting owned by the authenticated user.

    Returns 404 if the meeting does not exist or does not belong to the caller.
    This prevents ownership-probing via DELETE. (#71)
    """
    import uuid as _uuid

    try:
        _uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found") from None

    client = get_supabase_client()

    # Verify ownership before deleting dependent rows. Raise 404 whether the
    # meeting is genuinely missing or belongs to a different user. (#71)
    check = (
        client.table("meetings")
        .select("id")
        .eq("id", meeting_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not cast(list[dict[str, Any]], check.data):
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    # Delete dependent rows first (foreign key safety)
    client.table("chunks").delete().eq("meeting_id", meeting_id).execute()
    client.table("extracted_items").delete().eq("meeting_id", meeting_id).execute()
    result = client.table("meetings").delete().eq("id", meeting_id).execute()
    data = cast(list[dict[str, Any]], result.data)
    if not data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found") from None


# Extraction is handled exclusively by POST /api/meetings/{meeting_id}/extract
# in src/api/routes/extraction.py (Issue #25: duplicate GET removed from here).
