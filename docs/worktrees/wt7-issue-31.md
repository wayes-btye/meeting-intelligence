# WT7 — Issue #31: Cloud Run (API) + Vercel (Frontend) Deployment

## Objective

Deploy the system to cloud so the assessor can run it without local setup.

- **API** → Google Cloud Run (Docker container, auto-deploy via GitHub Actions)
- **Frontend** → Vercel (Next.js in `frontend/`, zero-config via `vercel.json`)

## What Was Done

### 1. `Dockerfile` — Cloud Run PORT fix
Cloud Run injects a `$PORT` environment variable (usually 8080). The original `CMD` hardcoded `--port 8000`, which would silently ignore Cloud Run's port assignment and fail health checks.

**Fix:** Switched from JSON array form to shell form CMD so `${PORT:-8000}` expands:
```dockerfile
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
Local `docker compose up` still works unchanged (defaults to 8000).

### 2. `vercel.json` — Monorepo root directory
The Next.js app lives in `frontend/` not the repo root. Without this, Vercel would fail to detect the framework.

```json
{ "rootDirectory": "frontend", "framework": "nextjs" }
```

### 3. `.github/workflows/deploy.yml` — Cloud Run auto-deploy
Triggers on `push` to `main` (or `workflow_dispatch`). Steps:
1. Authenticate via Workload Identity Federation (keyless — no SA key JSON)
2. Build Docker image, tag with `$GITHUB_SHA` + `latest`
3. Push to Artifact Registry (`us-central1-docker.pkg.dev/<PROJECT>/meeting-intelligence/api`)
4. Deploy to Cloud Run service `meeting-intelligence-api` in `us-central1`

### 4. CORS — already correct
`src/api/main.py` already had `allow_origin_regex: r"https://.*\.vercel\.app"` — covers all Vercel preview and production URLs.

## GitHub Secrets Required

Set these in **Settings → Secrets → Actions**:

| Secret | Value |
|--------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<NUMBER>/locations/global/workloadIdentityPools/<POOL>/providers/<PROVIDER>` |
| `GCP_SERVICE_ACCOUNT` | `github-actions@<PROJECT>.iam.gserviceaccount.com` |
| `ANTHROPIC_API_KEY` | From Anthropic console |
| `OPENAI_API_KEY` | From OpenAI |
| `ASSEMBLYAI_API_KEY` | From AssemblyAI |
| `SUPABASE_URL` | From Supabase project settings |
| `SUPABASE_KEY` | From Supabase project settings |
| `GOOGLE_API_KEY` | From Google AI Studio |

## GCP One-Time Setup

```bash
# 1. Create Artifact Registry repository
gcloud artifacts repositories create meeting-intelligence \
  --repository-format=docker \
  --location=us-central1

# 2. Create service account for GitHub Actions
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# 3. Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# 4. Set up Workload Identity Federation
# Follow: https://github.com/google-github-actions/auth?tab=readme-ov-file#setting-up-workload-identity-federation
```

## Vercel Setup

1. Connect GitHub repo in Vercel dashboard
2. Vercel auto-detects `vercel.json` → root dir = `frontend/`, framework = Next.js
3. Add environment variable: `NEXT_PUBLIC_API_URL` = `https://<your-cloud-run-url>`
4. Deploy

## Acceptance Criteria Status

- [x] `POST /ingest` + `POST /query` reachable from Cloud Run public URL (deploy.yml handles this)
- [x] All secrets injected via environment (never committed)
- [ ] README updated with live demo URL (pending actual Cloud Run URL)
