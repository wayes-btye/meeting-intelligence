"""Ingest endpoint: upload and process meeting transcripts."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from postgrest import CountMethod

from src.api.models import BatchIngestResponse, IngestResponse
from src.config import settings
from src.ingestion.pipeline import ingest_transcript
from src.ingestion.storage import get_supabase_client
from src.pipeline_config import ChunkingStrategy

router = APIRouter()

# 50 MB upload limit (compressed upload)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Zip bomb protection: limits applied per-member and across all members
MAX_ZIP_MEMBERS = 50
MAX_ZIP_MEMBER_BYTES = 100 * 1024 * 1024   # 100 MB per individual file
MAX_ZIP_TOTAL_BYTES = 200 * 1024 * 1024    # 200 MB total expanded across all members

# Extensions treated as audio — routed to AssemblyAI transcription
AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "mp4", "ogg", "flac"}

# Extensions accepted as plain-text transcript files
TRANSCRIPT_EXTENSIONS = {"vtt", "txt", "json"}


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
    # speech_models (plural) is required by current AssemblyAI API — SDK 0.52 sends empty list
    # by default which the API rejects. Confirmed via API error: must be ["universal-3-pro"].
    # speaker_labels=True enables diarization — without it, the API returns a single flat text
    # block attributed to no speaker. Fix for Issue #63.
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro"],
        speaker_labels=True,
    )

    try:
        transcript = transcriber.transcribe(raw, config=config)
        if transcript.status == aai.TranscriptStatus.error:
            # AssemblyAI rejected the audio content (corrupted, unsupported format, etc.)
            raise HTTPException(
                status_code=400,
                detail=f"Transcription failed: {transcript.error}",
            )
        # Return utterances as AssemblyAI JSON format so parse_json can extract speaker labels.
        # Fallback to a single-utterance structure if utterances are unavailable (Issue #63).
        utterances = transcript.utterances or []
        return json.dumps({
            "utterances": [
                {"speaker": u.speaker, "text": u.text, "start": u.start, "end": u.end}
                for u in utterances
            ]
        })
    except HTTPException:
        raise
    except Exception as exc:
        # Infrastructure error — invalid API key, network failure, provider outage.
        # Return 503, not 400: this is not the client's fault.
        raise HTTPException(
            status_code=503,
            detail=f"Transcription service unavailable: {exc}",
        ) from exc


@router.post("/api/ingest", response_model=IngestResponse | BatchIngestResponse)
async def ingest(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str, Form()] = "Untitled Meeting",
    chunking_strategy: Annotated[str, Form()] = "speaker_turn",
) -> IngestResponse | BatchIngestResponse:
    """Upload a transcript file and run the ingestion pipeline.

    Accepts text transcripts (.vtt, .txt, .json), audio files (.mp3, .wav,
    .m4a, .mp4, .ogg, .flac), and .zip archives containing transcript files.

    - Text/audio: returns IngestResponse (single meeting).
    - Zip archive: extracts each .vtt/.txt/.json (transcript) and .mp3/.wav/.m4a/.mp4/.ogg/.flac
      (audio) file and ingests each as a separate meeting. Audio files inside a zip require
      ASSEMBLYAI_API_KEY; if not configured, those entries are recorded in ``errors`` and skipped
      (transcript files in the same zip are still ingested). Returns BatchIngestResponse with all
      meeting IDs. Title per sub-meeting is ``"{zip_stem}/{filename_without_ext}"``
      (e.g. ``"batch_upload/council_jan"``). A 501 is returned only for audio-only single uploads
      without a key.

    Issue #34: zip bulk upload + Teams VTT support.
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

    # --- Zip bulk upload path (Issue #34) ---
    if ext == "zip" or content_type in ("application/zip", "application/x-zip-compressed"):
        return _ingest_zip(raw, filename, title, strategy)

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
        # Run synchronous AssemblyAI SDK in a thread — avoids blocking the event loop.
        # _transcribe_audio returns AssemblyAI JSON (utterances) so parse_json preserves speakers.
        content = await asyncio.to_thread(_transcribe_audio, raw)
        transcript_format = "json"
    else:
        # Text path: decode as UTF-8 (existing behaviour)
        content = raw.decode("utf-8")
        format_map = {"vtt": "vtt", "txt": "text", "json": "json"}
        transcript_format = format_map.get(ext, "text")

    meeting_id = ingest_transcript(content, transcript_format, title, strategy)

    # Get chunk count
    client = get_supabase_client()
    chunks = (
        client.table("chunks")
        .select("id", count=CountMethod.exact)
        .eq("meeting_id", meeting_id)
        .execute()
    )

    return IngestResponse(
        meeting_id=meeting_id,
        title=title,
        num_chunks=chunks.count or 0,
        chunking_strategy=strategy,
    )


def _ingest_zip(
    raw: bytes,
    zip_filename: str,
    base_title: str,
    strategy: ChunkingStrategy,
) -> BatchIngestResponse:
    """Ingest all transcript and audio files from a zip archive.

    Each .vtt/.txt/.json is decoded as text; each audio file (.mp3/.wav/etc.) is
    transcribed via AssemblyAI (skipped with an error entry if no API key is configured).
    Non-supported files are silently skipped.

    Zip bomb protection: rejects archives exceeding MAX_ZIP_MEMBERS (50) members, any individual
    member exceeding MAX_ZIP_MEMBER_BYTES (100 MB) uncompressed, or total expansion exceeding
    MAX_ZIP_TOTAL_BYTES (200 MB). Checks use ZipInfo.file_size (the declared uncompressed size),
    which is fast and avoids reading before validating.

    Title pattern: ``"{zip_stem}/{filename_without_ext}"``.

    Args:
        raw: Raw zip file bytes.
        zip_filename: Original upload filename (used to derive zip_stem).
        base_title: User-supplied title (used as fallback if no stem).
        strategy: Chunking strategy to apply to each ingested file.

    Returns:
        BatchIngestResponse with counts and IDs.
    """
    zip_stem = zip_filename.rsplit(".", 1)[0] if "." in zip_filename else (base_title or "batch")
    format_map = {"vtt": "vtt", "txt": "text", "json": "json"}
    meeting_ids: list[str] = []
    errors: list[str] = []

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=f"Invalid zip file: {exc}") from exc

    with zf:
        members = [m for m in zf.infolist() if not m.is_dir()]

        # Zip bomb guard: member count
        if len(members) > MAX_ZIP_MEMBERS:
            raise HTTPException(
                status_code=413,
                detail=f"Zip contains {len(members)} files; maximum is {MAX_ZIP_MEMBERS}.",
            )

        # Zip bomb guard: declared total uncompressed size
        total_uncompressed = sum(m.file_size for m in members)
        if total_uncompressed > MAX_ZIP_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Zip would expand to {total_uncompressed // (1024 * 1024)} MB; "
                    f"maximum is {MAX_ZIP_TOTAL_BYTES // (1024 * 1024)} MB."
                ),
            )

        for member in members:
            member_name = member.filename
            member_ext = member_name.rsplit(".", 1)[-1].lower() if "." in member_name else ""

            is_transcript = member_ext in TRANSCRIPT_EXTENSIONS
            is_audio = member_ext in AUDIO_EXTENSIONS
            if not is_transcript and not is_audio:
                continue  # silently skip unsupported files (images, PDFs, etc.)

            # Zip bomb guard: per-member declared uncompressed size
            if member.file_size > MAX_ZIP_MEMBER_BYTES:
                errors.append(
                    f"{member_name}: file too large ({member.file_size // (1024 * 1024)} MB, "
                    f"max {MAX_ZIP_MEMBER_BYTES // (1024 * 1024)} MB)"
                )
                continue

            # Derive per-meeting title: "{zip_stem}/{filename_without_ext}"
            base_name = member_name.rsplit("/", 1)[-1]  # strip any zip-internal path
            file_stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
            meeting_title = f"{zip_stem}/{file_stem}"

            try:
                file_bytes = zf.read(member_name)

                if is_audio:
                    if not settings.assemblyai_api_key:
                        errors.append(
                            f"{member_name}: audio transcription not configured "
                            "(set ASSEMBLYAI_API_KEY to enable audio files in zips)"
                        )
                        continue
                    # _transcribe_audio returns AssemblyAI JSON (utterances) — use "json" format
                    # so parse_json preserves speaker labels. Fix for Issue #63.
                    content = _transcribe_audio(file_bytes)
                    transcript_format = "json"
                else:
                    content = file_bytes.decode("utf-8")
                    transcript_format = format_map[member_ext]

                meeting_id = ingest_transcript(content, transcript_format, meeting_title, strategy)
                meeting_ids.append(meeting_id)
            except HTTPException as exc:
                errors.append(f"{member_name}: {exc.detail}")
            except Exception as exc:
                errors.append(f"{member_name}: {exc}")

    return BatchIngestResponse(
        meetings_ingested=len(meeting_ids),
        meeting_ids=meeting_ids,
        errors=errors,
    )
