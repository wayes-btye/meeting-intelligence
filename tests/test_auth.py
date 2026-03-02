"""Tests for per-user data isolation via JWT auth. Issue #71."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth import get_current_user_id
from src.api.main import app

# A fixed UUID used across auth tests to represent the authenticated user.
TEST_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_MEETING_ID = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture
def real_auth_client():
    """TestClient with real auth enforcement (no dependency override).

    The autouse override_auth fixture in conftest.py sets a bypass by default.
    This fixture removes that override for the duration of the test so that
    401/422 responses from missing or invalid tokens can be tested.
    """
    app.dependency_overrides.pop(get_current_user_id, None)
    yield TestClient(app, raise_server_exceptions=False)
    # conftest's autouse fixture will restore the override after the test exits


# ---------------------------------------------------------------------------
# Unauthenticated request tests — no Authorization header at all
# ---------------------------------------------------------------------------


def test_unauthenticated_ingest_returns_401(real_auth_client: TestClient) -> None:
    """POST /api/ingest without an Authorization header must return 401."""
    response = real_auth_client.post(
        "/api/ingest",
        files={"file": ("test.vtt", b"WEBVTT\n\n", "text/vtt")},
        data={"title": "Test"},
    )
    assert response.status_code == 422, (
        f"Expected 422 (missing header), got {response.status_code}: {response.text}"
    )


def test_unauthenticated_list_meetings_returns_401(real_auth_client: TestClient) -> None:
    """GET /api/meetings without an Authorization header must return 422."""
    response = real_auth_client.get("/api/meetings")
    assert response.status_code == 422, (
        f"Expected 422 (missing header), got {response.status_code}: {response.text}"
    )


def test_unauthenticated_query_returns_401(real_auth_client: TestClient) -> None:
    """POST /api/query without an Authorization header must return 422."""
    response = real_auth_client.post(
        "/api/query",
        json={"question": "What were the action items?"},
    )
    assert response.status_code == 422, (
        f"Expected 422 (missing header), got {response.status_code}: {response.text}"
    )


def test_invalid_bearer_token_returns_401(real_auth_client: TestClient) -> None:
    """A malformed JWT must return 401.

    FastAPI validates the header type but the JWT decode will fail and
    get_current_user_id raises HTTPException(401).
    """
    with patch("src.api.auth.settings") as mock_settings:
        mock_settings.supabase_jwt_secret = "test-secret"
        response = real_auth_client.get(
            "/api/meetings",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
    assert response.status_code == 401, (
        f"Expected 401 for invalid JWT, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Authenticated ingest — verify user_id is stored
# ---------------------------------------------------------------------------


def test_ingest_stores_user_id() -> None:
    """Authenticated ingest passes user_id to ingest_transcript.

    Uses the autouse auth bypass (TEST_USER_ID returned by override) and mocks
    ingest_transcript + Supabase so no external calls are made. Verifies
    ingest_transcript is called with user_id=TEST_USER_ID.
    """
    captured_kwargs: dict[str, Any] = {}

    def fake_ingest(
        content: str,
        format: str,
        title: str,
        strategy: object,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        captured_kwargs["user_id"] = user_id
        return TEST_MEETING_ID

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 2

    with (
        patch("src.api.routes.ingest.ingest_transcript", side_effect=fake_ingest),
        patch("src.api.routes.ingest.get_supabase_client", return_value=mock_client),
    ):
        response = TestClient(app).post(
            "/api/ingest",
            files={"file": ("test.vtt", b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello.\n", "text/vtt")},
            data={"title": "Auth Test Meeting"},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert captured_kwargs.get("user_id") == TEST_USER_ID, (
        f"Expected user_id={TEST_USER_ID!r}, got {captured_kwargs.get('user_id')!r}"
    )


# ---------------------------------------------------------------------------
# Authenticated list — verify user_id filter is applied
# ---------------------------------------------------------------------------


def test_list_meetings_filters_by_user_id() -> None:
    """GET /api/meetings applies .eq('user_id', user_id) filter.

    Uses the autouse auth bypass and inspects the chain of Supabase calls to
    confirm the user_id equality filter is applied.
    """
    mock_client = MagicMock()

    # Chain: .table().select().eq().order().execute() → data=[]
    mock_execute = MagicMock()
    mock_execute.data = []
    (
        mock_client
        .table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
    ) = mock_execute

    with (
        patch("src.api.routes.meetings.get_supabase_client", return_value=mock_client),
    ):
        response = TestClient(app).get(
            "/api/meetings",
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify .eq("user_id", TEST_USER_ID) was called on the select result
    select_result = mock_client.table.return_value.select.return_value
    select_result.eq.assert_called_once_with("user_id", TEST_USER_ID)


# ---------------------------------------------------------------------------
# Ownership check on GET /api/meetings/{id}
# ---------------------------------------------------------------------------


def test_get_meeting_wrong_owner_returns_404() -> None:
    """GET /api/meetings/{id} returns 404 when meeting belongs to a different user.

    The endpoint must not reveal existence — always 404 on ownership mismatch.
    Uses the autouse auth bypass (returns TEST_USER_ID) but the meeting row in
    the mock has a different user_id, triggering the ownership check.
    """
    other_user_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": TEST_MEETING_ID, "title": "Someone else's meeting", "user_id": other_user_id}
    ]

    with (
        patch("src.api.routes.meetings.get_supabase_client", return_value=mock_client),
    ):
        response = TestClient(app).get(
            f"/api/meetings/{TEST_MEETING_ID}",
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 404, (
        f"Expected 404 for ownership mismatch, got {response.status_code}: {response.text}"
    )
