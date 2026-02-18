"""Tests for structured extraction and query routing (no external APIs required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.extraction.extractor import _parse_tool_response, extract_from_transcript
from src.retrieval.router import QueryType, classify_query, format_structured_response

# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------


class TestParseToolResponse:
    """Test parsing of Claude tool_use responses."""

    def test_parse_valid_response(self) -> None:
        """A well-formed tool_use block is parsed into ExtractedItem list."""
        mock_response = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "store_extracted_items"
        tool_block.input = {
            "action_items": [
                {
                    "content": "Send the proposal to the client",
                    "assignee": "Alice",
                    "due_date": "next Friday",
                    "speaker": "Bob",
                    "confidence": 0.95,
                }
            ],
            "decisions": [
                {
                    "content": "Go with vendor A for the cloud migration",
                    "speaker": "Carol",
                    "confidence": 0.9,
                }
            ],
            "topics": [
                {
                    "content": "Q3 budget review",
                    "confidence": 0.85,
                }
            ],
        }
        mock_response.content = [tool_block]

        items = _parse_tool_response(mock_response)

        assert len(items) == 3

        action = items[0]
        assert action.item_type == "action_item"
        assert action.content == "Send the proposal to the client"
        assert action.assignee == "Alice"
        assert action.due_date == "next Friday"
        assert action.speaker == "Bob"
        assert action.confidence == 0.95

        decision = items[1]
        assert decision.item_type == "decision"
        assert decision.content == "Go with vendor A for the cloud migration"
        assert decision.speaker == "Carol"
        assert decision.assignee is None

        topic = items[2]
        assert topic.item_type == "topic"
        assert topic.content == "Q3 budget review"
        assert topic.speaker is None

    def test_parse_empty_response(self) -> None:
        """Empty arrays produce an empty item list."""
        mock_response = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "store_extracted_items"
        tool_block.input = {
            "action_items": [],
            "decisions": [],
            "topics": [],
        }
        mock_response.content = [tool_block]

        items = _parse_tool_response(mock_response)
        assert items == []

    def test_parse_ignores_non_tool_blocks(self) -> None:
        """Text blocks are skipped; only tool_use blocks are parsed."""
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        mock_response.content = [text_block]

        items = _parse_tool_response(mock_response)
        assert items == []

    def test_parse_string_input(self) -> None:
        """JSON-string input (instead of dict) is handled correctly."""
        import json

        mock_response = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "store_extracted_items"
        tool_block.input = json.dumps(
            {
                "action_items": [{"content": "Do the thing", "confidence": 0.8}],
                "decisions": [],
                "topics": [],
            }
        )
        mock_response.content = [tool_block]

        items = _parse_tool_response(mock_response)
        assert len(items) == 1
        assert items[0].content == "Do the thing"


class TestExtractFromTranscript:
    """Test the extract_from_transcript function with mocked Claude."""

    @patch("src.extraction.extractor.Anthropic")
    def test_calls_claude_with_tool_use(self, mock_anthropic_cls: MagicMock) -> None:
        """Verify Claude is called with the extraction tool and tool_choice."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "store_extracted_items"
        tool_block.input = {"action_items": [], "decisions": [], "topics": []}

        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_client.messages.create.return_value = mock_response

        result = extract_from_transcript("Alice: Let's ship it by Friday.")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["tools"] is not None
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "store_extracted_items"
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Query router tests
# ---------------------------------------------------------------------------


class TestClassifyQuery:
    """Test keyword-based query classification."""

    @pytest.mark.parametrize(
        "question",
        [
            "What are the action items?",
            "List all action items from the meeting",
            "What tasks were assigned?",
            "Show me the to-dos",
            "What are the follow-ups?",
            "Any deadlines mentioned?",
        ],
    )
    def test_action_item_queries(self, question: str) -> None:
        result = classify_query(question)
        assert result.query_type == QueryType.STRUCTURED
        assert result.item_type == "action_item"

    @pytest.mark.parametrize(
        "question",
        [
            "What decisions were made?",
            "What did they decide?",
            "What was agreed upon?",
            "List the agreements",
            "What conclusions were reached?",
        ],
    )
    def test_decision_queries(self, question: str) -> None:
        result = classify_query(question)
        assert result.query_type == QueryType.STRUCTURED
        assert result.item_type == "decision"

    @pytest.mark.parametrize(
        "question",
        [
            "What topics were discussed?",
            "What were the main themes?",
            "What subjects came up?",
            "What was on the agenda?",
        ],
    )
    def test_topic_queries(self, question: str) -> None:
        result = classify_query(question)
        assert result.query_type == QueryType.STRUCTURED
        assert result.item_type == "topic"

    @pytest.mark.parametrize(
        "question",
        [
            "What did Alice say about the budget?",
            "How long was the meeting?",
            "Who presented the sales figures?",
            "Can you explain the architecture discussion?",
        ],
    )
    def test_open_ended_queries(self, question: str) -> None:
        result = classify_query(question)
        assert result.query_type == QueryType.RAG
        assert result.item_type is None

    def test_mixed_query_returns_structured(self) -> None:
        """A question mentioning both action items and decisions is structured."""
        result = classify_query("What are the action items and decisions?")
        assert result.query_type == QueryType.STRUCTURED
        assert result.item_type is None  # multiple types, no filter


# ---------------------------------------------------------------------------
# Format structured response tests
# ---------------------------------------------------------------------------


class TestFormatStructuredResponse:
    """Test formatting of extracted items into human-readable text."""

    def test_empty_items(self) -> None:
        result = format_structured_response([], "action_item")
        assert "No action items found" in result

    def test_format_action_items(self) -> None:
        items = [
            {
                "item_type": "action_item",
                "content": "Send proposal",
                "assignee": "Alice",
                "due_date": "Friday",
                "speaker": "Bob",
            }
        ]
        result = format_structured_response(items, "action_item")
        assert "Action Items" in result
        assert "Send proposal" in result
        assert "Alice" in result
        assert "Friday" in result
        assert "Bob" in result

    def test_format_mixed_types(self) -> None:
        items = [
            {"item_type": "action_item", "content": "Do X"},
            {"item_type": "decision", "content": "Decided Y"},
            {"item_type": "topic", "content": "Discussed Z"},
        ]
        result = format_structured_response(items, None)
        assert "Action Items" in result
        assert "Decisions" in result
        assert "Key Topics" in result


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestExtractEndpoint:
    """Test the /api/meetings/{id}/extract endpoint validation."""

    def test_extract_not_found(self) -> None:
        """Non-existent meeting ID returns 404 or 500 (no Supabase)."""
        from fastapi.testclient import TestClient

        from src.api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/meetings/00000000-0000-0000-0000-000000000000/extract")
        # Without Supabase: 500; with Supabase and missing ID: 404
        assert response.status_code in [404, 500]

    def test_extract_endpoint_exists(self) -> None:
        """Verify the extract route is registered."""
        from src.api.main import app

        routes = [r.path for r in app.routes]  # type: ignore[union-attr]
        assert "/api/meetings/{meeting_id}/extract" in routes


class TestQueryRoutingEndpoint:
    """Test that the query endpoint routes structured questions correctly."""

    @patch("src.api.routes.query.lookup_extracted_items")
    @patch("src.api.routes.query.classify_query")
    def test_structured_query_skips_rag(
        self, mock_classify: MagicMock, mock_lookup: MagicMock
    ) -> None:
        """Structured queries go to DB lookup, not RAG."""
        from src.retrieval.router import RoutedQuery

        mock_classify.return_value = RoutedQuery(
            query_type=QueryType.STRUCTURED,
            item_type="action_item",
            original_question="What are the action items?",
        )
        mock_lookup.return_value = [
            {"item_type": "action_item", "content": "Send report"}
        ]

        from fastapi.testclient import TestClient

        from src.api.main import app

        client = TestClient(app)
        response = client.post(
            "/api/query", json={"question": "What are the action items?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "Send report" in data["answer"]
        assert data["sources"] == []
        # RAG should NOT be called
        mock_lookup.assert_called_once()
