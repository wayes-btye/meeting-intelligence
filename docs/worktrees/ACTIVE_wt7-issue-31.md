# Worktree WT7 — Issue #31
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt7-issue-31`
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
- Do not run `make lint` — the mypy errors (Issue #30) are being fixed in a separate worktree (wt6). Run `ruff check src/ tests/` only.

**Port for this worktree:** `PORT=8070 make api`

---

## Your mission

Deploy the system to cloud so the assessor can run it without local setup.

**Scope:**
1. `Dockerfile` for the FastAPI API
2. GitHub Actions `deploy.yml` workflow (build + push to GCR + deploy to Cloud Run)
3. `vercel.json` for the frontend
4. README updated with live demo URLs

---

## Step 1 — Dockerfile

Create `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Notes:**
- Cloud Run listens on port 8080 by default (or whatever `PORT` env var Cloud Run injects — use `$PORT` if you want to be flexible)
- `python:3.11-slim` keeps the image lean
- Copy only `src/` and `requirements.txt` — no tests, no docs, no worktree files

---

## Step 2 — GitHub Actions deploy workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # for Workload Identity Federation (preferred) or use service account key

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Build and push Docker image
        run: |
          gcloud builds submit \
            --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/meeting-intelligence-api:${{ github.sha }} \
            --project ${{ secrets.GCP_PROJECT_ID }}

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy meeting-intelligence-api \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/meeting-intelligence-api:${{ github.sha }} \
            --platform managed \
            --region europe-west2 \
            --allow-unauthenticated \
            --port 8080 \
            --set-env-vars "ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }},OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }},ASSEMBLYAI_API_KEY=${{ secrets.ASSEMBLYAI_API_KEY }},SUPABASE_URL=${{ secrets.SUPABASE_URL }},SUPABASE_KEY=${{ secrets.SUPABASE_KEY }}" \
            --project ${{ secrets.GCP_PROJECT_ID }}
```

**Required GitHub Secrets (manual — see MANUAL-TASKS issue #39):**
- `GCP_SA_KEY` — service account JSON key with Cloud Run + Cloud Build + GCR roles
- `GCP_PROJECT_ID` — your GCP project ID
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ASSEMBLYAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`

---

## Step 3 — Vercel config

Create `frontend/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "framework": "nextjs",
  "env": {
    "NEXT_PUBLIC_API_URL": "@meeting-intelligence-api-url"
  }
}
```

`@meeting-intelligence-api-url` references a Vercel environment variable — set it to the Cloud Run URL in the Vercel dashboard after the Cloud Run deploy succeeds.

---

## Step 4 — Update README

Update `README.md` to add a "Live Demo" section at the top:

```markdown
## Live Demo

- **API:** https://meeting-intelligence-api-XXXXX-ew.a.run.app
- **Frontend:** https://meeting-intelligence.vercel.app

Health check: `GET /health` → `{"status": "healthy"}`
```

(Fill in the actual URLs after deploy.)

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

- [ ] `Dockerfile` builds cleanly (`docker build .` exits 0)
- [ ] `.github/workflows/deploy.yml` created (CI will validate YAML syntax)
- [ ] `frontend/vercel.json` created
- [ ] `README.md` updated with placeholder demo URLs
- [ ] `ruff check src/ tests/` clean (do not run mypy — pre-existing errors in wt6)

---

## How to raise the PR

```bash
git add Dockerfile .github/workflows/deploy.yml frontend/vercel.json README.md
git commit -m "feat: Cloud Run deployment — Dockerfile, GitHub Actions deploy.yml, Vercel config (#31)"
gh pr create \
  --title "feat: cloud deployment — Cloud Run API + Vercel frontend (#31)" \
  --body "Closes #31

## What this adds
- Dockerfile for FastAPI API (python:3.11-slim, port 8080)
- .github/workflows/deploy.yml — builds/pushes to GCR, deploys to Cloud Run on push to main
- frontend/vercel.json — Vercel build config
- README.md — live demo URLs (placeholder until GCP project is set up)

## Manual steps required before deploy works
See Issue #39 MANUAL-TASKS for GCP project setup, service account, and GitHub Secrets.

## Test plan
- docker build . exits 0
- Workflow YAML validates (CI lint)
- Health check at /health returns 200 after deploy"
```
