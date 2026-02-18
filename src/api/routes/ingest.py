"""Ingest endpoint: upload and process meeting transcripts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from src.api.models import IngestResponse
from src.ingestion.pipeline import ingest_transcript
from src.ingestion.storage import get_supabase_client

router = APIRouter()


@router.post("/api/ingest", response_model=IngestResponse)
async def ingest(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str, Form()] = "Untitled Meeting",
    chunking_strategy: Annotated[str, Form()] = "speaker_turn",
) -> IngestResponse:
    """Upload a transcript file and run the ingestion pipeline."""
    content = (await file.read()).decode("utf-8")

    # Determine format from file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "txt"
    format_map = {"vtt": "vtt", "txt": "text", "json": "json"}
    transcript_format = format_map.get(ext, "text")

    meeting_id = ingest_transcript(content, transcript_format, title, chunking_strategy)

    # Get chunk count
    client = get_supabase_client()
    chunks = (
        client.table("chunks").select("id", count="exact").eq("meeting_id", meeting_id).execute()
    )

    return IngestResponse(
        meeting_id=meeting_id,
        title=title,
        num_chunks=chunks.count or 0,
        chunking_strategy=chunking_strategy,
    )
