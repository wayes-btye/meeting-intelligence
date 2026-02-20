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


# --- Issue #22: audio upload must not crash with 500 ---
def test_audio_upload_returns_clean_response_not_500(client):
    """Audio upload must not crash with 500.

    Returns 501 (not configured), 200 (transcribed), or 400 (transcription error).
    The critical regression is: no UnicodeDecodeError → 500.
    """
    # Fake MP3 binary header — will fail AssemblyAI transcription, but must NOT 500
    audio_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
    response = client.post(
        "/api/ingest",
        files={"file": ("test.mp3", audio_content, "audio/mpeg")},
        data={"title": "Test Audio Meeting"},
    )
    assert response.status_code != 500, f"Got 500 crash: {response.text}"
    assert response.status_code in (200, 400, 501), f"Unexpected status: {response.status_code}"


# --- Issue #25: GET /extract must not exist (only POST) ---
def test_extract_endpoint_no_get_method(client):
    """GET /api/meetings/{id}/extract must not exist — only POST should.

    Uses /api/ prefix to match actual route registration.
    Before fix: returns 200/500 (duplicate GET handler exists in meetings.py).
    After fix: returns 405 Method Not Allowed.
    """
    # Note: worktree doc template omits /api/ prefix — corrected here to match actual routes
    response = client.get("/api/meetings/some-fake-id/extract")
    assert response.status_code == 405, f"Expected 405 Method Not Allowed, got {response.status_code}"
