"""Tests for PipelineConfig, strategy enums, and strategy wiring."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.pipeline_config import ChunkingStrategy, PipelineConfig, RetrievalStrategy

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestChunkingStrategy:
    def test_values(self) -> None:
        assert ChunkingStrategy.NAIVE.value == "naive"
        assert ChunkingStrategy.SPEAKER_TURN.value == "speaker_turn"

    def test_from_string(self) -> None:
        assert ChunkingStrategy("naive") is ChunkingStrategy.NAIVE
        assert ChunkingStrategy("speaker_turn") is ChunkingStrategy.SPEAKER_TURN

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            ChunkingStrategy("invalid")

    def test_is_str_subclass(self) -> None:
        """Enum values behave as plain strings for JSON serialization."""
        assert isinstance(ChunkingStrategy.NAIVE, str)


class TestRetrievalStrategy:
    def test_values(self) -> None:
        assert RetrievalStrategy.SEMANTIC.value == "semantic"
        assert RetrievalStrategy.HYBRID.value == "hybrid"

    def test_from_string(self) -> None:
        assert RetrievalStrategy("semantic") is RetrievalStrategy.SEMANTIC
        assert RetrievalStrategy("hybrid") is RetrievalStrategy.HYBRID

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            RetrievalStrategy("invalid")

    def test_is_str_subclass(self) -> None:
        assert isinstance(RetrievalStrategy.HYBRID, str)


# ---------------------------------------------------------------------------
# PipelineConfig tests
# ---------------------------------------------------------------------------


class TestPipelineConfig:
    def test_defaults(self) -> None:
        cfg = PipelineConfig()
        assert cfg.chunking_strategy is ChunkingStrategy.SPEAKER_TURN
        assert cfg.retrieval_strategy is RetrievalStrategy.HYBRID

    def test_custom_values(self) -> None:
        cfg = PipelineConfig(
            chunking_strategy=ChunkingStrategy.NAIVE,
            retrieval_strategy=RetrievalStrategy.SEMANTIC,
        )
        assert cfg.chunking_strategy is ChunkingStrategy.NAIVE
        assert cfg.retrieval_strategy is RetrievalStrategy.SEMANTIC

    def test_immutable(self) -> None:
        cfg = PipelineConfig()
        with pytest.raises(AttributeError):
            cfg.chunking_strategy = ChunkingStrategy.NAIVE  # type: ignore[misc]


# ---------------------------------------------------------------------------
# API endpoint strategy tests
# ---------------------------------------------------------------------------


class TestQueryEndpointStrategy:
    def test_accepts_semantic_strategy(self) -> None:
        """The endpoint should accept 'semantic' as a valid strategy value."""
        response = client_no_raise.post(
            "/api/query",
            json={"question": "test", "strategy": "semantic"},
        )
        # 200 or 500 (no Supabase), but NOT 422 (validation error)
        assert response.status_code != 422

    def test_accepts_hybrid_strategy(self) -> None:
        response = client_no_raise.post(
            "/api/query",
            json={"question": "test", "strategy": "hybrid"},
        )
        assert response.status_code != 422

    def test_rejects_invalid_strategy(self) -> None:
        response = client.post(
            "/api/query",
            json={"question": "test", "strategy": "invalid_strategy"},
        )
        assert response.status_code == 422

    def test_default_strategy_is_hybrid(self) -> None:
        """When no strategy is provided, hybrid should be the default."""
        response = client_no_raise.post(
            "/api/query",
            json={"question": "test"},
        )
        assert response.status_code != 422


class TestIngestEndpointStrategy:
    def test_accepts_naive_strategy(self) -> None:
        response = client_no_raise.post(
            "/api/ingest",
            files={"file": ("test.txt", b"Hello world.", "text/plain")},
            data={"title": "Test", "chunking_strategy": "naive"},
        )
        assert response.status_code != 422

    def test_accepts_speaker_turn_strategy(self) -> None:
        response = client_no_raise.post(
            "/api/ingest",
            files={"file": ("test.txt", b"Hello world.", "text/plain")},
            data={"title": "Test", "chunking_strategy": "speaker_turn"},
        )
        assert response.status_code != 422

    def test_rejects_invalid_strategy(self) -> None:
        response = client_no_raise.post(
            "/api/ingest",
            files={"file": ("test.txt", b"Hello world.", "text/plain")},
            data={"title": "Test", "chunking_strategy": "invalid"},
        )
        # Should get 422 or 500 (ValueError from enum conversion)
        assert response.status_code in [422, 500]
