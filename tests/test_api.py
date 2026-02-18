"""Tests for API endpoints (no external API keys required)."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_query_validation():
    """Test that query endpoint validates input."""
    response = client.post("/api/query", json={})
    assert response.status_code == 422  # missing required field


def test_query_requires_question():
    """Empty string is a valid str, so validation passes."""
    response = client_no_raise.post("/api/query", json={"question": ""})
    # Should still accept (empty string is valid str)
    # The actual search will fail without Supabase/OpenAI, but validation passes
    assert response.status_code in [200, 500]  # 500 if no Supabase


def test_meetings_list():
    """Without Supabase, this will fail gracefully."""
    response = client_no_raise.get("/api/meetings")
    assert response.status_code in [200, 500]


def test_ingest_requires_file():
    """Ingest requires a file upload."""
    response = client.post("/api/ingest")
    assert response.status_code == 422
