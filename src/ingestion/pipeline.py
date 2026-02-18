"""End-to-end ingestion pipeline: parse -> chunk -> embed -> store."""

from __future__ import annotations

from src.ingestion.chunking import naive_chunk, speaker_turn_chunk
from src.ingestion.embeddings import embed_chunks
from src.ingestion.parsers import parse_transcript
from src.ingestion.storage import get_supabase_client, store_chunks, store_meeting


def ingest_transcript(
    content: str,
    format: str,
    title: str,
    chunking_strategy: str = "speaker_turn",
) -> str:
    """Full ingestion pipeline: parse -> chunk -> embed -> store.

    Args:
        content: Raw transcript text.
        format: Transcript format (``"vtt"``, ``"json"``, ``"text"``).
        title: Human-readable meeting title.
        chunking_strategy: ``"naive"`` or ``"speaker_turn"``.

    Returns:
        The newly created meeting ID.
    """
    # 1. Parse
    segments = parse_transcript(content, format)

    # 2. Chunk
    chunks = naive_chunk(segments) if chunking_strategy == "naive" else speaker_turn_chunk(segments)

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

    return meeting_id
