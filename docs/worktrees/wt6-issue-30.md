# Worktree WT6 — Issue #30
**Branch:** `fix/30-mypy-errors`
**Created from:** main @ 75209d7
**Worktree path:** `C:\meeting-intelligence-wt6-issue-30`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend, Supabase (pgvector) for vector + metadata storage, Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config lives in `src/config.py` via Pydantic `Settings`. Always use `settings.x` not `os.getenv("X")`.
- mypy is run in strict mode: `mypy src/ --strict` (see `pyproject.toml`)
- Ruff is the linter/formatter. Run `ruff check src/ tests/` before any commit.
- There are currently **0 ruff errors** on main. Do not introduce any.
- Pre-existing mypy errors: **218 across 15 files** (that is your whole mission).

**What is already working and must stay working:**
- All 113 unit tests pass. Do not break them (`pytest tests/ -m "not expensive"`).
- Functional behaviour must not change — this is type annotations only.

---

## Your mission

Fix all 218 mypy errors so `mypy src/` exits 0. No functional changes.

---

## Error categories (from Issue #30)

### Category 1 — Claude API union-attr (~150 errors)
**Files:** `src/retrieval/generation.py`, `src/evaluation/metrics.py`, `src/evaluation/generate_test_set.py`, `src/evaluation/cross_check.py`

**Problem:** Code does `response.content[0].text` but `content[0]` is a union of `TextBlock | ToolUseBlock`. mypy doesn't know it has `.text`.

**Fix pattern:**
```python
from anthropic.types import TextBlock

block = response.content[0]
if isinstance(block, TextBlock):
    text = block.text
else:
    raise ValueError(f"Unexpected content block type: {type(block)}")
```

Or with a helper (if used in 3+ places):
```python
def _text_from_response(response) -> str:
    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise TypeError(f"Expected TextBlock, got {type(block)}")
    return block.text
```

### Category 2 — Supabase JSON return type (~50 errors)
**Files:** `src/api/routes/meetings.py`, `src/ingestion/storage.py`, `src/retrieval/search.py`, `src/api/routes/extraction.py`

**Problem:** `client.table("x").select("*").execute().data` returns `list[Any]`. mypy complains when you treat items as dicts with known keys.

**Fix pattern:**
```python
from typing import Any, cast

rows = cast(list[dict[str, Any]], result.data)
```

Or annotate the variable explicitly:
```python
data: list[dict[str, Any]] = result.data or []
```

### Category 3 — Bare dict without type params (~15 errors)
**Problem:** `def foo() -> dict:` or `x: dict = {}`.

**Fix:** Always use `dict[str, Any]` or a more specific type like `dict[str, str]`.

### Category 4 — Misc (~3 errors)
- `src/api/main.py:21` — missing return type annotation on `health()` function. Add `-> dict[str, str]`.
- `src/ingestion/parsers.py:166` — `no-any-return`. The function returns `Any` but is annotated with a concrete type. Either broaden the return type or narrow the value.
- `src/extraction/extractor.py:128` — `call-overload` mismatch. Check what the Anthropic `client.messages.create()` overload expects for `tool_choice`.

---

## Approach

Work file by file. Suggested order (most errors first):

**1.** `src/retrieval/generation.py`
**2.** `src/evaluation/metrics.py`
**3.** `src/evaluation/generate_test_set.py`
**4.** `src/evaluation/cross_check.py`
**5.** `src/ingestion/storage.py`
**6.** `src/retrieval/search.py`
**7.** `src/api/routes/meetings.py`
**8.** `src/api/routes/extraction.py`
**9.** `src/api/main.py`
**10.** `src/ingestion/parsers.py`
**11.** `src/extraction/extractor.py`

After each file: `mypy src/<file> --strict` to confirm it goes to 0 for that file.

---

## No new tests needed

This is type annotation work only. The existing test suite is the regression check.

After all files are fixed:
```bash
mypy src/                         # must exit 0
pytest tests/ -m "not expensive"  # must all pass
ruff check src/ tests/            # must be clean
```

---

## Definition of done

- [ ] `mypy src/` exits 0 (zero errors)
- [ ] `pytest tests/ -m "not expensive"` — all pass, no regressions
- [ ] `ruff check src/ tests/` — clean
- [ ] No functional behaviour changes (type annotations and casts only)

---

## How to raise the PR

```bash
git add src/
git commit -m "fix: resolve 218 mypy type errors across src/ (Issue #30)"
gh pr create \
  --title "fix: resolve 218 mypy errors — CI lint now fully green (#30)" \
  --body "Closes #30

## What changed
Type annotations and casts only — no functional behaviour changes.

**Category 1 (~150 errors):** Claude API content blocks — added isinstance(block, TextBlock) guards in generation.py, metrics.py, generate_test_set.py, cross_check.py.

**Category 2 (~50 errors):** Supabase .data return type — cast to list[dict[str, Any]] in storage.py, search.py, meetings.py, extraction.py.

**Category 3 (~15 errors):** Bare dict → dict[str, Any] throughout.

**Category 4 (3 errors):** Missing return annotation, no-any-return, call-overload mismatch.

## Test plan
- \`mypy src/\` exits 0
- \`pytest tests/ -m 'not expensive'\` all pass
- \`ruff check src/ tests/\` clean"
```
