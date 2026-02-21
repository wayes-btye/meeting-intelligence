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
  evaluation/     # Test set generation, RAGAS/DeepEval metrics, cross-check
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
make api              # Start FastAPI dev server
make streamlit        # Start Streamlit UI
make test             # Run pytest suite
make lint             # Run ruff + mypy
make format           # Auto-format with ruff
docker compose up     # Start all services
```

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

### Creating a Worktree
**Only run from the main workspace (`meeting-intelligence`).**

```bash
# Step 1: Create worktree
git worktree add ../meeting-intelligence-wt1-issue-1 -b feat/1-foundation

# Step 2: Copy environment
cp .env ../meeting-intelligence-wt1-issue-1/.env

# Step 3: Install dependencies (in the worktree)
cd ../meeting-intelligence-wt1-issue-1
pip install -r requirements.txt
```

### Naming Convention

| Component | Format | Example |
|-----------|--------|---------|
| Folder | `meeting-intelligence-wt{N}-issue-{XXX}` | `meeting-intelligence-wt1-issue-1` |
| Branch | `feat/issue-number-description` | `feat/1-foundation` |

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

Example: `PORT=8060 make api` to start the API on port 8060 from WT6.

### Shared Database Caution
All worktrees share the same Supabase project. Schema migrations in one worktree affect all others. Coordinate schema changes — only one worktree should run migrations at a time.

### Remove When Done (after PR merged)
```bash
git worktree remove ../meeting-intelligence-wt1-issue-1
git branch -d feat/1-foundation
```

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
- Config loaded via Pydantic BaseSettings (validates on startup)

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
