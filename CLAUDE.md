# CLAUDE.md — Meeting Intelligence

## Stack
- **Language:** Python 3.11+
- **Backend:** FastAPI (API server)
- **Primary UI:** React/Next.js 14 (`frontend/`) — production frontend, deployed to Vercel
- **Dev UI:** Streamlit (`src/ui/`) — lightweight secondary UI, maintained for dev/experimentation
- **API Explorer:** FastAPI Swagger at `/docs`, ReDoc at `/redoc` — always available when API is running
- **Database:** Supabase (Postgres + pgvector for vectors, metadata, structured data)
- **LLM:** Claude API (direct SDK calls — no LangChain/LlamaIndex)
- **Embeddings:** OpenAI text-embedding-3-small (1536 dimensions)
- **Transcription:** AssemblyAI (speaker diarization)

**Supabase Project Name:** `meeting-intelligence`
**Supabase Project ID:** `qjmswgbkctaazcyhinew`

## Architecture
Three separate services via Docker Compose:
- `api` — FastAPI backend (`src/api/`)
- `ui` — Streamlit dev UI (`src/ui/`)
- `db` — Supabase (external, configured via env vars)

React frontend (`frontend/`) is a standalone Next.js app — run separately with `npm run dev`.

Pipeline: Ingest -> Chunk -> Embed -> Store -> Retrieve -> Generate

## UI Environments

Three UIs are maintained. React is the canonical production UI; the others are dev/exploration tools.

| UI | Path | Start command | Default URL | Purpose |
|----|------|---------------|-------------|---------|
| **React/Next.js** (primary) | `frontend/` | `cd frontend && npm run dev` | `http://localhost:3000` | Production UI — upload, chat, meetings list. Deployed to Vercel. |
| **Streamlit** (dev) | `src/ui/app.py` | `make streamlit` | `http://localhost:8501` | Lightweight dev UI — maintained for rapid prototyping and experimentation. No npm required. |
| **API Explorer** (dev) | `src/api/` | `make api` (always on) | `http://localhost:8000/docs` | FastAPI auto-generated Swagger UI. Use `/redoc` for ReDoc view. Useful for testing endpoints directly. |

**Maintenance policy:**
- React: all new user-facing features go here
- Streamlit: keep working, update when backend API changes; good for trying new ideas before building React components
- API docs: no maintenance needed — auto-generated from route definitions

## Project Structure
```
src/
  api/            # FastAPI endpoints (POST /ingest, POST /query, GET /meetings)
  ingestion/      # Transcript parsing (.vtt/.txt/.json), chunking, embedding
  retrieval/      # Semantic + hybrid search, query processing
  extraction/     # Structured extraction (action items, decisions, topics)
  evaluation/     # Test set generation, Claude-as-judge metrics, cross-check (no RAGAS/DeepEval)
  ui/             # Streamlit application
tests/            # pytest test suite
data/             # Sample transcripts, MeetingBank subset
supabase/         # Database migrations
docs/             # Work log, architecture notes
.issues/          # Auto-exported GitHub issues/PRs as markdown (committed, nightly update)
private-context/  # Private planning docs (gitignored — never commit)
```

## Commands
```bash
make api              # Start FastAPI dev server (kills any stale process on the port first)
make streamlit        # Start Streamlit UI
make test             # Run pytest suite
make lint             # Run ruff + mypy
make format           # Auto-format with ruff
docker compose up     # Start all services
```

## Starting the Dev Environment

**This is fundamental. If you cannot start the dev environment, you cannot test, verify, or debug anything. Do this first, every time.**

### Step 1 — API server
```bash
cd /c/meeting-intelligence
make api
# Starts on http://localhost:8000 — verify with: curl http://localhost:8000/health
```

`make api` runs `scripts/start-api.sh` which **kills any existing process on the port before starting**. You should never need to manually hunt for stale processes. If `make` is not on PATH (Git Bash limitation), run directly:
```bash
bash scripts/start-api.sh
# or with a custom port:
PORT=8080 bash scripts/start-api.sh
```

### Step 2 — React frontend

**Windows note:** `npm run dev` (webpack bundler) has a bug on Windows where CSS and core chunks 404 in the browser. Use Turbopack instead — it works correctly and is faster:

```bash
cd /c/meeting-intelligence/frontend
npm run dev -- --turbo
# Starts on http://localhost:3000 with hot reload
```

Before running for the first time after a `git pull`, always run `npm install` first — `git pull` updates `package.json` but does not install new packages automatically.

If Turbopack has issues, fallback: `npm run build && npm start` (no hot reload, rebuild required after each change).

### Step 3 — Verify both are up
```bash
curl http://localhost:8000/health          # → {"status":"healthy"}
curl -o /dev/null -w "%{http_code}" http://localhost:3000   # → 200 or 307 (redirect to /login)
```

### Windows-specific: killing stale processes manually
If `scripts/start-api.sh` fails to clear a port (rare), use this:
```bash
# Find what's on port 8000
netstat -ano | grep ":8000" | grep LISTEN
# Kill it by PID (replace 12345 with actual PID)
cmd //c "taskkill /PID 12345 /F"
```
To kill ALL node processes (clears stale Next.js dev servers):
```bash
cmd //c "taskkill /F /IM node.exe"
```

### Environment files
- `/.env` — Python API keys (copy from `.env.example`, never commit)
- `/frontend/.env.local` — Next.js env vars (copy from `frontend/.env.example`, never commit)
- Both files must exist before starting. If the API crashes immediately on startup, a missing `.env` is the most likely cause.

## Testing
- Framework: **pytest**
- Mark expensive API-calling tests with `@pytest.mark.expensive`
  - Run all tests: `make test`
  - Skip expensive: `pytest -m "not expensive"`
- Linting: **ruff** (linter + formatter)
- Type checking: **mypy** (strict mode, type hints required throughout)
- **Always run `make lint && make test` before pushing to any branch or main**

## Testing Standards

### External API mocking (MANDATORY)
- **Never make live API calls in regular tests** — mock all external services (AssemblyAI, OpenAI, Supabase, Claude) using `unittest.mock.patch`
- Mark tests `@pytest.mark.expensive` ONLY when a live API call is truly necessary and unavoidable
- Tests in `tests/` must pass with no API keys set
- **After every PR touching an external integration, I will tell you explicitly in chat what needs manual testing before you merge.**

### Scope philosophy for fixes
- **Implement now** if: ≤5 lines, no new tests needed, behaviour change is safe
- **Defer** if: requires significant new test coverage, architectural decision, or risk of side effects
- Either way: leave a code comment explaining the trade-off and reference the issue number

## Git Workflow
- **Conventional Commits:** `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- **Never work on main directly** — always create feature branches per issue
- Branch naming: `feat/issue-number-short-description` or `fix/issue-number-short-description`
- Check if a branch already exists for the issue before creating a new one (avoid duplicates across sessions)
- Lint + test before push — whether it's a branch or main, any merge of the sort
- Issue-branch workflow: each GitHub issue gets its own branch
- Be explicit in commit messages whenever there is a band-aid fix, for clear traceability
- After each fix, perform a **band-aid fix assessment**: list each fix, state if it was proper or band-aid, why, potential side effects, and what a proper fix would look like
- When creating GitHub issues, avoid `#` followed by a number for list items (GitHub interprets as issue reference). Use `1.` or `**1.**` for numbered lists instead.

## Worktree Development (Parallel Issue Work)

This project uses git worktrees for parallel development with separate Claude Code sessions.

### Branch Safety Rules — CRITICAL

These rules apply to every agent and every session working in a worktree. Violating them can corrupt the main branch.

**NEVER, under any circumstances:**
- `git push origin main` from a worktree — ever, for any reason
- `git commit` from the main workspace (`C:\meeting-intelligence`) for work that belongs on a feature branch
- Force-push or rebase a branch that already has an open PR without explicit user instruction
- Merge a branch into main from within a worktree

**ALWAYS, before touching any git command in a worktree:**
1. Run `git branch --show-current` and verify you are on the expected feature branch
2. If the branch does not match the worktree's context file — STOP. Do not commit. Flag the mismatch to the user.

**Permitted in a worktree:**
- `git add`, `git commit`, `git push origin <feature-branch>` — normal development workflow
- `git push -u origin <feature-branch>` — to set tracking on first push
- `gh pr create` — creating a PR against main is fine; the merge itself is the user's decision
- `gh issue comment` — progress updates on GitHub issues

**Only the main workspace may:**
- Push to `main` (`git push origin main`)
- Apply database migrations (`supabase db push --linked`)
- Merge PRs (done via GitHub UI or `gh pr merge`, user-initiated)

### Creating a Worktree
**Only run from the main workspace (`meeting-intelligence`).**

```bash
# Step 1: Create worktree
git worktree add ../meeting-intelligence-wt1-issue-1 -b feat/1-foundation

# Step 2: Copy environment
cp .env ../meeting-intelligence-wt1-issue-1/.env

# Step 3: Install Python dependencies (uses pyproject.toml)
cd ../meeting-intelligence-wt1-issue-1
pip install -e ".[dev]"
```

### Naming Convention

| Component | Format | Example |
|-----------|--------|---------|
| Folder | `meeting-intelligence-wt{N}-issue-{XXX}` | `meeting-intelligence-wt1-issue-1` |
| Branch | `feat/issue-number-description` | `feat/1-foundation` |

### Worktree Context Files (`docs/worktrees/`)

Every worktree has a context file in `docs/worktrees/`. The filename prefix shows its current state — visible at a glance in any file explorer:

| Prefix | Meaning |
|--------|---------|
| `PLANNED_` | Issue raised, worktree not yet created |
| `ACTIVE_` | Worktree created and work in progress |
| `MERGED_` | PR merged, worktree removed |

**Lifecycle:**
1. When an issue is queued for a worktree, create `PLANNED_wt{N}-issue-{XXX}.md` with the brief context.
2. When the worktree is created, rename to `ACTIVE_` and update the `**Status:**` line in the file.
3. When the PR is merged and the worktree is removed, rename to `MERGED_` and record the PR number and date on the status line.

The second line of every context file is a `**Status:**` badge — the single most useful line when you open the file.

### API Port Allocation (if running services in worktrees)

Use `PORT=XXXX make api` and `STREAMLIT_PORT=YYYY make streamlit` — the Makefile respects these env vars (defaults to 8000/8501).

| Worktree | API port | Streamlit port |
|----------|----------|----------------|
| Main workspace | :8000 | :8501 |
| WT1 (issue-22/25) | :8010 | :8511 |
| WT2 | :8020 | :8521 |
| WT3 (issue-23/33) | :8030 | :8531 |
| WT4 | :8040 | :8541 |
| WT5 (issue-32) | :8050 | :8551 |
| WT6 (issue-30) | :8060 | :8561 |
| WT7 (issue-31) | :8070 | :8571 |
| WT8 (issue-34) | :8080 | :8581 |
| WT9 (issue-35) | :8090 | :8591 |
| WT10 (issue-52) | :8100 | frontend-only (no API changes) |
| WT11 (issues-41/44) | frontend-only | uses main :8000 |
| WT12 (issues-42/43) | :8120 | — |
| WT13 (issue-47) | frontend-only | uses main :8000 |
| WT14 (issue-48) | :8130 | — |
| WT15 (issue-49) | frontend-only | uses main :8000 |
| WT16 (issue-45) | :8160 | — |
| WT17 (issue-61) | :8170 | — |

Example: `PORT=8060 make api` to start the API on port 8060 from WT6.

### Shared Database Caution
All worktrees share the same Supabase project. Schema migrations applied in any worktree take effect immediately and permanently for the entire project.

**CRITICAL — migrations are the main workspace's responsibility:**
- **Never apply a migration from a worktree without explicit user instruction.** If your branch requires a schema change, write the migration file and stop — do not run `supabase db push`. Ask the user: "This branch requires a migration. Should I apply it now, or will the main workspace handle it?"
- **The main workspace applies all migrations**, after checking that no other open worktree has a conflicting schema change pending. Before applying, check open PRs and active worktrees for any branches that also touch the schema.
- **Migrations are one-at-a-time and sequential.** Two worktrees must never push schema changes concurrently. If unsure whether another branch is mid-migration, ask before proceeding.
- **Migration commands:** `supabase migration new <name>` to create, `supabase db push --linked` to apply. Never use the Supabase MCP `apply_migration` tool in production — it bypasses the migration tracking table.

### Agent-Driven Worktrees

When a Claude agent is launched to work autonomously in a worktree (rather than a human working interactively), the agent follows this protocol:

**On start:**
1. `cd` into the worktree directory (e.g. `C:\meeting-intelligence-wt12-issues-42-43`)
2. Run `git branch --show-current` — verify it matches the expected branch; abort if not
3. Read the context file from `docs/worktrees/ACTIVE_wt{N}-*.md` for the implementation spec
4. Run `gh issue view <issue-number>` for every issue this worktree addresses — read the full description, labels, and all comments. The context file is a summary; the issue is the source of truth and may contain additional decisions, follow-up notes, or corrections added after the context file was written.

**During work:**
- Make all code changes, run tests (`pytest tests/ -m "not expensive"`), run lint (`ruff check src/ tests/`), run type checking (`mypy src/`)
- Only commit when tests and lint are passing
- Use conventional commit messages (`feat:`, `fix:`, etc.)

**On completion:**
- `git push -u origin <branch>` — push the branch (never main)
- `gh pr create` — open a PR against main with a summary of changes
- `gh issue comment <issue-number> --body "..."` — post a progress note on each relevant issue
- **Leave the worktree directory intact** — do not delete it; the user may want to enter it manually to test, inspect, or continue work

**The worktree stays alive.** It is not cleaned up by the agent. The user decides when to remove it (after reviewing and merging the PR).

### Remove When Done (user decision, after PR merged)

The user removes the worktree manually once they are satisfied with the PR and it has been merged:

```bash
# Run from main workspace only
git worktree remove ../meeting-intelligence-wt1-issue-1
git branch -d feat/1-foundation
```

Rename the context file to `MERGED_` and record the PR number and merge date.

## Work Log
**IMPORTANT**: Always maintain `docs/work_log.md`:
- **After any meaningful action** (code change, major decision), append an entry at the END
- **Always keep entries in chronological order** (oldest at top, newest at bottom)
- **NEVER create new log/summary files** — always use `docs/work_log.md`
- **To check recent activity**: Read the last 5-10 entries from end of file

### Entry Template
```
### [<ISO8601 timestamp>] — <Type: Session Summary | Task/Event>
**Focus:** <one-liner>
**Done:**
- <up to 3 bullets>
**Next:**
- <1–2 bullets>
**Decisions:**
- <0–2 bullets>
```

### Constraints
- Max 3 bullets per list
- Do not paste large code or logs; link to diffs/PRs/issues instead
- Do not overwrite existing entries; append only

## Environment
- Copy `.env.example` to `.env` and fill in API keys
- Required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ASSEMBLYAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- Optional keys: `GOOGLE_API_KEY` (Gemini image summary — graceful 501 if absent)
- Config loaded via Pydantic BaseSettings (validates on startup)

## Infrastructure & Deployment

### Cloud Run (API backend)
- **GCP Project:** `meeting-intelligence-488107` (region: `europe-west1`)
- **Service:** `meeting-intelligence-api`
- **URL:** `https://meeting-intelligence-api-893899075779.europe-west1.run.app`
- **CI/CD:** Cloud Build triggers automatically on every push to `main` — no GitHub Actions needed
- **gcloud CLI is available** — use it to inspect services, check build status, describe configs
  ```bash
  gcloud config set project meeting-intelligence-488107
  gcloud run services list --platform managed
  gcloud builds list --limit 5
  gcloud run services describe meeting-intelligence-api --region europe-west1
  ```

### Vercel (frontend)
- **Project:** `meeting-intelligence-wc` (team: `wayes-btyes-projects`)
- **Production URL:** `https://meeting-intelligence-wc.vercel.app`
- **Vercel CLI is available** — use it to inspect deployments and env vars
  ```bash
  vercel list --scope wayes-btyes-projects
  ```
- `NEXT_PUBLIC_API_URL` is set in Vercel dashboard to the Cloud Run URL above

## MCP Server Usage

### Supabase MCP
- **Use for**: Database operations, schema management, checking RLS policies
- **CRITICAL**: Always check Supabase MCP when database issues arise
- **Best practice**: Verify schema, debug queries, validate pgvector operations
- **Migrations**: Always use `supabase migration new` + `supabase db push --linked`. NEVER use MCP `apply_migration` for production (doesn't track in migration table)

### Context7 MCP
- **Use for**: Documentation lookup for FastAPI, RAGAS, DeepEval, Streamlit, AssemblyAI, etc.
- **CRITICAL**: Always check Context7 when knowledge gaps exist — training data may be outdated
- **Best practice**: Verify current API docs before implementing integrations

### Playwright MCP
- **Use for**: UI testing and validation after React or Streamlit changes
- **Best practice**: Take screenshots before/after UI changes; use chrome-devtools MCP for React (Next.js), Playwright for broader browser automation

## PRD Maintenance
- All new features must be added to `docs/PRD.md` with ID, priority, and status before implementation.
- Update the Decisions Log in `docs/PRD.md` when architectural decisions are made or changed.

## Custom Skills (`.claude/commands/`)
Project-specific slash commands available as `/project:<name>`:
- `/project:status` — open issues, test status, mypy errors
- `/project:ingest-test` — run a transcript through the full pipeline with verification
- `/project:smoke-test` — guided walkthrough of all main user flows

## Web Search is Mandatory, Not Optional

When something isn't working, behaviour is unexpected, a library API looks unfamiliar, or you're about to implement something non-trivial — **search first**. Training data goes stale fast; the web doesn't. Use `WebSearch` for error messages, library docs, community bug reports, and "is this a known issue?" checks. Do this proactively and frequently, not as a last resort.

## Key Design Decisions
- Direct Claude API calls (no orchestration frameworks) — understand what happens under the hood
- Supabase as single store for vectors + metadata + structured data (no separate vector DB)
- Strategy toggle system: swap chunking (naive/speaker-turn) and retrieval (semantic/hybrid) via PipelineConfig
- Evaluation is core: auto-generated test sets, RAGAS metrics, RAG vs context-stuffing cross-check

## GitHub Issues Context (`.issues/`)
The `.issues/` directory contains **auto-exported GitHub issues and PRs as markdown**, updated nightly by a GitHub Actions workflow. This directory is **committed to the repo** (not gitignored).

**Purpose:** Provides full issue/PR context to any LLM session — including Claude web, OpenAI connectors, or any tool that reads repo files — without requiring GitHub CLI setup. When answering questions about project history, tasks, or decisions, **read `.issues/` for full context** rather than assuming the GitHub API is available.

## private-context/
The `private-context/` directory is **gitignored**. It contains private planning docs,
research notes, and assignment context. Never commit or reference these files in code.
