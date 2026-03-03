"""Tests for per-user data isolation via JWT auth. Issue #71."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import jwt
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


def test_unauthenticated_ingest_returns_422(real_auth_client: TestClient) -> None:
    """POST /api/ingest without an Authorization header must return 422."""
    response = real_auth_client.post(
        "/api/ingest",
        files={"file": ("test.vtt", b"WEBVTT\n\n", "text/vtt")},
        data={"title": "Test"},
    )
    assert response.status_code == 422, (
        f"Expected 422 (missing header), got {response.status_code}: {response.text}"
    )


def test_unauthenticated_list_meetings_returns_422(real_auth_client: TestClient) -> None:
    """GET /api/meetings without an Authorization header must return 422."""
    response = real_auth_client.get("/api/meetings")
    assert response.status_code == 422, (
        f"Expected 422 (missing header), got {response.status_code}: {response.text}"
    )


def test_unauthenticated_query_returns_422(real_auth_client: TestClient) -> None:
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

    Patches the JWKS client to raise PyJWKClientError (as it would for an
    unrecognised key ID or malformed token) — no real JWKS network call. (#71)
    """
    with patch("src.api.auth._jwks_client.get_signing_key_from_jwt", side_effect=jwt.PyJWTError("bad token")):
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

    The endpoint filters by both id and user_id at DB level, so a row owned by
    another user is never returned — the empty result triggers the 404.
    """
    mock_client = MagicMock()
    # DB-level filter (id + user_id) returns nothing for a non-owned meeting.
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

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


# ---------------------------------------------------------------------------
# Unconfigured JWT secret → 503
# ---------------------------------------------------------------------------


def test_jwks_fetch_failure_returns_401(real_auth_client: TestClient) -> None:
    """A JWKS network failure must return 401, not 500.

    If Supabase's JWKS endpoint is unreachable (e.g. network error or key not
    found), PyJWKClient raises PyJWKError which is a subclass of PyJWTError.
    The except clause in get_current_user_id must catch it and return 401. (#71)
    """
    with patch("src.api.auth._jwks_client.get_signing_key_from_jwt", side_effect=jwt.PyJWTError("jwks unavailable")):
        response = real_auth_client.get(
            "/api/meetings",
            headers={"Authorization": "Bearer some.jwt.token"},
        )
    assert response.status_code == 401, (
        f"Expected 401 for JWKS failure, got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Structured query path — user isolation
# ---------------------------------------------------------------------------


def test_structured_query_passes_user_id_to_lookup() -> None:
    """POST /api/query for a structured question passes user_id to lookup_extracted_items.

    Verifies the structured path (action items, decisions, topics) is scoped to
    the authenticated user's meetings and cannot return other users' data. (#71)
    """
    from unittest.mock import call

    mock_client = MagicMock()
    # Return an empty meeting list for the user — lookup should return [] early.
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("src.retrieval.router.get_supabase_client", return_value=mock_client):
        response = TestClient(app).post(
            "/api/query",
            json={"question": "What were the action items?"},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    # Verify the meetings table was queried with eq("user_id", TEST_USER_ID)
    # — proof that user_id reached lookup_extracted_items.
    eq_calls = mock_client.table.return_value.select.return_value.eq.call_args_list
    assert any(c == call("user_id", TEST_USER_ID) for c in eq_calls), (
        f"Expected eq('user_id', {TEST_USER_ID!r}) in Supabase calls, got: {eq_calls}"
    )
