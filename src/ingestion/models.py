"""Data models for the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    """Uniform representation of a transcript segment."""

    speaker: str | None
    text: str
    start_time: float | None = None
    end_time: float | None = None


@dataclass
class Chunk:
    """A chunk ready for embedding and storage."""

    content: str
    speaker: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    chunk_index: int = 0
    strategy: str = field(default="naive")
