"""Pydantic request/response schemas for the Meeting Intelligence API."""

from __future__ import annotations

from typing import Any

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
    meeting_title: str | None = None


class QueryResponse(BaseModel):
    """Response body for the /api/query endpoint."""

    answer: str
    sources: list[SourceChunk]
    model: str | None = None
    usage: dict[str, Any] | None = None


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
    extracted_items: list[dict[str, Any]] = []


class IngestResponse(BaseModel):
    """Response body for the /api/ingest endpoint."""

    meeting_id: str
    title: str
    num_chunks: int
    chunking_strategy: ChunkingStrategy


class BatchIngestResponse(BaseModel):
    """Response body for the /api/ingest endpoint when a .zip file is uploaded.

    Each .vtt/.txt/.json inside the zip is ingested as a separate meeting.
    Issue #34 — zip bulk upload.
    """

    meetings_ingested: int
    meeting_ids: list[str]
    errors: list[str]


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


class ImageSummaryResponse(BaseModel):
    """Response body for the /api/meetings/{id}/image-summary endpoint."""

    meeting_id: str
    image_data: str  # base64-encoded image
    mime_type: str = "image/png"
