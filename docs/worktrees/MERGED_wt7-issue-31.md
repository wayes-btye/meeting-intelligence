# Worktree WT7 — Issue #31
**Status:** `MERGED` — PR #50/#51 merged 2026-02-21, Cloud Run live, worktree removed
**Branch:** `feat/31-cloud-run`
**Created from:** main @ 75209d7
**Worktree path:** `C:\meeting-intelligence-wt7-issue-31`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`/frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. On Cloud Run, secrets are injected as env vars — Pydantic reads them automatically.
- The FastAPI app entry point is `src/api/main.py`. `uvicorn src.api.main:app` is the command.
- Health check endpoint: `GET /health` → `{"status": "healthy"}` — this is what Cloud Run uses for readiness checks.
- Frontend (`/frontend/`) is a Next.js app. It reads `NEXT_PUBLIC_API_URL` from `.env.local` — for Vercel this becomes a Vercel environment variable.
- CORS is already configured in `src/api/main.py` — it allows `localhost:3000` and any `*.vercel.app` origin.
- Run `ruff check src/ tests/` only (do not run mypy).

**Port for this worktree:** `PORT=8070 make api`

---

## How deployment actually works (updated after research)

### Cloud Run — UI-based Continuous Deployment (no GitHub Actions needed)

Cloud Run's "Continuous Deployment" feature creates a **Cloud Build trigger** on GCP's side when you connect a GitHub repo via the Console UI. **No `.github/workflows/deploy.yml` file is needed.** Nothing is written to the GitHub repo — the pipeline lives entirely in GCP.

How it works:
1. In the Cloud Run Console, create a new service → "Continuously deploy from a source repository"
2. Authenticate GitHub via the Cloud Build GitHub App (OAuth flow)
3. Select repo + branch (`main`)
4. Choose "Dockerfile" build type, point to `Dockerfile` at repo root
5. Set env vars (API keys) in the service configuration
6. Cloud Run creates the Cloud Build trigger and deploys on every push to main

**Your job in this worktree: create the `Dockerfile` only.** The user connects the repo via the Cloud Run Console.

### Vercel — zero config needed

Vercel auto-detects Next.js. When importing the GitHub repo:
1. Set **Root Directory** to `frontend` in the dashboard
2. Vercel auto-detects Next.js, sets `next build` as build command, `.next` as output
3. Set `NEXT_PUBLIC_API_URL` to the Cloud Run URL as a Vercel environment variable

**No `vercel.json` is needed** for a standard Next.js app. Do not create one.

---

## Your mission (what to build)

Two files only:

**1. `Dockerfile` at the repo root**
**2. `README.md` updated with Live Demo section**

The GitHub Actions workflow and `vercel.json` are NOT needed.

---

## Step 1 — Dockerfile

Create `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Cloud Run injects $PORT; default to 8080 if not set
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
```

**Notes:**
- `python:3.11-slim` keeps the image lean
- Copy only `src/` and `requirements.txt` — no tests, no docs
- `${PORT}` respects whatever Cloud Run injects (it's always 8080 in practice)

---

## Step 2 — Update README

Update `README.md` to add a "Live Demo" section at the top (placeholder URLs — the user fills in real URLs after connecting Cloud Run):

```markdown
## Live Demo

- **API:** https://meeting-intelligence-api-XXXXX-ew.a.run.app
- **Frontend:** https://meeting-intelligence.vercel.app

Health check: `GET /health` → `{"status": "healthy"}`
```

---

## What the user does manually (not your job)

These are manual steps the user performs in their browser — **do not try to script these:**

### Cloud Run setup
1. Go to [Cloud Run Console](https://console.cloud.google.com/run) → Create Service
2. Choose "Continuously deploy from a source repository"
3. Connect GitHub repo via Cloud Build GitHub App (OAuth)
4. Select branch: `main`, build type: `Dockerfile`, Dockerfile path: `Dockerfile`
5. Set env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ASSEMBLYAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`
6. Allow unauthenticated invocations, region: `europe-west2` (or user's preference)

**Required IAM** (Cloud Build service account needs these roles):
- `roles/run.admin` (to deploy revisions)
- `roles/iam.serviceAccountUser`

### Vercel setup
1. Go to [vercel.com/new](https://vercel.com/new) → Import GitHub repo
2. Set **Root Directory** to `frontend`
3. Framework auto-detected as Next.js — no other settings needed
4. Add environment variable: `NEXT_PUBLIC_API_URL` = Cloud Run URL (from step above)
5. Deploy

---

## Testing the Dockerfile locally (optional)

```bash
# From worktree root
docker build -t meeting-intelligence-api .
docker run -p 8080:8080 \
  -e ANTHROPIC_API_KEY=... \
  -e OPENAI_API_KEY=... \
  -e SUPABASE_URL=... \
  -e SUPABASE_KEY=... \
  meeting-intelligence-api

curl http://localhost:8080/health
# → {"status":"healthy"}
```

---

## Definition of done

- [ ] `Dockerfile` at repo root builds cleanly (`docker build .` exits 0)
- [ ] `README.md` updated with placeholder Live Demo URLs
- [ ] `ruff check src/ tests/` clean
- [ ] No `vercel.json` created (not needed)
- [ ] No `.github/workflows/deploy.yml` created (Cloud Run UI handles this)

---

## How to raise the PR

```bash
git add Dockerfile README.md
git commit -m "feat: Dockerfile + README live demo section for Cloud Run deploy (#31)"
gh pr create \
  --title "feat: cloud deployment — Dockerfile for Cloud Run (#31)" \
  --body "Closes #31

## What this adds
- Dockerfile for FastAPI API (python:3.11-slim, \$PORT-aware)
- README.md — Live Demo section with placeholder URLs

## What the user connects manually
- Cloud Run: Continuous Deployment via Cloud Run Console UI (no GitHub Actions needed — Cloud Run creates Cloud Build trigger automatically)
- Vercel: Import repo, set Root Directory to \`frontend\`, add NEXT_PUBLIC_API_URL env var

## Test plan
- docker build . exits 0
- docker run with env vars → GET /health returns {status: healthy}"
```
