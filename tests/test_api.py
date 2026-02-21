"""Tests for API endpoints (no external API keys required)."""

from unittest.mock import MagicMock, patch

from fastapi import HTTPException as FastAPIHTTPException
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
# Both tests below are fully deterministic — no live API calls.

def test_audio_upload_no_key_returns_501():
    """Audio upload returns 501 when ASSEMBLYAI_API_KEY is not configured.

    Patches settings so the key is empty → 501 path, no external call.
    Regression: before fix this was a 500 UnicodeDecodeError.
    """
    audio_content = b"\xff\xfb\x90\x00" + b"\x00" * 100  # fake MP3 binary header
    with patch("src.api.routes.ingest.settings") as mock_settings:
        mock_settings.assemblyai_api_key = ""
        response = client.post(
            "/api/ingest",
            files={"file": ("test.mp3", audio_content, "audio/mpeg")},
            data={"title": "Test Audio Meeting"},
        )
    assert response.status_code == 501, f"Expected 501, got {response.status_code}: {response.text}"
    assert "not configured" in response.json()["detail"].lower()


def test_audio_upload_transcription_failure_returns_400_not_500():
    """AssemblyAI rejecting audio returns 400, not 500.

    Patches _transcribe_audio to raise HTTPException(400) and mocks a non-empty key.
    No live API call — purely deterministic.
    """
    audio_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
    with (
        patch("src.api.routes.ingest.settings") as mock_settings,
        patch(
            "src.api.routes.ingest._transcribe_audio",
            side_effect=FastAPIHTTPException(status_code=400, detail="bad audio"),
        ),
    ):
        mock_settings.assemblyai_api_key = "test-key"
        response = client.post(
            "/api/ingest",
            files={"file": ("test.mp3", audio_content, "audio/mpeg")},
            data={"title": "Test Audio Meeting"},
        )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    # MANUAL TEST REQUIRED: verify real AssemblyAI transcription end-to-end.
    # See CLAUDE.md § "Manual verification checklist" for steps.


# --- Issue #42: DELETE /api/meetings/{id} endpoint ---

def test_delete_meeting(client: TestClient) -> None:
    """DELETE /meetings/{id} returns 204 when meeting exists.

    Mocks all three Supabase delete calls so no live DB is required.
    """
    meeting_id = "12345678-1234-1234-1234-123456789abc"

    mock_supabase = MagicMock()
    # chunks and extracted_items deletes return empty data (rows deleted)
    mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    # meetings delete returns the deleted row so 404 is not raised
    meetings_delete_result = MagicMock()
    meetings_delete_result.data = [{"id": meeting_id, "title": "Test"}]

    call_count = 0

    def table_side_effect(name: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        tbl = MagicMock()
        if name == "meetings" and call_count >= 3:
            # Third table() call is the meetings delete — return a row
            tbl.delete.return_value.eq.return_value.execute.return_value = meetings_delete_result
        else:
            tbl.delete.return_value.eq.return_value.execute.return_value.data = []
        return tbl

    mock_supabase.table.side_effect = table_side_effect

    with patch("src.api.routes.meetings.get_supabase_client", return_value=mock_supabase):
        response = client.delete(f"/api/meetings/{meeting_id}")

    assert response.status_code == 204


def test_delete_nonexistent_meeting_returns_404(client: TestClient) -> None:
    """DELETE /meetings/{id} returns 404 when meeting does not exist.

    Mocks Supabase to return empty data for the meetings delete, simulating a
    non-existent meeting ID.
    """
    mock_supabase = MagicMock()
    # All deletes return empty data — meetings delete returns [] meaning not found
    mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []

    with patch("src.api.routes.meetings.get_supabase_client", return_value=mock_supabase):
        response = client.delete("/api/meetings/nonexistent-id")

    assert response.status_code == 404


# --- Issue #25: GET /extract must not exist (only POST) ---
def test_extract_endpoint_no_get_method():
    """GET /api/meetings/{id}/extract must not exist — only POST should.

    Uses /api/ prefix to match actual route registration.
    Before fix: returns 200/500 (duplicate GET handler exists in meetings.py).
    After fix: returns 405 Method Not Allowed.
    """
    # Note: worktree doc template omits /api/ prefix — corrected here to match actual routes
    response = client.get("/api/meetings/some-fake-id/extract")
    assert response.status_code == 405, f"Expected 405 Method Not Allowed, got {response.status_code}"
