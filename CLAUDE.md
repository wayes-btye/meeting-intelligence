# CLAUDE.md — Meeting Intelligence

## Stack
- **Language:** Python 3.11+
- **Backend:** FastAPI (API server)
- **Frontend:** Streamlit (thin client, calls FastAPI over HTTP)
- **Database:** Supabase (Postgres + pgvector for vectors, metadata, structured data)
- **LLM:** Claude API (direct SDK calls — no LangChain/LlamaIndex)
- **Embeddings:** OpenAI text-embedding-3-small (1536 dimensions)
- **Transcription:** AssemblyAI (speaker diarization)

**Supabase Project Name:** `meeting-intelligence`
**Supabase Project ID:** `qjmswgbkctaazcyhinew`

## Architecture
Three separate services via Docker Compose:
- `api` — FastAPI backend (src/api/)
- `ui` — Streamlit frontend (src/ui/)
- `db` — Supabase (external, configured via env vars)

Pipeline: Ingest -> Chunk -> Embed -> Store -> Retrieve -> Generate

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
- Main workspace: API :8000, Streamlit :8501
- Worktree 1: API :8010, Streamlit :8511
- Worktree 2: API :8020, Streamlit :8521
- Worktree 3: API :8030, Streamlit :8531

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
- **Use for**: UI testing and validation after Streamlit changes
- **Best practice**: Take screenshots before/after UI changes

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
