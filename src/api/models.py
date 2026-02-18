"""Pydantic request/response schemas for the Meeting Intelligence API."""

from __future__ import annotations

from pydantic import BaseModel

from src.pipeline_config import ChunkingStrategy, RetrievalStrategy


class QueryRequest(BaseModel):
    """Request body for the /api/query endpoint."""

    question: str
    meeting_id: str | None = None
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID


class SourceChunk(BaseModel):
    """A single retrieved transcript chunk with metadata."""

    content: str
    speaker: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    similarity: float | None = None
    meeting_id: str | None = None
    combined_score: float | None = None


class QueryResponse(BaseModel):
    """Response body for the /api/query endpoint."""

    answer: str
    sources: list[SourceChunk]
    model: str | None = None
    usage: dict | None = None


class MeetingSummary(BaseModel):
    """Summary representation of a meeting for list views."""

    id: str
    title: str
    source_file: str | None = None
    transcript_format: str | None = None
    num_speakers: int | None = None
    created_at: str | None = None
    chunk_count: int = 0


class MeetingDetail(BaseModel):
    """Full meeting detail including chunks and extracted items."""

    id: str
    title: str
    source_file: str | None = None
    transcript_format: str | None = None
    num_speakers: int | None = None
    created_at: str | None = None
    raw_transcript: str | None = None
    summary: str | None = None
    chunks: list[SourceChunk] = []
    extracted_items: list[dict] = []


class IngestResponse(BaseModel):
    """Response body for the /api/ingest endpoint."""

    meeting_id: str
    title: str
    num_chunks: int
    chunking_strategy: ChunkingStrategy


class ExtractedItemResponse(BaseModel):
    """A single extracted item in API responses."""

    item_type: str
    content: str
    assignee: str | None = None
    due_date: str | None = None
    speaker: str | None = None
    confidence: float = 1.0


class ExtractResponse(BaseModel):
    """Response body for the /api/meetings/{id}/extract endpoint."""

    meeting_id: str
    items_extracted: int
    action_items: list[ExtractedItemResponse] = []
    decisions: list[ExtractedItemResponse] = []
    topics: list[ExtractedItemResponse] = []
