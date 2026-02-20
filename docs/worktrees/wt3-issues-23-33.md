# Worktree WT3 — Issues #23 and #33
**Branch:** `fix/23-33-eval-tests`
**Created from:** main @ 771203b

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, Streamlit frontend, Supabase (pgvector) for vector + metadata storage, Claude for generation, OpenAI for embeddings.

**CRITICAL — how the codebase works:**
- All configuration lives in `src/config.py` via Pydantic `Settings`. Always use `settings.x` not `os.getenv("X")`.
- Tests in `tests/` — 108 pass on main. Do not break them.
- Lint with `ruff check src/` — must be clean before PR.
- Mark any test that calls a live API with `@pytest.mark.expensive` — these are excluded from CI.
- MeetingBank data: `data/meetingbank/` contains 30 downloaded JSON files. NOT yet loaded into Supabase (that's Issue #26 — separate manual task).
- The evaluation framework uses Claude-as-judge (faithfulness, answer relevancy, context precision). It does NOT use RAGAS or DeepEval libraries — the README incorrectly claims this and it needs correcting.

**What PR #27 already fixed:**
- SDK clients use `settings.x` (core flow now works end-to-end)
- UI field names fixed (Issue #24 closed)
- Manually verified: upload → query → answer with citations ✅

---

## Your mission

Fix the evaluation runner so it runs as a Python module, add real test fixtures, and improve test coverage. Do not touch API routes, UI, or retrieval code.

---

## Issue #23 — Evaluation runner has no entry point

**What happens:** `python -m src.evaluation.runner` fails because `runner.py` has no `if __name__ == "__main__":` block. The README claims "Run `python -m src.evaluation.runner`" but this doesn't work.

**Also:** The README (root `README.md`) says "RAGAS + DeepEval metrics" in the Evaluation section. The actual implementation is Claude-as-judge. Fix the README wording.

**Where to look:** `src/evaluation/runner.py`

**What to add:**
- An `if __name__ == "__main__":` block with argparse
- Minimum args: `--meetings` (list of meeting IDs to evaluate), `--output` (output file path, default `reports/eval_results.json`), `--strategies` (which strategy combos to run)
- The block should call the existing runner functions — don't rewrite the evaluation logic, just wire up the entry point

---

## Issue #33 — Improve test coverage with real fixtures

**Current state:** The only test fixture is `tests/fixtures/sample.vtt` — a handful of speaker turns. All 108 tests use this or mocks. No test touches real MeetingBank data or runs the pipeline against a real transcript.

**What to add:**

### 1. Real MeetingBank fixture

Add a real MeetingBank transcript to `tests/fixtures/meetingbank/`. Use one of the 30 files already in `data/meetingbank/`. Pick a short one. Copy or symlink it to `tests/fixtures/meetingbank/sample_council_meeting.json`.

The MeetingBank JSON format has these fields: `{"meeting_id": "...", "transcription": [...], "summary": "..."}`. Each transcription item has `speaker_id`, `start_time`, `end_time`, `text`.

### 2. Parser test with real data

In `tests/test_ingestion.py`, add:
```python
def test_meetingbank_json_parser_with_real_fixture():
    """Parser correctly handles real MeetingBank JSON format."""
```
Assert: speaker labels populated, timestamps present, content non-empty, reasonable chunk count.

### 3. Integration test skeleton (expensive)

Create `tests/test_pipeline_integration.py`:
```python
import pytest

@pytest.mark.expensive
def test_full_ingest_and_query_pipeline():
    """Full pipeline: ingest transcript → store in Supabase → query → get answer.

    Requires: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY
    Run with: pytest -m expensive tests/test_pipeline_integration.py -v
    """
    # Implementation goes here
```

This test should be complete and correct even though it won't run in CI. It's the "golden path" test — if it passes, the system works end-to-end. Write it properly.

---

## TDD approach — MANDATORY

Write failing tests FIRST. Do not touch implementation until tests exist and fail.

### Step 1: Write failing tests

**Test A — runner entry point:**
```python
# In tests/test_evaluation.py
import subprocess, sys

def test_runner_callable_as_module():
    """python -m src.evaluation.runner --help must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "src.evaluation.runner", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Runner --help failed: {result.stderr}"
```

**Test B — real fixture parsing:**
```python
def test_meetingbank_json_parser_with_real_fixture():
    # Will fail until fixture is added
```

### Step 2: Confirm they fail (red)

```bash
pytest tests/test_evaluation.py::test_runner_callable_as_module -v
```

### Step 3: Fix the code

1. Add `__main__` block to `src/evaluation/runner.py`
2. Add `tests/fixtures/meetingbank/sample_council_meeting.json` (copy from `data/meetingbank/`)
3. Add the real fixture tests

### Step 4: Confirm they pass (green)

```bash
pytest tests/ -x
```

### Step 5: Full regression check

```bash
pytest tests/ -x
ruff check src/
```

---

## README fix

In `README.md` (root), find the Evaluation section. It currently says:

> RAGAS + DeepEval metrics — Faithfulness, answer relevancy, context precision/recall measured systematically.

Change to:

> Claude-as-judge evaluation — Faithfulness, answer relevancy, and context precision/recall assessed using Claude as the evaluator, with interpretable per-question reasoning. (RAGAS/DeepEval libraries are not used; the evaluation logic is explicit Python code.)

---

## If you cannot test something

Add a comment:
```python
# MANUAL TEST REQUIRED: [describe exact steps]
```

For the expensive integration tests: write them fully even though they can't run in CI. Add a comment block at the top of `test_pipeline_integration.py`:
```
# MANUAL RUN REQUIRED: These tests require live API keys.
# Run manually with: pytest -m expensive tests/test_pipeline_integration.py -v
# Ensure .env has OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY set.
```

---

## Files to touch

| File | Why |
|------|-----|
| `src/evaluation/runner.py` | Add `__main__` entry point |
| `README.md` | Fix RAGAS/DeepEval → Claude-as-judge |
| `tests/test_evaluation.py` | Add runner entry point test |
| `tests/test_ingestion.py` | Add real fixture parser test |
| `tests/test_pipeline_integration.py` | New file — expensive integration tests |
| `tests/fixtures/meetingbank/sample_council_meeting.json` | New fixture |

**Do not touch:** `src/api/`, `src/retrieval/`, `src/ui/`, `src/config.py`

---

## Definition of done

- [ ] `python -m src.evaluation.runner --help` exits 0
- [ ] `pytest tests/ -x` (excluding expensive) — all pass
- [ ] `ruff check src/` — clean
- [ ] `README.md` no longer claims RAGAS/DeepEval for the implemented metrics
- [ ] At least one real MeetingBank transcript in `tests/fixtures/meetingbank/`
- [ ] `test_pipeline_integration.py` exists with a proper `@pytest.mark.expensive` golden path test
- [ ] PR description includes "Manual verification needed" steps for the integration tests

---

## How to raise the PR

```bash
git add src/evaluation/runner.py README.md tests/
git commit -m "fix: add eval runner __main__ entry point, real fixtures, integration test skeleton"
gh pr create --title "fix: evaluation runner entry point + test coverage improvements (#23, #33)" --body "..."
```

Close issues: "Closes #23, Closes #33"
