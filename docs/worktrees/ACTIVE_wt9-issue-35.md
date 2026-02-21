# Worktree WT9 — Issue #35
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt9-issue-35`
**Branch:** `feat/35-gemini-visual-summary`
**Created from:** main @ 75209d7
**Worktree path:** `C:\meeting-intelligence-wt9-issue-35`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`/frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. `GEMINI_API_KEY` is already in `Settings` and `.env.example` — use `settings.gemini_api_key`.
- API routes: `src/api/routes/`. Add new files here.
- Frontend pages: `frontend/app/`. The Upload page is `frontend/app/page.tsx`.
- The frontend calls `NEXT_PUBLIC_API_URL` (from `.env.local`) for all API calls. API helpers live in `frontend/lib/api.ts`.
- CORS is configured for `localhost:3000` and `*.vercel.app` — new endpoints are covered automatically.
- All 113 tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8090 make api` and `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8090 npm run dev`
- Do not run `mypy` — pre-existing errors being fixed in wt6. Run `ruff check src/ tests/` only.

---

## Your mission

Add a `POST /api/meetings/{id}/visual-summary` endpoint that calls Gemini to generate a structured visual summary of a meeting transcript.

The frontend Upload page should call this immediately after ingest completes, showing it alongside the existing extracted items.

---

## Backend: New endpoint

### Create `src/api/routes/visual_summary.py`

```python
"""Visual summary endpoint — calls Gemini for speaker/topic/timeline breakdown."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.models import ...  # import as needed
from src.config import settings
from src.ingestion.storage import get_supabase_client

router = APIRouter()


class VisualSummaryResponse(BaseModel):
    meeting_id: str
    speaker_breakdown: list[dict]   # [{speaker, utterance_count, percentage}]
    topic_timeline: list[dict]      # [{timestamp, topic}]
    key_moments: list[dict]         # [{timestamp, description}]
    word_count: int
    duration_seconds: int | None


@router.post("/api/meetings/{meeting_id}/visual-summary", response_model=VisualSummaryResponse)
async def visual_summary(meeting_id: str) -> VisualSummaryResponse:
    ...
```

### Gemini call

Use `google-generativeai` SDK (check if it's in `requirements.txt` — add if not):

```python
import google.generativeai as genai

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

prompt = f"""Analyse this meeting transcript and return a JSON object with:
- speaker_breakdown: list of {{speaker, utterance_count, percentage}}
- topic_timeline: list of {{timestamp, topic}} (approximate timestamps)
- key_moments: list of {{timestamp, description}} (max 5 most important moments)
- word_count: total word count
- duration_seconds: estimated duration in seconds (null if unknown)

Transcript:
{transcript}

Return only valid JSON, no markdown."""

response = model.generate_content(prompt)
import json
data = json.loads(response.text)
```

### Graceful degradation if no Gemini key

```python
if not settings.gemini_api_key:
    raise HTTPException(
        status_code=501,
        detail="Visual summary requires GEMINI_API_KEY — not configured."
    )
```

### Register the router

In `src/api/main.py`, add:
```python
from src.api.routes.visual_summary import router as visual_summary_router
app.include_router(visual_summary_router)
```

---

## Frontend: Update Upload page

In `frontend/lib/api.ts`, add:
```typescript
export async function getVisualSummary(meetingId: string) {
  const res = await fetch(`${API_URL}/api/meetings/${meetingId}/visual-summary`, {
    method: 'POST',
  })
  if (!res.ok) return null  // graceful degradation if 501
  return res.json()
}
```

In `frontend/app/page.tsx`, after ingest + extract succeeds:
```typescript
const visual = await getVisualSummary(meetingId)
if (visual) {
  // render speaker_breakdown as a simple list or table
  // render key_moments
}
```

Keep it simple — a clean card with speaker percentages and key moments is enough. No charts library needed.

---

## Testing

### Unit test (mock Gemini)

In `tests/test_api.py`, add:

```python
from unittest.mock import patch, MagicMock

def test_visual_summary_returns_501_without_key(client):
    """If GEMINI_API_KEY is not set, visual summary returns 501."""
    with patch("src.config.settings.gemini_api_key", None):
        response = client.post("/meetings/fake-id/visual-summary")
    assert response.status_code in (404, 501)  # 404 if meeting not found, 501 if key check is first
```

For the full happy-path test with a real key, mark `@pytest.mark.expensive`.

---

## .env.example

Verify `GEMINI_API_KEY=` is already in `.env.example` (it was added previously). If not, add it.

---

## Definition of done

- [ ] `POST /api/meetings/{id}/visual-summary` returns structured JSON
- [ ] Returns 501 if `GEMINI_API_KEY` not set (graceful degradation)
- [ ] Router registered in `src/api/main.py`
- [ ] `google-generativeai` in `requirements.txt` (if not already)
- [ ] Frontend Upload page shows visual summary after ingest (or silently skips if 501)
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check src/ tests/` — clean

---

## How to raise the PR

```bash
git add src/api/routes/visual_summary.py src/api/main.py \
        frontend/lib/api.ts frontend/app/page.tsx \
        requirements.txt tests/test_api.py
git commit -m "feat: Gemini visual summary endpoint + frontend integration (#35)"
gh pr create \
  --title "feat: upload-time visual summary via Gemini (#35)" \
  --body "Closes #35

## What this adds
- POST /api/meetings/{id}/visual-summary — calls Gemini 1.5 Flash to return speaker breakdown, topic timeline, key moments
- Graceful 501 if GEMINI_API_KEY not set
- Frontend Upload page shows visual summary card after ingest completes

## Test plan
- test_visual_summary_returns_501_without_key passes
- pytest tests/ -m 'not expensive' all pass
- Manual: set GEMINI_API_KEY, upload a transcript, verify visual summary card appears"
```
