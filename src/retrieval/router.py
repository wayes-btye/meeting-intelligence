"""Query router: classify questions as structured (DB lookup) or open-ended (RAG)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.ingestion.storage import get_supabase_client


class QueryType(StrEnum):
    """Classification of a user query."""

    STRUCTURED = "structured"
    RAG = "rag"


@dataclass
class RoutedQuery:
    """Result of query routing."""

    query_type: QueryType
    item_type: str | None = None  # "action_item", "decision", "topic", or None (all)
    original_question: str = ""


# Keywords that signal structured extraction queries
_ACTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\baction\s*items?\b", re.IGNORECASE),
    re.compile(r"\btasks?\b", re.IGNORECASE),
    re.compile(r"\bto[\s-]?dos?\b", re.IGNORECASE),
    re.compile(r"\bassigned\b", re.IGNORECASE),
    re.compile(r"\bfollow[\s-]?ups?\b", re.IGNORECASE),
    re.compile(r"\bdeadlines?\b", re.IGNORECASE),
]

_DECISION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bdecisions?\b", re.IGNORECASE),
    re.compile(r"\bdecide[ds]?\b", re.IGNORECASE),
    re.compile(r"\bagreed\b", re.IGNORECASE),
    re.compile(r"\bagreements?\b", re.IGNORECASE),
    re.compile(r"\bresolved\b", re.IGNORECASE),
    re.compile(r"\bconclusions?\b", re.IGNORECASE),
]

_TOPIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\btopics?\b", re.IGNORECASE),
    re.compile(r"\bthemes?\b", re.IGNORECASE),
    re.compile(r"\bsubjects?\b", re.IGNORECASE),
    re.compile(r"\bagenda\b", re.IGNORECASE),
    re.compile(r"\bdiscussed\b", re.IGNORECASE),
    re.compile(r"\bkey\s*points?\b", re.IGNORECASE),
]

# General structured query signals (match any extracted type)
_GENERAL_STRUCTURED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\blist\s+(all\s+)?(the\s+)?", re.IGNORECASE),
    re.compile(r"\bwhat\s+(were|are)\s+(the\s+)?(main|key)\b", re.IGNORECASE),
    re.compile(r"\bsummarize\s+(the\s+)?", re.IGNORECASE),
]


def classify_query(question: str) -> RoutedQuery:
    """Classify a question as structured or open-ended using keyword matching.

    Args:
        question: The user's natural-language question.

    Returns:
        A RoutedQuery with the classification and optional item_type filter.
    """
    action_match = any(p.search(question) for p in _ACTION_PATTERNS)
    decision_match = any(p.search(question) for p in _DECISION_PATTERNS)
    topic_match = any(p.search(question) for p in _TOPIC_PATTERNS)

    # Specific item type requested
    if action_match and not decision_match and not topic_match:
        return RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type="action_item",
            original_question=question,
        )
    if decision_match and not action_match and not topic_match:
        return RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type="decision",
            original_question=question,
        )
    if topic_match and not action_match and not decision_match:
        return RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type="topic",
            original_question=question,
        )

    # Multiple structured types or general structured signal
    if sum([action_match, decision_match, topic_match]) >= 2:
        return RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type=None,
            original_question=question,
        )

    # Check general structured patterns combined with any match
    general_match = any(p.search(question) for p in _GENERAL_STRUCTURED_PATTERNS)
    if general_match and (action_match or decision_match or topic_match):
        item_type = None
        if action_match:
            item_type = "action_item"
        elif decision_match:
            item_type = "decision"
        elif topic_match:
            item_type = "topic"
        return RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type=item_type,
            original_question=question,
        )

    # Default: open-ended RAG
    return RoutedQuery(
        query_type=QueryType.RAG,
        item_type=None,
        original_question=question,
    )


def lookup_extracted_items(
    meeting_id: str | None = None,
    item_type: str | None = None,
) -> list[dict[str, Any]]:
    """Query the extracted_items table directly.

    Args:
        meeting_id: Optional filter by meeting.
        item_type: Optional filter by type (``"action_item"``, ``"decision"``, ``"topic"``).

    Returns:
        List of extracted item dicts from the database.
    """
    client = get_supabase_client()
    query = client.table("extracted_items").select("*")

    if meeting_id:
        query = query.eq("meeting_id", meeting_id)
    if item_type:
        query = query.eq("item_type", item_type)

    query = query.order("created_at", desc=True)
    result = query.execute()
    return result.data  # type: ignore[no-any-return]


def format_structured_response(items: list[dict[str, Any]], item_type: str | None) -> str:
    """Format extracted items into a human-readable answer string.

    Args:
        items: Raw extracted item dicts from the database.
        item_type: The specific type requested, or None for all types.

    Returns:
        A formatted markdown-style answer.
    """
    if not items:
        type_label = item_type.replace("_", " ") + "s" if item_type else "extracted items"
        return f"No {type_label} found for this meeting."

    # Group by type
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        t = item.get("item_type", "unknown")
        grouped.setdefault(t, []).append(item)

    parts: list[str] = []

    type_labels = {
        "action_item": "Action Items",
        "decision": "Decisions",
        "topic": "Key Topics",
    }

    for t in ["action_item", "decision", "topic"]:
        group = grouped.get(t, [])
        if not group:
            continue

        label = type_labels.get(t, t)
        parts.append(f"**{label}:**")
        for i, item in enumerate(group, 1):
            line = f"  {i}. {item['content']}"
            if item.get("assignee"):
                line += f" (assigned to {item['assignee']})"
            if item.get("due_date"):
                line += f" — due: {item['due_date']}"
            if item.get("speaker"):
                line += f" [mentioned by {item['speaker']}]"
            parts.append(line)
        parts.append("")

    return "\n".join(parts).strip()
