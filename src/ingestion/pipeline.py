"""End-to-end ingestion pipeline: parse -> chunk -> embed -> store."""

from __future__ import annotations

import logging

from src.ingestion.chunking import naive_chunk, speaker_turn_chunk
from src.ingestion.embeddings import embed_chunks
from src.ingestion.parsers import parse_transcript
from src.ingestion.storage import get_supabase_client, store_chunks, store_meeting
from src.pipeline_config import ChunkingStrategy

logger = logging.getLogger(__name__)


def ingest_transcript(
    content: str,
    format: str,
    title: str,
    chunking_strategy: str | ChunkingStrategy = ChunkingStrategy.SPEAKER_TURN,
    extract: bool = False,
) -> str:
    """Full ingestion pipeline: parse -> chunk -> embed -> store (-> extract).

    Args:
        content: Raw transcript text.
        format: Transcript format (``"vtt"``, ``"json"``, ``"text"``).
        title: Human-readable meeting title.
        chunking_strategy: ``"naive"`` or ``"speaker_turn"`` (string or enum).
        extract: If True, run structured extraction after ingestion.

    Returns:
        The newly created meeting ID.
    """
    # Normalise to enum
    if isinstance(chunking_strategy, str):
        chunking_strategy = ChunkingStrategy(chunking_strategy)

    # 1. Parse
    segments = parse_transcript(content, format)

    # 2. Chunk
    if chunking_strategy is ChunkingStrategy.NAIVE:
        chunks = naive_chunk(segments)
    else:
        chunks = speaker_turn_chunk(segments)

    # 3. Embed
    chunks_with_embeddings = embed_chunks(chunks)

    # 4. Store
    client = get_supabase_client()
    num_speakers = len({s.speaker for s in segments if s.speaker})
    meeting_id = store_meeting(
        client,
        title,
        content,
        transcript_format=format,
        num_speakers=num_speakers or None,
    )
    store_chunks(client, meeting_id, chunks_with_embeddings)

    # 5. Optional extraction
    if extract:
        try:
            from src.extraction.extractor import extract_and_store

            items = extract_and_store(meeting_id, content)
            logger.info("Extracted %d items for meeting %s", len(items), meeting_id)
        except Exception:
            logger.exception("Extraction failed for meeting %s", meeting_id)

    return meeting_id
