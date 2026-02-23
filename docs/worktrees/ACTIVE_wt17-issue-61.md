# Worktree WT17 — Issue #61
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt17-issue-61`
**Branch:** `feat/61-image-summary`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. Use `settings.x` not `os.getenv("X")`.
- `settings.google_api_key` maps to env var `GOOGLE_API_KEY` — already present in `.env`.
- `google-generativeai` package already in `pyproject.toml` — no new dependency needed.
- Meetings route: `src/api/routes/meetings.py` — `GET /api/meetings`, `GET /api/meetings/{id}`.
- Models: `src/api/models.py`.
- API registered in `src/api/main.py` — add your new router there.
- Frontend nav: `frontend/components/nav.tsx`.
- Frontend meeting detail: `frontend/app/meetings/page.tsx` — this is where the button goes.
- All tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8170 make api`
- mypy is passing — run `ruff check src/ tests/` AND `mypy src/` before PR.

---

## Your mission

Add a **"Generate Visual Summary"** button to the meeting detail view. When clicked, it calls a new backend endpoint which uses **Nano Banana Pro** (`gemini-3-pro-image-preview`) to generate an image summarising the meeting. The image is displayed inline. This is manually triggered — never auto-generated on upload. Not a batch operation.

---

## Implementation

### Step 1 — New backend route: `src/api/routes/image_summary.py`

Create this file:

```python
"""Image summary endpoint — calls Gemini 3 Pro Image (Nano Banana Pro) to generate a meeting visual."""
from __future__ import annotations

import base64
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.ingestion.storage import get_supabase_client

router = APIRouter()


class ImageSummaryResponse(BaseModel):
    meeting_id: str
    image_data: str   # base64-encoded PNG
    mime_type: str


@router.post("/api/meetings/{meeting_id}/image-summary", response_model=ImageSummaryResponse)
async def image_summary(meeting_id: str) -> ImageSummaryResponse:
    """Generate a visual summary image of a meeting using Nano Banana Pro."""
    if not settings.google_api_key:
        raise HTTPException(
            status_code=501,
            detail="Image summary requires GOOGLE_API_KEY — not configured.",
        )

    client = get_supabase_client()
    result = client.table("meetings").select("raw_transcript, title").eq("id", meeting_id).execute()
    rows = cast(list[dict[str, Any]], result.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = rows[0].get("raw_transcript", "")
    title = rows[0].get("title", "Meeting")
    if not transcript:
        raise HTTPException(status_code=400, detail="Meeting has no transcript")

    import google.generativeai as genai  # type: ignore[import]

    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-3-pro-image-preview")

    prompt = f"""Create a visual summary infographic for a meeting titled "{title}".
Include: speaker names and their participation level, key decisions made,
main topics discussed in order, and any action items.
Use a clean, professional style with clear sections, icons, and labels.
Make it visually engaging and easy to read at a glance.

Transcript:
{transcript[:8000]}"""

    response = model.generate_content(
        [prompt],
        generation_config={"response_modalities": ["IMAGE", "TEXT"]},
    )

    for part in response.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            mime_type = part.inline_data.mime_type or "image/png"
            # SDK may return bytes or base64 string — normalise to base64 string
            if isinstance(image_bytes, bytes):
                b64 = base64.b64encode(image_bytes).decode("utf-8")
            else:
                b64 = image_bytes  # already base64
            return ImageSummaryResponse(
                meeting_id=meeting_id,
                image_data=b64,
                mime_type=mime_type,
            )

    raise HTTPException(status_code=502, detail="Gemini did not return an image.")
```

### Step 2 — Register in `src/api/main.py`

Read `main.py` first. Add:
```python
from src.api.routes.image_summary import router as image_summary_router
# ...
app.include_router(image_summary_router)
```

### Step 3 — Check `src/config.py`

Read it. Confirm `google_api_key` field exists mapped to `GOOGLE_API_KEY`. If it doesn't exist, add:
```python
google_api_key: str | None = None
```

### Step 4 — Frontend: `frontend/lib/api.ts`

Read the file first. Add a helper:
```typescript
imageSummary: async (meetingId: string): Promise<{ image_data: string; mime_type: string } | null> => {
  const res = await fetch(`${API_URL}/api/meetings/${meetingId}/image-summary`, { method: 'POST' })
  if (!res.ok) return null
  return res.json()
},
```

### Step 5 — Frontend: `frontend/app/meetings/page.tsx`

Read the full file first (it is large — wt13 added chunk viewer here already, so read carefully).

Add to the `MeetingDetailPanel` component (or wherever the detail panel renders):

**State:**
```typescript
const [imageSummary, setImageSummary] = useState<{ image_data: string; mime_type: string } | null>(null)
const [imageLoading, setImageLoading] = useState(false)
const [imageError, setImageError] = useState<string | null>(null)
```

**Handler:**
```typescript
const handleGenerateImage = async () => {
  if (!detail) return
  setImageLoading(true)
  setImageError(null)
  try {
    const result = await api.imageSummary(detail.id)
    if (result) setImageSummary(result)
    else setImageError('Failed to generate image.')
  } catch {
    setImageError('Failed to generate image.')
  } finally {
    setImageLoading(false)
  }
}
```

**Button + image render** (add below extracted items / chunk viewer, before closing panel):
```tsx
<div className="mt-4">
  <Button
    onClick={handleGenerateImage}
    disabled={imageLoading || !detail.raw_transcript}
    variant="outline"
    size="sm"
  >
    {imageLoading ? 'Generating…' : 'Generate Visual Summary'}
  </Button>
  {imageError && <p className="text-destructive text-xs mt-2">{imageError}</p>}
  {imageSummary && (
    <div className="mt-3">
      <img
        src={`data:${imageSummary.mime_type};base64,${imageSummary.image_data}`}
        alt="Visual meeting summary"
        className="rounded-lg border w-full"
      />
    </div>
  )}
</div>
```

---

## Testing

### Backend (automated)
```bash
python -m pytest tests/ -m "not expensive" -q
ruff check src/ tests/
mypy src/
```

Add a test:
```python
def test_image_summary_no_api_key(client: TestClient) -> None:
    """Returns 501 when GOOGLE_API_KEY is not set."""
    import unittest.mock
    with unittest.mock.patch("src.api.routes.image_summary.settings") as mock_settings:
        mock_settings.google_api_key = None
        response = client.post("/api/meetings/12345678-1234-1234-1234-123456789abc/image-summary")
    assert response.status_code == 501
```

### Frontend (visual)
`npm run build` — TypeScript must compile cleanly.

---

## Definition of done

- [ ] `POST /api/meetings/{id}/image-summary` returns base64 image
- [ ] Returns 501 gracefully if `GOOGLE_API_KEY` not set
- [ ] Button in meeting detail view — disabled if no transcript
- [ ] Click → spinner → image rendered inline
- [ ] Error state on failure
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check` + `mypy src/` — clean
- [ ] `npm run build` — clean

---

## Port allocation
- API: `PORT=8170 make api`
- Frontend: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8170 npm run dev -- --turbo`
