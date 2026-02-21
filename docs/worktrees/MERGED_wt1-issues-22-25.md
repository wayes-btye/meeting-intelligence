# Worktree WT1 — Issues #22 and #25
**Status:** `MERGED` — PR #36 merged 2026-02-20, worktree removed
**Branch:** `fix/22-25-audio-endpoint`
**Created from:** main @ 771203b

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, Streamlit frontend, Supabase (pgvector) for vector + metadata storage, Claude for generation, OpenAI for embeddings.

**CRITICAL — how the codebase works:**
- All configuration lives in `src/config.py` via Pydantic `Settings`. Always use `settings.x` not `os.getenv("X")` — `os.getenv()` does not read `.env` files on Windows. This was the root cause of a major bug fixed in PR #27.
- API routes live in `src/api/routes/`
- Tests in `tests/` — 108 pass on main. Do not break them.
- Lint with `ruff check src/` — must be clean before PR
- Type check `mypy src/` — there are pre-existing 218 errors in main (tracked in Issue #30, separate worktree). Do not worry about errors in files you didn't touch; do not introduce new ones in files you do touch.

**What PR #27 already fixed (do not re-fix):**
- SDK clients now use `settings.x` instead of `os.getenv()`
- UI field names corrected (Issue #24 — closed)
- Core flow manually verified working: upload → chunk → embed → store → query → answer with citations ✅

---

## Your mission

Fix two isolated bugs. Nothing else. Do not touch unrelated code.

---

## Issue #22 — Audio upload crashes with 500

**What happens:** When a user uploads an audio file (.mp3, .wav, .m4a) via `POST /ingest`, the endpoint tries to decode binary audio data as UTF-8 text, which raises a `UnicodeDecodeError` → 500 crash.

**Where to look:** `src/api/routes/ingest.py` — the ingest endpoint reads the uploaded file and passes it to the ingestion pipeline without checking content type.

**Decision you must make:** Check whether `ASSEMBLYAI_API_KEY` is set in `.env`:
- If it's set and non-empty: implement the AssemblyAI transcription flow (upload audio → AssemblyAI API → get transcript text → continue pipeline as normal). The AssemblyAI SDK is likely already a dependency.
- If it's empty or missing: return a clean `501 Not Implemented` response with message `"Audio transcription is not configured. Please upload a text transcript (.vtt, .txt, .json)."` Do NOT crash with a 500.

Either way: **no 500 crash on audio upload**.

Document which path you took in the PR description.

---

## Issue #25 — Duplicate GET extract endpoint

**What happens:** There is a `GET /meetings/{id}/extract` endpoint that should not exist. Only `POST /meetings/{id}/extract` should exist. The GET version returns a malformed response.

**Where to look:** `src/api/routes/extraction.py`

**Fix:** Delete the GET endpoint handler. One endpoint stays: `POST /meetings/{id}/extract`.

---

## TDD approach — MANDATORY

Write the failing tests FIRST. Do not touch implementation code until the tests exist and are confirmed failing (red).

### Step 1: Write failing tests

In `tests/test_api.py`, add:

```python
def test_audio_upload_returns_clean_response_not_500(client):
    """Audio upload must not crash with 500. Returns 501 (not configured) or 200 (transcribed)."""
    audio_content = b"\xff\xfb\x90\x00" + b"\x00" * 100  # fake MP3 binary header
    response = client.post(
        "/ingest",
        files={"file": ("test.mp3", audio_content, "audio/mpeg")},
        data={"title": "Test Audio Meeting"},
    )
    assert response.status_code != 500, f"Got 500 crash: {response.text}"
    assert response.status_code in (200, 400, 501), f"Unexpected status: {response.status_code}"


def test_extract_endpoint_no_get_method(client):
    """GET /meetings/{id}/extract must not exist — only POST should."""
    response = client.get("/meetings/some-fake-id/extract")
    assert response.status_code == 405, f"Expected 405 Method Not Allowed, got {response.status_code}"
```

### Step 2: Confirm they fail (red)

```bash
pytest tests/test_api.py::test_audio_upload_returns_clean_response_not_500 tests/test_api.py::test_extract_endpoint_no_get_method -v
```

Both should fail. If they pass immediately, read the existing code carefully — the behaviour may be different than expected.

### Step 3: Fix the code

### Step 4: Confirm they pass (green)

```bash
pytest tests/test_api.py::test_audio_upload_returns_clean_response_not_500 tests/test_api.py::test_extract_endpoint_no_get_method -v
```

### Step 5: Full regression check

```bash
pytest tests/ -x
ruff check src/
```

Both must be clean before raising the PR.

---

## If you cannot test something

Add a comment directly above the test:
```python
# MANUAL TEST REQUIRED: [describe the exact manual step]
```

Add a "Manual verification needed" section to the PR description with step-by-step instructions.

**Do not skip writing the test.** Write it as accurately as you can, even if it needs live APIs that the test environment doesn't have. Mark it `@pytest.mark.expensive` if it requires live API keys.

---

## Files to touch

| File | Why |
|------|-----|
| `src/api/routes/ingest.py` | Fix audio upload handler |
| `src/api/routes/extraction.py` | Remove duplicate GET endpoint |
| `tests/test_api.py` | Add two new tests |

**Do not touch:** `src/ingestion/`, `src/retrieval/`, `src/evaluation/`, `src/ui/`, `src/config.py`, any other test file.

---

## Definition of done

- [ ] `pytest tests/ -x` — all pass
- [ ] `ruff check src/` — clean
- [ ] No new mypy errors in files you touched (run `mypy src/api/routes/ingest.py src/api/routes/extraction.py`)
- [ ] PR description states whether audio was implemented (AssemblyAI) or gracefully deferred (501)
- [ ] PR description has a "Manual verification needed" section if applicable

---

## How to raise the PR

```bash
git add src/api/routes/ingest.py src/api/routes/extraction.py tests/test_api.py
git commit -m "fix: audio upload returns 501/400 not 500; remove duplicate GET extract endpoint"
gh pr create --title "fix: audio upload clean error + remove duplicate extract endpoint (#22, #25)" --body "..."
```

Close issues in the PR body: "Closes #22, Closes #25"
