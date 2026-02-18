"""Supabase storage helpers for meetings and chunks."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from supabase import Client, create_client

if TYPE_CHECKING:
    from src.ingestion.models import Chunk


def get_supabase_client() -> Client:
    """Create and return a Supabase client from environment variables."""
    return create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_KEY", ""),
    )


def store_meeting(
    client: Client,
    title: str,
    raw_transcript: str,
    source_file: str | None = None,
    transcript_format: str | None = None,
    duration_seconds: int | None = None,
    num_speakers: int | None = None,
) -> str:
    """Store meeting metadata and return the generated meeting ID."""
    result = (
        client.table("meetings")
        .insert(
            {
                "title": title,
                "raw_transcript": raw_transcript,
                "source_file": source_file,
                "transcript_format": transcript_format,
                "duration_seconds": duration_seconds,
                "num_speakers": num_speakers,
            }
        )
        .execute()
    )
    return str(result.data[0]["id"])


def store_chunks(
    client: Client,
    meeting_id: str,
    chunks_with_embeddings: list[tuple[Chunk, list[float]]],
) -> None:
    """Store chunks with embeddings in Supabase (batched by 50)."""
    rows: list[dict[str, object]] = []
    for chunk, embedding in chunks_with_embeddings:
        rows.append(
            {
                "meeting_id": meeting_id,
                "content": chunk.content,
                "speaker": chunk.speaker,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "chunk_index": chunk.chunk_index,
                "strategy": chunk.strategy,
                "embedding": embedding,
            }
        )

    # Insert in batches of 50
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        client.table("chunks").insert(rows[i : i + batch_size]).execute()
