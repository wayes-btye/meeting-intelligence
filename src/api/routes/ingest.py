"""Ingest endpoint: upload and process meeting transcripts."""

from __future__ import annotations

import asyncio
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


def _transcribe_audio(raw: bytes) -> str:
    """Transcribe audio bytes via AssemblyAI SDK.

    The SDK accepts bytes directly — no temp file needed.

    Raises:
        HTTPException(400): Bad audio content (transcript error from AssemblyAI).
        HTTPException(503): Infrastructure error (bad API key, network, provider outage).
    """
    import assemblyai as aai  # type: ignore[import-untyped]  # no stubs; import inside function

    aai.settings.api_key = settings.assemblyai_api_key
    transcriber = aai.Transcriber()

    try:
        transcript = transcriber.transcribe(raw)
        if transcript.status == aai.TranscriptStatus.error:
            # AssemblyAI rejected the audio content (corrupted, unsupported format, etc.)
            raise HTTPException(
                status_code=400,
                detail=f"Transcription failed: {transcript.error}",
            )
        return transcript.text or ""
    except HTTPException:
        raise
    except Exception as exc:
        # Infrastructure error — invalid API key, network failure, provider outage.
        # Return 503, not 400: this is not the client's fault.
        raise HTTPException(
            status_code=503,
            detail=f"Transcription service unavailable: {exc}",
        ) from exc


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

    # Detect extension before attempting any decode — audio is binary.
    # Fall back to Content-Type for extensionless filenames (e.g. "recording" uploaded
    # as audio/mpeg) — guards against the UTF-8 decode crash on binary-but-unnamed files.
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = (file.content_type or "").lower()

    if ext in AUDIO_EXTENSIONS or content_type.startswith("audio/"):
        # Audio path: transcribe with AssemblyAI or return 501 if not configured
        if not settings.assemblyai_api_key:
            raise HTTPException(
                status_code=501,
                detail=(
                    "Audio transcription is not configured. "
                    "Please upload a text transcript (.vtt, .txt, .json)."
                ),
            )
        # Run synchronous AssemblyAI SDK in a thread — avoids blocking the event loop
        content = await asyncio.to_thread(_transcribe_audio, raw)
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
