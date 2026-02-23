# Meeting Intelligence — Reviewer Guide

*A guide for the technical reviewer assessing this submission.*

---

## What This Is

A RAG-powered system for querying across a corpus of meeting transcripts. It ingests meeting transcripts (text, VTT, zip, Teams format), chunks and embeds them, and answers natural language questions with source attribution across the full meeting history.

The interesting engineering is not in "building a RAG pipeline" — that's table stakes. It's in:

- **Query router** — structured queries go to SQL; open-ended queries go to RAG. Demonstrates understanding of when RAG is and isn't the right tool.
- **Strategy comparison infrastructure** — multiple chunking and retrieval strategies, configurable per request, with an evaluation framework to measure which performs better.
- **Cross-check evaluation** — every test question runs through both RAG and full-transcript context-stuffing to test whether retrieval genuinely helps.
- **Parallel development workflow** — git worktrees, per-issue context files, structured GitHub issues. Shows how a lead manages concurrent feature work.

---

## Live Demo

**URL:** https://meeting-intelligence-wc.vercel.app

**Login credentials:**
```
Email:    wayes.chawdoury@gmail.com
Password: Test_123!
```

> **Note:** This is a single-user demo instance. Any uploads you make will appear in the shared meetings list — this is a known limitation tracked in Issue [#45](https://github.com/wayes-btye/meeting-intelligence/issues/45) (project namespacing). Feel free to upload test data; it can be cleaned up afterwards.

**API (Swagger/OpenAPI):**
https://meeting-intelligence-api-893899075779.europe-west1.run.app/docs

---

## Where to Start

Recommended reading order:

| Document | What it covers |
|----------|---------------|
| This file | Overview and what to try |
| [README](README.md) | Architecture, tech stack decisions, setup |
| [docs/architecture.md](docs/architecture.md) | Design decisions with rationale — why this database, why no orchestration framework, how hybrid search works, query routing |
| [docs/PRD.md](docs/PRD.md) | Full requirements with status flags (✅/⚠️/🔲/❌) — what was planned, delivered, and deferred |
| [docs/engineering-philosophy.md](docs/engineering-philosophy.md) | Thought process — Streamlit→React journey, CI/CD, worktrees, RAG stages, testing |

---

## What to Try

### 1. Upload a transcript

Go to the **Upload** page. A sample transcript is included in the repo:

**`tests/data/gitlab-engineering-meeting.txt`** — A real GitLab engineering key review meeting (24 minutes, 7 speakers, discussing MR rate KPIs, bug SLOs, and infrastructure issues).

Download it from: https://github.com/wayes-btye/meeting-intelligence/blob/main/tests/data/gitlab-engineering-meeting.txt

Alternatively, any `.vtt` file from a Teams or Zoom recording works. You can also upload a `.zip` containing multiple transcript files.

After upload, the system immediately returns:
- Extracted action items, decisions, and topics (direct LLM call on the full transcript — not RAG)
- A visual summary image

These use a direct full-context LLM call — not retrieval. This is an explicit architectural choice: a single document that fits in context is better handled by direct LLM than by probabilistic retrieval.

### 2. Ask questions in Chat

Go to the **Chat** page and try:

**Open-ended (routes through RAG pipeline):**
- "What were the main concerns raised?"
- "What decisions were made about infrastructure?"
- "Who mentioned the migration timeline?"

**Structured (routes to SQL — bypasses RAG entirely):**
- "List all action items"
- "What decisions were recorded?"

The chat UI shows which chunks were retrieved, their similarity scores, and the source attribution (speaker, timestamp, meeting). This transparency is intentional — retrieval is visible and debuggable, not a black box.

### 3. Toggle retrieval strategy

In the chat interface, switch between **Semantic** and **Hybrid** retrieval. The parameter panel shows exactly what changed. This demonstrates the strategy comparison infrastructure — it's designed to make differences observable, not theoretical.

### 4. Browse meetings

The **Meetings** page shows each ingested meeting with:
- Extracted items (action items, decisions, topics)
- Chunk viewer — see exactly how the transcript was chunked and what's in each chunk
- Full transcript view

### 5. Explore the API

The FastAPI backend has interactive Swagger docs — try endpoints directly without the UI:
https://meeting-intelligence-api-893899075779.europe-west1.run.app/docs

---

## The Most Interesting Code

For a lead-level code review, these are the most representative areas:

**Query routing (when NOT to use RAG):**
```
src/retrieval/query_router.py      # Classifies queries → SQL vs RAG
```

**Hybrid search implementation:**
```
src/retrieval/hybrid_search.py     # Vector + FTS combined scoring
```

**Strategy pattern:**
```
src/ingestion/chunkers.py          # Naive fixed-window + speaker-turn strategies
src/pipeline_config.py             # PipelineConfig — single config controls all strategies
```

**Evaluation framework (Claude-as-judge):**
```
src/evaluation/metrics.py          # 4 metrics: faithfulness, relevancy, precision, recall
src/evaluation/cross_check.py      # RAG vs context-stuffing comparison
src/evaluation/runner.py           # End-to-end evaluation orchestrator
```

**Database schema + hybrid search SQL:**
```
supabase/migrations/               # pgvector setup, HNSW index, hybrid_search() function
```

---

## Running Locally

### Prerequisites
- Python 3.11+, Node.js 18+
- Supabase project (free tier works)
- API keys: Anthropic, OpenAI, AssemblyAI

### Setup
```bash
git clone https://github.com/wayes-btye/meeting-intelligence.git
cd meeting-intelligence

# Environment
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY, OPENAI_API_KEY, ASSEMBLYAI_API_KEY, SUPABASE_URL, SUPABASE_KEY

pip install -e ".[dev]"

# Database: run migrations in supabase/migrations/ against your Supabase project

# Start API
make api                           # → http://localhost:8000

# Start React frontend
cd frontend && npm install
cp .env.example .env.local
# Edit .env.local: add NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev -- --turbo             # Windows (Turbopack)
npm run dev                        # macOS/Linux
# → http://localhost:3000
```

### Verify
```bash
curl http://localhost:8000/health   # → {"status":"healthy"}
```

### Run tests
```bash
make test    # 132 tests, all passing (external APIs mocked — no keys needed)
make lint    # ruff + mypy
```

---

## What Was Cut and Why

Nothing is hidden. Deferred items are in the PRD with status flags and in open GitHub issues:

| Item | Status | Rationale |
|------|--------|-----------|
| Evaluation results | Framework complete; not yet run against full corpus | Requires MeetingBank corpus loaded into live DB — infrastructure ready |
| Hybrid weight tuning | Defaults used (70% vector, 30% FTS) | Grid-search against evaluation output is the right approach; framework now supports it |
| Cross-encoder reranking | Not implemented | Documented roadmap item; 15–40% precision gain in benchmarks; adds latency |
| Multi-user isolation | Single shared account | Issue #45 — project namespacing; medium effort |
| Contextual retrieval | Not implemented | 67% retrieval failure reduction (Anthropic research); next RAG iteration |

---

## Development Process Artefacts

The repository contains more than code — the development process is visible:

**`.issues/` directory:** All 37+ issues and 18 PRs exported as markdown and committed. Readable without GitHub access. Also makes the project history queryable by any LLM via a simple repository connector — no GitHub API auth required.

**`docs/worktrees/`:** Context files for every parallel feature branch. Shows the worktree-based parallel development methodology.

**Commit history:** 79 commits on main, conventional commit format throughout.

**`docs/PRD.md`:** Living requirements document with status flags on every requirement.

---

## AI Tool Usage

This project was built using Claude Code as an AI development assistant:

- **Architecture decisions** were mine, informed by research into RAG systems and the constraints of this assignment.
- **The evaluation framework design** (cross-check: RAG vs context-stuffing) was my idea — the insight that you need to honestly measure where RAG adds value rather than assuming it always does.
- **The query routing design** (knowing when NOT to use RAG) is a deliberate architectural choice.
- **Implementation** was AI-assisted — Claude Code generated code; I reviewed, iterated, and made judgement calls at each stage.

For a lead role, the relevant signal is not whether AI tools were used — it's whether the engineering judgement is present in the output.
