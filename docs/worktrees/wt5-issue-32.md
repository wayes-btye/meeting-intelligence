# Worktree WT5 — Issue #32
**Branch:** `feat/32-react-frontend`
**Created from:** main @ 771203b

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend (port 8000), Streamlit frontend (port 8501 — keep it, it's the dev tool), Supabase pgvector for storage, Claude for generation.

**CRITICAL — the FastAPI API is the source of truth.** The React frontend is a pure HTTP client. Zero backend logic lives in the frontend. Every action the frontend takes is an API call to FastAPI.

**What PR #27 confirmed is working end-to-end:**
- `POST /ingest` — upload transcript, returns `{meeting_id, chunks_created}`
- `POST /query` — ask a question, returns `{answer, sources: [{speaker, content, similarity, start_time}]}`
- `GET /meetings` — list meetings, returns `[{id, title, created_at, chunk_count, speaker_count}]`
- `GET /meetings/{id}` — meeting detail, returns `{id, title, created_at, chunks, extracted_items}`
- `POST /meetings/{id}/extract` — run structured extraction, returns `{action_items, decisions, topics}`
- `GET /health` — returns `{"status": "healthy"}`

**Strategy toggle:** The query endpoint accepts `chunking_strategy` (`"naive"` or `"speaker_turn"`) and `retrieval_strategy` (`"semantic"` or `"hybrid"`) in the request body.

**Supabase project:** `qjmswgbkctaazcyhinew` (for reference — frontend talks to FastAPI, not Supabase directly)

---

## Your mission

Build a React/Next.js frontend in `/frontend/`. Streamlit stays — this is additive, not a replacement. The frontend is what the assessor will see in the demo. It needs to look professional and work reliably.

---

## Tech stack

- **Framework:** Next.js 14 (App Router)
- **UI components:** shadcn/ui (https://ui.shadcn.com/) — pre-built accessible components, consistent design
- **Styling:** Tailwind CSS (comes with shadcn)
- **HTTP client:** native `fetch` or `axios`
- **Package manager:** npm

**Why this stack:** Next.js deploys to Vercel with zero configuration. shadcn gives a polished default appearance with minimal CSS work. The assessor will see a modern, professional UI.

---

## Pages to build

### 1. Upload Page (`/`)
- Drag-and-drop file upload (accepts `.vtt`, `.txt`, `.json`)
- Meeting title input field
- Strategy selector: chunking (naive / speaker_turn) and retrieval (semantic / hybrid) — show as radio buttons or a dropdown
- On submit: `POST /ingest`
- While ingesting: progress indicator ("Processing transcript...")
- On success: immediately show extraction results (action items, decisions, topics) — call `POST /meetings/{id}/extract` automatically after ingest
- Show: chunks created count, processing strategy used

### 2. Chat Page (`/chat` or tab on upload page)
- Meeting selector dropdown (populated from `GET /meetings`)
- Free-text question input
- Submit button
- Answer display area with formatted text
- Source citations panel: expandable cards showing `speaker`, `content`, `start_time`, `similarity` score
- Strategy selector (same as upload page — which strategy to use for retrieval)
- Query is filtered to the selected meeting OR unfiltered (across all meetings)

### 3. Meetings Browser (`/meetings`)
- Paginated list of meetings (from `GET /meetings`)
- Each row: title, date, chunk count, speaker count
- Click row → meeting detail view
- Detail view: metadata + list of extracted action items / decisions / topics (from `GET /meetings/{id}`)
- Each action item shows: `content`, `assignee`, `due_date` if present

### 4. Layout
- Sidebar or top navigation between Upload, Chat, Meetings
- App title: "Meeting Intelligence"
- Status indicator: shows whether the API is reachable (GET /health)

---

## Backend change needed (minimal)

In `src/api/main.py`, add CORS middleware. The frontend on localhost:3000 (dev) and Vercel (prod) needs to be able to call the API.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This is the ONLY change to `src/`. Do not touch anything else in the backend.

---

## Environment variables for the frontend

Create `/frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For Vercel deployment, `NEXT_PUBLIC_API_URL` will be the Cloud Run API URL (e.g., `https://meeting-intelligence-api-xxxx.run.app`).

Create `/frontend/.env.example`:
```
# FastAPI backend URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Vercel deployment (to be done manually by user after this PR merges)

1. Push branch to GitHub
2. Go to vercel.com → New Project → Import from GitHub
3. Set Root Directory to `frontend`
4. Add environment variable: `NEXT_PUBLIC_API_URL=<Cloud Run API URL>`
5. Deploy

The Cloud Run API must be deployed first (Issue #31) before the Vercel frontend can point at it. For the demo, if Cloud Run isn't ready yet, point `NEXT_PUBLIC_API_URL` at `http://localhost:8000` and run locally.

**Note on CORS:** Once the Vercel URL is known (e.g., `https://meeting-intelligence.vercel.app`), add it to the `allow_origins` list in `src/api/main.py` and redeploy the API.

---

## Testing approach (frontend)

Unit tests don't apply here. Use Playwright for end-to-end UI tests.

### Step 1: Write Playwright spec files BEFORE building each page

Create `frontend/e2e/` directory with:
- `upload.spec.ts` — upload a file, assert extraction results appear
- `chat.spec.ts` — select a meeting, ask a question, assert answer and sources appear
- `meetings.spec.ts` — assert list renders, click row, assert detail view shows

### Step 2: Run Playwright — confirm tests fail (red)

Pages don't exist yet. Tests should fail.

### Step 3: Build pages

### Step 4: Run Playwright — confirm tests pass (green)

### Step 5: Take screenshots using Playwright for the PR

Use Playwright to capture screenshots of:
- Upload page (before and after upload)
- Chat page with an answer visible
- Meetings browser
- Meeting detail view

Include all screenshots in the PR description.

---

## If you cannot run Playwright tests

Add at the top of each spec file:
```typescript
// MANUAL VISUAL CHECK REQUIRED:
// 1. Start API: make api (from main repo root, not frontend)
// 2. Start frontend: npm run dev
// 3. Visit http://localhost:3000
// 4. [specific thing to verify on this page]
```

**The user will do manual visual verification before merging.** Make it explicit exactly what to check.

---

## If the API is not running

The frontend should handle this gracefully — show a "⚠️ API not reachable" indicator rather than crashing. The health check (`GET /health`) should be polled on load.

---

## Files to touch

| File/Dir | Why |
|----------|-----|
| `/frontend/` | New Next.js app — all new code |
| `src/api/main.py` | Add CORS middleware only |
| `/frontend/.env.example` | Document NEXT_PUBLIC_API_URL |

**Do not touch:** Any other file in `src/`, tests, docs (except if adding a deployment note).

---

## Definition of done

- [ ] `cd frontend && npm run build` passes with no errors
- [ ] All three pages render without console errors
- [ ] Upload → extraction results visible in the UI
- [ ] Ask a question → answer with sources displayed
- [ ] Meetings list → click → detail view shows action items
- [ ] Strategy toggle sends correct params in the request body
- [ ] `GET /health` failure handled gracefully (error indicator in UI)
- [ ] `/frontend/.env.example` documented
- [ ] PR includes screenshots of every page
- [ ] PR includes "Manual verification needed" section with exact steps for the user

---

## How to raise the PR

```bash
git add frontend/ src/api/main.py
git commit -m "feat: React/Next.js frontend with upload, chat, and meetings pages (#32)"
gh pr create --title "feat: React/Next.js frontend replacing Streamlit as demo UI (#32)" --body "..."
```

Close issue: "Closes #32"

Include screenshots directly in the PR body using GitHub image paste (drag image into the PR description text box).
