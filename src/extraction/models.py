"""Data models for structured extraction results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExtractedItem:
    """A single extracted item (action item, decision, or topic)."""

    item_type: str  # "action_item", "decision", "topic"
    content: str
    assignee: str | None = None
    due_date: str | None = None
    speaker: str | None = None
    confidence: float = 1.0
