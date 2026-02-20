"""Ingest endpoint: upload and process meeting transcripts."""

from __future__ import annotations

import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.models import IngestResponse
from src.config import settings
from src.ingestion.pipeline import ingest_transcript
from src.ingestion.storage import get_supabase_client
from src.pipeline_config import ChunkingStrategy

router = APIRouter()

# 50 MB upload limit
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Extensions treated as audio — routed to AssemblyAI transcription
AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "mp4", "ogg", "flac"}


def _transcribe_audio(raw: bytes, ext: str) -> str:
    """Transcribe audio bytes via AssemblyAI SDK.

    Writes to a temp file (SDK requires a path or URL), polls until complete,
    and returns the transcript text.

    Raises HTTPException(400) on transcription failure.
    """
    import assemblyai as aai  # type: ignore[import-untyped]  # no stubs; import inside function — only needed for audio path

    aai.settings.api_key = settings.assemblyai_api_key
    transcriber = aai.Transcriber()

    # AssemblyAI SDK needs a file path — write bytes to a temp file
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        transcript = transcriber.transcribe(tmp_path)
        if transcript.status == aai.TranscriptStatus.error:
            raise HTTPException(
                status_code=400,
                detail=f"Transcription failed: {transcript.error}",
            )
        return transcript.text or ""
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Transcription failed: {exc}",
        ) from exc
    finally:
        os.unlink(tmp_path)


@router.post("/api/ingest", response_model=IngestResponse)
async def ingest(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str, Form()] = "Untitled Meeting",
    chunking_strategy: Annotated[str, Form()] = "speaker_turn",
) -> IngestResponse:
    """Upload a transcript file and run the ingestion pipeline.

    Accepts text transcripts (.vtt, .txt, .json) and audio files (.mp3, .wav,
    .m4a, .mp4, .ogg, .flac).  Audio files are transcribed via AssemblyAI when
    ASSEMBLYAI_API_KEY is configured; otherwise a 501 is returned.
    """
    # Enforce file size limit
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    # Validate chunking strategy enum early
    strategy = ChunkingStrategy(chunking_strategy)

    # Detect extension before attempting any decode — audio is binary
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "txt"

    if ext in AUDIO_EXTENSIONS:
        # Audio path: transcribe with AssemblyAI or return 501 if not configured
        if not settings.assemblyai_api_key:
            raise HTTPException(
                status_code=501,
                detail=(
                    "Audio transcription is not configured. "
                    "Please upload a text transcript (.vtt, .txt, .json)."
                ),
            )
        # NOTE: _transcribe_audio is synchronous (AssemblyAI SDK polling).
        # This blocks the event loop on the ingest call — acceptable for current
        # single-user usage. A proper fix would use asyncio.to_thread().
        content = _transcribe_audio(raw, ext)
        transcript_format = "text"
    else:
        # Text path: decode as UTF-8 (existing behaviour)
        content = raw.decode("utf-8")
        format_map = {"vtt": "vtt", "txt": "text", "json": "json"}
        transcript_format = format_map.get(ext, "text")

    meeting_id = ingest_transcript(content, transcript_format, title, strategy)

    # Get chunk count
    client = get_supabase_client()
    chunks = (
        client.table("chunks").select("id", count="exact").eq("meeting_id", meeting_id).execute()
    )

    return IngestResponse(
        meeting_id=meeting_id,
        title=title,
        num_chunks=chunks.count or 0,
        chunking_strategy=strategy,
    )
