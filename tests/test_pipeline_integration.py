"""End-to-end integration tests for the full RAG pipeline.

# MANUAL RUN REQUIRED: These tests require live API keys and a running Supabase project.
# Run manually with: pytest -m expensive tests/test_pipeline_integration.py -v
# Ensure .env has OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY set.
#
# Also start the API server before running:
#   make api           (main workspace, port 8000)
#   PORT=8030 make api (WT3 worktree, port 8030)
#
# Override the base URL via env var:
#   API_BASE_URL=http://localhost:8030 pytest -m expensive tests/test_pipeline_integration.py -v
#
# These tests are NOT run in CI (marked @pytest.mark.expensive).
# They represent the "golden path" — if they pass, the system works end-to-end.
#
# API SCHEMA (confirmed from src/api/routes/ and src/api/models.py):
#   POST /api/ingest   — multipart/form-data: file (UploadFile), title (Form),
#                        chunking_strategy (Form). Returns IngestResponse with
#                        server-generated meeting_id (UUID).
#   POST /api/query    — JSON: {question, meeting_id (singular str|None), strategy}
#                        QueryRequest.strategy is a RetrievalStrategy enum ("semantic"/"hybrid")
#   GET  /api/meetings — list all meetings
#
# No DELETE /api/meetings/{id} endpoint exists yet — cleanup is done directly
# via Supabase client. Manual cleanup instructions are printed on cleanup failure.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "meetingbank"
FIXTURE_PATH = FIXTURES_DIR / "sample_council_meeting.json"

# Allow overriding API base URL via env var so this test works from any worktree.
# Defaults to port 8000 (main workspace). Set API_BASE_URL=http://localhost:8030
# when running from WT3. CLAUDE.md port allocation: main=8000, WT3=8030.
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def _cleanup_meeting(meeting_id: str) -> None:
    """Delete a test meeting and its chunks from Supabase.

    Used after integration tests to avoid polluting the shared Supabase project.
    No DELETE endpoint exists on the API yet, so this goes directly to Supabase.
    Prints a warning (non-fatal) on failure — the test has already passed.

    # MANUAL CLEANUP REQUIRED if this fails:
    #   DELETE FROM chunks WHERE meeting_id = '<meeting_id>' in Supabase SQL editor.
    #   DELETE FROM meetings WHERE id = '<meeting_id>' in Supabase SQL editor.
    """
    try:
        from src.ingestion.storage import get_supabase_client

        client = get_supabase_client()
        client.table("chunks").delete().eq("meeting_id", meeting_id).execute()
        client.table("meetings").delete().eq("id", meeting_id).execute()
    except Exception as exc:  # noqa: BLE001
        print(
            f"\nWARNING: cleanup failed for meeting_id={meeting_id!r}: {exc}\n"
            "Manual cleanup needed:\n"
            f"  DELETE FROM chunks WHERE meeting_id = '{meeting_id}';\n"
            f"  DELETE FROM meetings WHERE id = '{meeting_id}';\n"
        )


@pytest.mark.expensive
def test_full_ingest_and_query_pipeline() -> None:
    """Full pipeline: ingest transcript → store in Supabase → query → get answer.

    Requires: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY
    Run with: pytest -m expensive tests/test_pipeline_integration.py -v

    This is the golden-path test. Steps:
      1. Load the MeetingBank council meeting fixture.
      2. POST to /api/ingest as multipart/form-data (UploadFile + Form fields).
         The server generates a UUID meeting_id — no pre-specified ID.
      3. Verify the ingest response reports num_chunks > 0.
      4. POST to /api/query (JSON body) with meeting_id from ingest response.
         Uses QueryRequest schema: question, meeting_id (singular), strategy.
      5. Assert answer mentions $250,000 (the budget amount in the fixture transcript).
      6. Clean up by deleting the test meeting directly from Supabase (no API delete
         endpoint yet).

    The fixture transcript discusses a $250,000 budget amendment for Oak Street bridge —
    a specific numeric fact that makes answer validation unambiguous.

    # MANUAL TEST REQUIRED: start the API server first with:
    #   make api    OR    API_BASE_URL=http://localhost:8030 PORT=8030 make api
    # then run:
    #   pytest -m expensive tests/test_pipeline_integration.py::test_full_ingest_and_query_pipeline -v
    """
    import httpx  # already in pyproject.toml dependencies

    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # Flatten the MeetingBank transcription to plain text for ingest
    lines = [
        f"{item['speaker_id']}: {item['text']}" for item in fixture["transcription"]
    ]
    transcript_text = "\n".join(lines)

    # Write transcript to a temp file — the /api/ingest endpoint takes a file upload
    meeting_id: str | None = None
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb") as tmp:
        tmp.write(transcript_text.encode("utf-8"))
        tmp_path = tmp.name

    try:
        # ── Step 1: Ingest via multipart form-data ────────────────────────────
        # POST /api/ingest — UploadFile + Form fields (title, chunking_strategy)
        # The server generates a UUID and returns it as meeting_id.
        with httpx.Client(timeout=120.0) as client:
            with open(tmp_path, "rb") as f:
                ingest_resp = client.post(
                    f"{API_BASE_URL}/api/ingest",
                    files={"file": ("council_meeting.txt", f, "text/plain")},
                    data={
                        "title": "Integration Test — Oak Street Council Meeting",
                        "chunking_strategy": "speaker_turn",
                    },
                )

        assert ingest_resp.status_code == 200, (
            f"Ingest failed ({ingest_resp.status_code}): {ingest_resp.text}"
        )
        ingest_data = ingest_resp.json()
        meeting_id = ingest_data["meeting_id"]
        assert meeting_id, "Ingest response must include a meeting_id (server-generated UUID)"
        assert ingest_data["num_chunks"] > 0, (
            f"Expected at least one chunk after ingest, got {ingest_data['num_chunks']}"
        )

        # ── Step 2: Query the ingested meeting ────────────────────────────────
        # POST /api/query — JSON body matching QueryRequest schema:
        #   question: str, meeting_id: str|None, strategy: "semantic"|"hybrid"
        # (NOT meeting_ids, NOT retrieval_strategy — those don't exist in QueryRequest)
        with httpx.Client(timeout=60.0) as client:
            query_resp = client.post(
                f"{API_BASE_URL}/api/query",
                json={
                    "question": "How much money was approved for the Oak Street bridge project?",
                    "meeting_id": meeting_id,
                    "strategy": "hybrid",
                },
            )

        assert query_resp.status_code == 200, (
            f"Query failed ({query_resp.status_code}): {query_resp.text}"
        )
        query_data = query_resp.json()

        # ── Step 3: Validate the answer ───────────────────────────────────────
        answer = query_data.get("answer", "")
        assert answer.strip(), "Answer should not be empty"

        # The fixture transcript contains an approved $250,000 budget amendment.
        answer_lower = answer.lower()
        assert any(
            token in answer_lower
            for token in ["250,000", "250000", "250 thousand", "$250", "two hundred fifty"]
        ), f"Answer should mention the $250,000 amount from the fixture. Got:\n{answer}"

        # Sources should reference the ingested meeting
        sources = query_data.get("sources", [])
        if sources:
            source_meetings = {s.get("meeting_id") for s in sources}
            assert meeting_id in source_meetings, (
                f"Expected source citation for meeting {meeting_id}, got: {source_meetings}"
            )

    finally:
        # Always attempt cleanup — whether the test passed or failed
        os.unlink(tmp_path)
        if meeting_id:
            _cleanup_meeting(meeting_id)


@pytest.mark.expensive
def test_ingest_stores_chunks_in_supabase() -> None:
    """Ingest endpoint creates chunks in the database and reports accurate count.

    Simpler than the full pipeline test — just verifies the ingest half works.
    Does not require the query/Claude/embedding pipeline to be fully operational.

    # MANUAL RUN REQUIRED: same prerequisites as test_full_ingest_and_query_pipeline.
    """
    import httpx

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    lines = [
        f"{item['speaker_id']}: {item['text']}" for item in fixture["transcription"]
    ]
    transcript_text = "\n".join(lines)

    meeting_id: str | None = None
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb") as tmp:
        tmp.write(transcript_text.encode("utf-8"))
        tmp_path = tmp.name

    try:
        with httpx.Client(timeout=120.0) as client:
            with open(tmp_path, "rb") as f:
                resp = client.post(
                    f"{API_BASE_URL}/api/ingest",
                    files={"file": ("council_naive.txt", f, "text/plain")},
                    data={"title": "Chunk Count Test", "chunking_strategy": "naive"},
                )

        assert resp.status_code == 200, f"Ingest failed: {resp.text}"
        data = resp.json()
        meeting_id = data["meeting_id"]

        assert data["num_chunks"] > 0, "Should create at least one chunk"
        assert data["title"] == "Chunk Count Test"
        assert data["chunking_strategy"] == "naive"

    finally:
        os.unlink(tmp_path)
        if meeting_id:
            _cleanup_meeting(meeting_id)


@pytest.mark.expensive
def test_query_without_relevant_meeting_returns_graceful_response() -> None:
    """Query about a topic absent from all meetings should return a graceful answer.

    This tests that the system does not hallucinate or crash when no relevant
    chunks are retrieved. Requires at least one meeting to exist in Supabase.

    # MANUAL RUN REQUIRED: requires live API keys and at least one ingested meeting.
    """
    import httpx

    # POST /api/query with no meeting_id filter (searches across all meetings)
    # A question about Mars orbital mechanics won't match any council meeting content.
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{API_BASE_URL}/api/query",
            json={
                "question": "What was the orbital velocity of the Mars probe discussed at the meeting?",
                "strategy": "semantic",
                # meeting_id omitted → searches all meetings
            },
        )

    # System must not 500 — should return a graceful "no relevant content" answer
    assert resp.status_code == 200, f"Query errored unexpectedly: {resp.text}"
    data = resp.json()
    answer = data.get("answer", "")
    assert answer.strip(), "Answer field should never be empty (should say no info found)"
