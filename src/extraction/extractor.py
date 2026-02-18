"""Claude-powered structured extraction of action items, decisions, and topics."""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from src.config import settings
from src.extraction.models import ExtractedItem
from src.ingestion.storage import get_supabase_client

# Tool definition for Claude structured output
EXTRACTION_TOOL: dict[str, Any] = {
    "name": "store_extracted_items",
    "description": (
        "Store structured items extracted from a meeting transcript. "
        "Call this once with all extracted action items, decisions, and topics."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_items": {
                "type": "array",
                "description": "Action items — tasks someone needs to do.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Description of the action item.",
                        },
                        "assignee": {
                            "type": "string",
                            "description": "Person assigned (null if unassigned).",
                        },
                        "due_date": {
                            "type": "string",
                            "description": "Deadline if mentioned (free-form text, e.g. 'next Friday').",
                        },
                        "speaker": {
                            "type": "string",
                            "description": "Who mentioned or assigned this item.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1.",
                        },
                    },
                    "required": ["content", "confidence"],
                },
            },
            "decisions": {
                "type": "array",
                "description": "Decisions made during the meeting.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The decision that was made.",
                        },
                        "speaker": {
                            "type": "string",
                            "description": "Who announced or confirmed the decision.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1.",
                        },
                    },
                    "required": ["content", "confidence"],
                },
            },
            "topics": {
                "type": "array",
                "description": "Key topics or themes discussed.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Brief description of the topic.",
                        },
                        "speaker": {
                            "type": "string",
                            "description": "Primary speaker for this topic (if identifiable).",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1.",
                        },
                    },
                    "required": ["content", "confidence"],
                },
            },
        },
        "required": ["action_items", "decisions", "topics"],
    },
}

SYSTEM_PROMPT = (
    "You are a meeting intelligence assistant. Extract structured information "
    "from the meeting transcript provided.\n\n"
    "Extract:\n"
    "1. **Action items** — tasks that someone needs to complete. Include the "
    "assignee and deadline when mentioned.\n"
    "2. **Decisions** — conclusions or agreements reached during the meeting.\n"
    "3. **Key topics** — main subjects or themes discussed.\n\n"
    "Use the store_extracted_items tool to return your results. "
    "Be precise and only extract items clearly supported by the transcript. "
    "Assign a confidence score (0-1) to each item."
)


def extract_from_transcript(transcript: str) -> list[ExtractedItem]:
    """Extract action items, decisions, and topics from a transcript using Claude.

    Args:
        transcript: The raw meeting transcript text.

    Returns:
        A list of ExtractedItem instances.
    """
    client = Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "store_extracted_items"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract action items, decisions, and key topics from this "
                    f"meeting transcript:\n\n{transcript}"
                ),
            }
        ],
    )

    # Parse tool_use response
    return _parse_tool_response(response)


def _parse_tool_response(response: Any) -> list[ExtractedItem]:
    """Parse the Claude tool_use response into ExtractedItem list."""
    items: list[ExtractedItem] = []

    for block in response.content:
        if block.type != "tool_use":
            continue
        if block.name != "store_extracted_items":
            continue

        data = block.input
        if isinstance(data, str):
            data = json.loads(data)

        for action in data.get("action_items", []):
            items.append(
                ExtractedItem(
                    item_type="action_item",
                    content=action["content"],
                    assignee=action.get("assignee"),
                    due_date=action.get("due_date"),
                    speaker=action.get("speaker"),
                    confidence=action.get("confidence", 1.0),
                )
            )

        for decision in data.get("decisions", []):
            items.append(
                ExtractedItem(
                    item_type="decision",
                    content=decision["content"],
                    assignee=None,
                    due_date=None,
                    speaker=decision.get("speaker"),
                    confidence=decision.get("confidence", 1.0),
                )
            )

        for topic in data.get("topics", []):
            items.append(
                ExtractedItem(
                    item_type="topic",
                    content=topic["content"],
                    assignee=None,
                    due_date=None,
                    speaker=topic.get("speaker"),
                    confidence=topic.get("confidence", 1.0),
                )
            )

    return items


def store_extracted_items(meeting_id: str, items: list[ExtractedItem]) -> int:
    """Store extracted items in the Supabase extracted_items table.

    Args:
        meeting_id: The meeting UUID.
        items: List of extracted items to store.

    Returns:
        Number of items stored.
    """
    if not items:
        return 0

    client = get_supabase_client()

    rows = [
        {
            "meeting_id": meeting_id,
            "item_type": item.item_type,
            "content": item.content,
            "assignee": item.assignee,
            "due_date": item.due_date,
            "speaker": item.speaker,
            "confidence": item.confidence,
        }
        for item in items
    ]

    # Insert in batches of 50
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        client.table("extracted_items").insert(rows[i : i + batch_size]).execute()

    return len(rows)


def extract_and_store(meeting_id: str, transcript: str) -> list[ExtractedItem]:
    """Extract structured items from a transcript and store them.

    This is the main entry point: extracts via Claude, stores in Supabase,
    and returns the extracted items.

    Args:
        meeting_id: The meeting UUID.
        transcript: The raw meeting transcript text.

    Returns:
        The list of extracted items.
    """
    items = extract_from_transcript(transcript)
    store_extracted_items(meeting_id, items)
    return items
