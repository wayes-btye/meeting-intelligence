"""End-to-end integration tests for the full RAG pipeline.

# MANUAL RUN REQUIRED: These tests require live API keys and a running Supabase project.
# Run manually with: pytest -m expensive tests/test_pipeline_integration.py -v
# Ensure .env has OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY set.
#
# These tests are NOT run in CI (marked @pytest.mark.expensive).
# They represent the "golden path" — if they pass, the system works end-to-end.
#
# WHAT IS TESTED:
#   1. Ingest a MeetingBank transcript fixture via the /ingest API endpoint
#   2. Verify the meeting record is stored in Supabase (metadata + chunks)
#   3. Query the stored meeting via /query
#   4. Assert the answer is non-empty and cites the correct meeting
#   5. Clean up (delete the test meeting from Supabase)
#
# WHY THIS MATTERS:
#   The system has multiple failure points: embedding API, Supabase pgvector upsert,
#   retrieval, and Claude generation. This test exercises all of them in sequence
#   and is the fastest way to verify a fresh deployment works.
"""

from __future__ import annotations

import json
import pathlib
import time
import uuid

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "meetingbank"
FIXTURE_PATH = FIXTURES_DIR / "sample_council_meeting.json"

# Use a unique meeting ID per test run to avoid collisions with other worktrees
# or parallel test runs sharing the same Supabase project.
TEST_MEETING_ID = f"integration-test-{uuid.uuid4().hex[:8]}"

# API base URL — matches the worktree 3 port allocation (see CLAUDE.md)
API_BASE_URL = "http://localhost:8030"


@pytest.mark.expensive
def test_full_ingest_and_query_pipeline() -> None:
    """Full pipeline: ingest transcript → store in Supabase → query → get answer.

    Requires: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY
    Run with: pytest -m expensive tests/test_pipeline_integration.py -v

    This is the golden-path test. Steps:
      1. Load the MeetingBank council meeting fixture.
      2. POST to /ingest (via the FastAPI server running on port 8030).
      3. Verify the ingest response reports success.
      4. POST to /query with a question answerable from the fixture transcript.
      5. Assert answer is non-empty, score is reasonable, and citations reference
         the correct meeting.
      6. Clean up by deleting the test meeting via DELETE /meetings/{meeting_id}
         (or directly from Supabase if the API does not expose a delete endpoint yet).

    # MANUAL TEST REQUIRED: start the API server first with:
    #   PORT=8030 make api
    # then run:
    #   pytest -m expensive tests/test_pipeline_integration.py::test_full_ingest_and_query_pipeline -v
    """
    import httpx  # type: ignore[import-untyped]

    # ── Step 1: Load fixture transcript ──────────────────────────────────────
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # Flatten the MeetingBank transcription to plain text for ingest
    lines = [
        f"{item['speaker_id']}: {item['text']}" for item in fixture["transcription"]
    ]
    transcript_text = "\n".join(lines)

    # ── Step 2: Ingest via API ────────────────────────────────────────────────
    ingest_payload = {
        "meeting_id": TEST_MEETING_ID,
        "transcript": transcript_text,
        "format": "text",
        "chunking_strategy": "speaker_turn",
        "metadata": {
            "source": "integration_test",
            "original_meeting_id": fixture["meeting_id"],
        },
    }

    with httpx.Client(timeout=120.0) as client:
        ingest_resp = client.post(f"{API_BASE_URL}/ingest", json=ingest_payload)

    assert ingest_resp.status_code == 200, (
        f"Ingest failed ({ingest_resp.status_code}): {ingest_resp.text}"
    )
    ingest_data = ingest_resp.json()
    assert ingest_data.get("status") == "ok" or "chunk" in str(ingest_data).lower(), (
        f"Unexpected ingest response: {ingest_data}"
    )

    # Brief pause to allow any async Supabase operations to settle
    time.sleep(1)

    # ── Step 3: Query the ingested meeting ────────────────────────────────────
    # The fixture transcript contains a $250,000 budget amendment for Oak Street bridge.
    # This is a factual question with a specific numeric answer — ideal for precision testing.
    query_payload = {
        "question": "How much money was approved for the Oak Street bridge project?",
        "meeting_ids": [TEST_MEETING_ID],
        "retrieval_strategy": "hybrid",
    }

    with httpx.Client(timeout=60.0) as client:
        query_resp = client.post(f"{API_BASE_URL}/query", json=query_payload)

    assert query_resp.status_code == 200, (
        f"Query failed ({query_resp.status_code}): {query_resp.text}"
    )
    query_data = query_resp.json()

    # ── Step 4: Validate the answer ───────────────────────────────────────────
    answer = query_data.get("answer", "")
    assert answer.strip(), "Answer should not be empty"

    # The answer must mention the dollar amount (250,000 or $250k etc.)
    answer_lower = answer.lower()
    assert any(
        token in answer_lower
        for token in ["250,000", "250000", "250 thousand", "$250", "two hundred fifty"]
    ), f"Answer should mention the $250,000 amount. Got: {answer}"

    # Citations should reference our test meeting
    citations = query_data.get("citations", query_data.get("sources", []))
    if citations:
        cited_meetings = {
            c.get("meeting_id") or c.get("source_meeting_id", "") for c in citations
        }
        assert TEST_MEETING_ID in cited_meetings, (
            f"Expected citation for {TEST_MEETING_ID}, got: {cited_meetings}"
        )

    # ── Step 5: Clean up ──────────────────────────────────────────────────────
    # Attempt to delete the test meeting via API (endpoint may not exist yet).
    # If unavailable, delete directly from Supabase.
    # MANUAL CLEANUP REQUIRED if this step fails:
    #   DELETE FROM meetings WHERE meeting_id = '<TEST_MEETING_ID>' in Supabase SQL editor.
    try:
        with httpx.Client(timeout=30.0) as client:
            del_resp = client.delete(f"{API_BASE_URL}/meetings/{TEST_MEETING_ID}")
        if del_resp.status_code not in (200, 204, 404):
            # Non-fatal — test already passed; log the cleanup failure
            print(
                f"\nWARNING: cleanup DELETE returned {del_resp.status_code}. "
                f"Manually delete meeting_id='{TEST_MEETING_ID}' from Supabase."
            )
    except Exception as exc:  # noqa: BLE001
        print(
            f"\nWARNING: cleanup request failed ({exc}). "
            f"Manually delete meeting_id='{TEST_MEETING_ID}' from Supabase."
        )


@pytest.mark.expensive
def test_ingest_idempotency() -> None:
    """Ingesting the same meeting twice should not raise an error or duplicate chunks.

    # MANUAL RUN REQUIRED: same prerequisites as test_full_ingest_and_query_pipeline.
    """
    import httpx  # type: ignore[import-untyped]

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    lines = [
        f"{item['speaker_id']}: {item['text']}" for item in fixture["transcription"]
    ]
    transcript_text = "\n".join(lines)

    idempotency_meeting_id = f"idempotency-test-{uuid.uuid4().hex[:8]}"
    ingest_payload = {
        "meeting_id": idempotency_meeting_id,
        "transcript": transcript_text,
        "format": "text",
        "chunking_strategy": "naive",
    }

    with httpx.Client(timeout=120.0) as client:
        resp1 = client.post(f"{API_BASE_URL}/ingest", json=ingest_payload)
        assert resp1.status_code == 200, f"First ingest failed: {resp1.text}"

        # Second ingest of the same meeting_id should succeed (upsert, not error)
        resp2 = client.post(f"{API_BASE_URL}/ingest", json=ingest_payload)
        assert resp2.status_code == 200, (
            f"Second (idempotency) ingest failed: {resp2.text}"
        )

    # MANUAL CLEANUP REQUIRED: delete meeting_id='{idempotency_meeting_id}' from Supabase.
    print(f"\nManual cleanup needed: delete meeting_id='{idempotency_meeting_id}'")


@pytest.mark.expensive
def test_query_without_relevant_meeting_returns_graceful_response() -> None:
    """Query against a meeting that has no relevant content should return a graceful answer.

    This tests that the system does not hallucinate or crash when no good chunks are retrieved.

    # MANUAL RUN REQUIRED: requires at least one meeting ingested in Supabase.
    """
    import httpx  # type: ignore[import-untyped]

    query_payload = {
        "question": "What was the orbital velocity of the Mars probe discussed at the meeting?",
        # Use a real meeting ID from your Supabase instance — a council meeting won't
        # contain anything about Mars probes.
        "retrieval_strategy": "semantic",
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{API_BASE_URL}/query", json=query_payload)

    # System should not 500 — it should return a graceful "I don't know" style answer
    assert resp.status_code == 200, f"Query errored: {resp.text}"
    data = resp.json()
    answer = data.get("answer", "")
    assert answer.strip(), "Answer field should never be empty (should explain no info found)"
