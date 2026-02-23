"""Tests for the image summary endpoint (POST /api/meetings/{id}/image-summary).

Automated tests cover only the no-API-key path (501) and not-found (404).
Live Gemini API calls are marked @pytest.mark.expensive and excluded from CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_image_summary_no_api_key_returns_501() -> None:
    """POST /api/meetings/{id}/image-summary returns 501 when GOOGLE_API_KEY is absent.

    This is the primary automated test: no external calls made, purely deterministic.
    The endpoint must degrade gracefully rather than raise a 500.
    """
    meeting_id = "12345678-1234-1234-1234-123456789abc"

    with patch("src.api.routes.image_summary.settings") as mock_settings:
        mock_settings.google_api_key = ""
        response = client.post(f"/api/meetings/{meeting_id}/image-summary")

    assert response.status_code == 501, (
        f"Expected 501 when GOOGLE_API_KEY is absent, got {response.status_code}: {response.text}"
    )
    detail = response.json()["detail"].lower()
    assert "not configured" in detail or "google_api_key" in detail, (
        f"Expected mention of missing key in detail, got: {detail}"
    )


def test_image_summary_meeting_not_found_returns_404() -> None:
    """POST /api/meetings/{id}/image-summary returns 404 when meeting does not exist.

    Mocks: settings has a key, Supabase returns empty data.
    """
    meeting_id = "12345678-1234-1234-1234-123456789abc"

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with (
        patch("src.api.routes.image_summary.settings") as mock_settings,
        patch("src.api.routes.image_summary.get_supabase_client", return_value=mock_supabase),
    ):
        mock_settings.google_api_key = "fake-key"
        response = client.post(f"/api/meetings/{meeting_id}/image-summary")

    assert response.status_code == 404, (
        f"Expected 404 for missing meeting, got {response.status_code}: {response.text}"
    )


def test_image_summary_no_transcript_returns_400() -> None:
    """POST /api/meetings/{id}/image-summary returns 400 when meeting has no transcript."""
    meeting_id = "12345678-1234-1234-1234-123456789abc"

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": meeting_id, "raw_transcript": None}
    ]

    with (
        patch("src.api.routes.image_summary.settings") as mock_settings,
        patch("src.api.routes.image_summary.get_supabase_client", return_value=mock_supabase),
    ):
        mock_settings.google_api_key = "fake-key"
        response = client.post(f"/api/meetings/{meeting_id}/image-summary")

    assert response.status_code == 400, (
        f"Expected 400 for missing transcript, got {response.status_code}: {response.text}"
    )


# --- Expensive test (live Gemini API call) ---
# Run manually with: pytest tests/test_image_summary.py -m expensive

# NOTE: No @pytest.mark.expensive test is included here because the live Gemini
# image generation API is unstable in CI and requires a real API key plus a valid
# meeting_id in the database. Manual testing is the verification path for the happy
# path. See PR description for the manual test checklist.
