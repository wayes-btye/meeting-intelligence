# Meeting Intelligence

A RAG-powered conversational AI system that ingests meeting transcripts, extracts structured insights, and answers natural language queries across a corpus of meetings.

**Live demo:** https://meeting-intelligence-wc.vercel.app
**API docs:** https://meeting-intelligence-api-893899075779.europe-west1.run.app/docs
**Reviewer guide:** [REVIEWER-GUIDE.md](REVIEWER-GUIDE.md) — start here if you're reviewing this for an assessment

---

## Why This Exists

Single-meeting summarisation is a solved problem — you can paste a transcript into any LLM's context window and get decent answers. The interesting challenge starts when you have **50+ meetings** and need to answer questions like:

- *"What action items were assigned to Sarah across all Q1 planning meetings?"*
- *"How has the team's position on the migration timeline evolved over the last 3 months?"*
- *"Which meetings discussed budget concerns, and what decisions were reached?"*

At that scale, context-stuffing breaks down and you genuinely need retrieval. This project builds that retrieval layer — with an honest evaluation of where RAG helps and where it doesn't.

---

## Documentation

| Document | What it covers |
|----------|---------------|
| [REVIEWER-GUIDE.md](REVIEWER-GUIDE.md) | Live demo access, what to try, code pointers |
| [docs/PRD.md](docs/PRD.md) | Full requirements, MVP scope, implementation status, decisions log |
| [docs/architecture.md](docs/architecture.md) | Design decisions with rationale, trade-offs, production considerations |
| [docs/engineering-philosophy.md](docs/engineering-philosophy.md) | Thought process: Streamlit→React, CI/CD, worktree workflow, RAG stages, testing |
| [docs/work_log.md](docs/work_log.md) | Chronological development log |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│              React / Next.js 14 Frontend (Vercel)                   │
│  Upload │ Chat │ Meetings │ Chunk Viewer │ Supabase Auth            │
└───────────────────────────┬────────────────────────────────────────┘
                            │ HTTP (JSON)
┌───────────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend (Cloud Run)                       │
│                                                                      │
│  POST /api/ingest   POST /api/query   GET /api/meetings             │
│  GET /api/meetings/{id}   POST /api/meetings/{id}/extract           │
│  POST /api/meetings/{id}/image-summary                              │
│                                                                      │
│  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│  │  Ingestion    │  │   Query Router   │  │   Extraction         │ │
│  │  Pipeline     │  │                  │  │   (direct LLM call)  │ │
│  └──────┬────────┘  └────────┬─────────┘  └──────────────────────┘ │
│         │                   │                                        │
│         │           structured? ──────────────────────────────────┐ │
│         │                   │ no                                  │ │
│         │           ┌───────▼──────────┐                          │ │
│         │           │  RAG Pipeline    │                          │ │
│         │           │  retrieve→gen    │                          │ │
│         │           └───────┬──────────┘                          │ │
└─────────┼───────────────────┼─────────────────────────────────────┘ │
          │                   │                                        │
┌─────────▼───────────────────▼──────────────────────────────────┐   │
│                    Supabase (Postgres + pgvector)                │   │
│                                                                  │   │
│  meetings table    chunks table          extracted_items         │◄──┘
│  (metadata +       (halfvec 1536         (action items,
│   auth RLS)         + tsvector)           decisions, topics)
│                                                                  │
│  HNSW index (cosine similarity)   GIN index (full-text search)  │
│  match_chunks() — vector search   hybrid_search() — combined    │
└─────────────────────────────────────────────────────────────────┘
          │                   │
   ┌──────▼──────┐    ┌───────▼──────────┐    ┌──────────────────┐
   │  OpenAI     │    │   Claude API     │    │  Vertex AI       │
   │  Embeddings │    │  (Generation +   │    │  (Image summary) │
   │  (1536d)    │    │   Extraction +   │    └──────────────────┘
   └─────────────┘    │   Evaluation)    │
                      └──────────────────┘
```

### Core Pipeline

1. **Ingest** — Upload transcripts (`.vtt`, `.txt`, `.json`, `.zip`, Teams VTT format) or audio files (`.mp3`, `.wav`). Audio is transcribed via AssemblyAI with speaker diarization.
2. **Chunk** — Transcripts are split using configurable strategies (naive fixed-size, speaker-turn based). Each chunk retains speaker label, timestamps, and meeting metadata.
3. **Embed & Store** — Chunks are embedded with OpenAI `text-embedding-3-small` and stored in Supabase (Postgres + pgvector) alongside structured metadata.
4. **Route** — Incoming queries are classified: structured queries ("list action items") go to SQL; open-ended queries go to RAG.
5. **Retrieve** — RAG queries use hybrid search (semantic similarity + keyword matching) with configurable weights and metadata pre-filtering.
6. **Generate** — Retrieved context is passed to Claude for answer generation with source attribution (speaker, timestamp, meeting).

### Strategy Toggle System

| Layer | Strategies | Default |
|-------|-----------|---------|
| Chunking | Naive (fixed-size, 500 tokens), Speaker-turn | Speaker-turn |
| Retrieval | Semantic (vector only), Hybrid (vector + FTS) | Hybrid |
| Transcription | AssemblyAI, Manual upload | AssemblyAI |

Strategies are swappable per request via `PipelineConfig`. Both versions of a chunked meeting are stored simultaneously — strategy comparisons don't require re-ingestion.

---

## UI Environments

Three UIs are maintained:

| UI | Path | URL | Purpose |
|----|------|-----|---------|
| **React/Next.js** (production) | `frontend/` | http://localhost:3000 | Main demo UI — upload, chat, meetings, auth |
| **Streamlit** (dev) | `src/ui/app.py` | http://localhost:8501 | Dev/experimentation — no npm required |
| **API Explorer** (always on) | auto-generated | http://localhost:8000/docs | FastAPI Swagger — test endpoints directly |

**On the Streamlit → React journey:** Development started with Streamlit to stay focused on the RAG pipeline without frontend overhead. As the parameter exposure and debugging requirements grew (chunk scores, strategy toggles, source attribution cards), Streamlit's component model became the constraint. React was the right move — and with AI-assisted development, the scaffolding cost was low enough that "thin UI" was no longer a meaningful argument for Streamlit as the demo surface. Streamlit is retained for rapid prototyping. See [docs/engineering-philosophy.md](docs/engineering-philosophy.md).

---

## Tech Stack Decisions

| Choice | Why |
|--------|-----|
| **Python + FastAPI** | Standard for ML/AI pipelines. Typed endpoints, async support, auto-generated OpenAPI docs. |
| **React / Next.js 14** | App Router with Supabase Auth. Production frontend — Vercel deployment, proper state management, markdown rendering. |
| **Supabase (pgvector)** | Postgres-native vector search: one database for vectors, metadata, structured data, and auth. Hybrid search (vector + FTS) runs as a single SQL function. No separate vector DB to manage. |
| **Claude API (direct)** | Direct SDK calls, no LangChain/LlamaIndex. For a lead role, understanding what happens under the hood matters more than using an orchestration framework. Strategy toggle and evaluation framework both require full control over each pipeline stage. |
| **OpenAI text-embedding-3-small** | Good quality/cost balance. 1536 dimensions. Straightforward to swap via the embedding layer. |
| **AssemblyAI** | Best developer experience for transcription + speaker diarization. Production note: for regulated environments (HIPAA/pharma), WhisperX self-hosted is the correct alternative — audio never leaves your infrastructure. |

---

## Evaluation

The evaluation framework is a core part of the project — not an afterthought.

### Approach

- **Auto-generated test set** — Claude generates Q&A pairs from MeetingBank reference summaries, producing questions across difficulty levels (factual, inference, action items, decisions, multi-meeting).
- **Claude-as-judge evaluation** — Four metrics implemented as explicit Python code with Claude judge prompts (not RAGAS or DeepEval libraries):
  - *Faithfulness* — are all claims in the answer supported by retrieved context?
  - *Answer relevancy* — does the answer directly address the question?
  - *Context precision* — what fraction of retrieved chunks are actually relevant?
  - *Context recall* — does the retrieved context contain what's needed for the expected answer?
- **Cross-check evaluation** — Every test question runs through both the RAG pipeline and full-transcript context-stuffing. Disagreements reveal where RAG genuinely helps vs where simpler approaches work just as well.
- **Strategy comparison** — Side-by-side metrics for all chunking × retrieval combinations (naive/speaker-turn × semantic/hybrid).

### Running the evaluation

```bash
# Generate test set and run evaluation (requires live API keys + loaded meeting data)
python -m src.evaluation.runner \
    --meetings <meeting-id-1> <meeting-id-2> \
    --output reports/eval_results
```

### Current status

The evaluation framework is fully implemented and tested (512 lines of test coverage). Actual results require the MeetingBank corpus loaded into Supabase — see `scripts/load_meetingbank.py`. This is the next step after the initial submission.

---

## Data

Uses [MeetingBank](https://huggingface.co/datasets/huuuyeah/MeetingBank) — 1,366 city council meetings with word-level alignment, speaker diarization, and reference summaries. 30 meetings are downloaded to `data/meetingbank/` and ready to load.

City council meetings work well: clear structure (motions, votes, named speakers with titles), and reference summaries enable automated evaluation without manually reading every transcript.

A real test transcript for local testing is at `tests/data/gitlab-engineering-meeting.txt` (GitLab engineering meeting, 7 speakers).

---

## Setup

### Prerequisites

- Python 3.11+, Node.js 18+
- Supabase account (free tier works)
- API keys: Anthropic (Claude), OpenAI (embeddings), AssemblyAI (transcription)

### Quick Start

```bash
git clone https://github.com/wayes-btye/meeting-intelligence.git
cd meeting-intelligence

# Environment
cp .env.example .env
# Edit .env — add your API keys

pip install -e ".[dev]"

# Database: run migrations in supabase/migrations/ against your Supabase project

# Start API
make api                  # → http://localhost:8000

# Start React frontend (separate process)
cd frontend && npm install
cp .env.example .env.local
# Edit .env.local — add NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev -- --turbo   # Windows (Turbopack — avoids a webpack bug on Windows)
npm run dev              # macOS/Linux
# → http://localhost:3000
```

### Environment Variables

**`/.env` (API backend):**
```
ANTHROPIC_API_KEY=        # Claude API
OPENAI_API_KEY=           # Embeddings
ASSEMBLYAI_API_KEY=       # Audio transcription
SUPABASE_URL=             # Your Supabase project URL
SUPABASE_KEY=             # Your Supabase anon/service key
```

**`/frontend/.env.local` (React frontend):**
```
NEXT_PUBLIC_API_URL=           # FastAPI backend URL
NEXT_PUBLIC_SUPABASE_URL=      # Supabase project URL
NEXT_PUBLIC_SUPABASE_ANON_KEY= # Supabase anon key
```

---

## Project Structure

```
meeting-intelligence/
├── src/
│   ├── api/              # FastAPI endpoints + routing
│   ├── ingestion/        # Transcript parsing, chunking, embedding
│   ├── retrieval/        # Query router, hybrid search, retrieval strategies
│   ├── extraction/       # Structured extraction (action items, decisions, topics)
│   ├── evaluation/       # Claude-as-judge metrics, cross-check, test set generation
│   └── ui/               # Streamlit dev UI
├── frontend/             # React / Next.js 14 production frontend
├── tests/                # 132 tests (external APIs mocked — no keys needed)
├── data/                 # MeetingBank subset (30 meetings, ready to load)
├── supabase/             # Database migrations (pgvector, HNSW, hybrid search SQL)
├── scripts/              # Data loading and API startup scripts
├── docs/                 # Architecture, PRD, engineering philosophy, work log
├── .issues/              # Auto-exported GitHub issues/PRs as markdown (committed, nightly)
└── docker-compose.yml    # Brings up API + Streamlit (React runs separately)
```

---

## Available Commands

```bash
# Development
make api                  # Start FastAPI dev server (port 8000, kills stale processes first)
make streamlit            # Start Streamlit dev UI (port 8501)
make test                 # Run 132 tests (all external APIs mocked)
make lint                 # ruff + mypy
make format               # Auto-format with ruff
docker compose up         # Start API + Streamlit via Docker

# Data
python scripts/load_meetingbank.py --max 10     # Load 10 MeetingBank meetings into Supabase

# Evaluation
python -m src.evaluation.runner \
    --meetings <id1> <id2> \
    --output reports/eval_results
```

---

## Production Roadmap

This is an MVP prototype. For production deployment in a regulated environment:

- **Self-hosted transcription** — WhisperX instead of AssemblyAI (audio never leaves infrastructure; HIPAA/pharma compliance)
- **API authentication** — `X-API-Key` middleware (Issue #53, ~15 lines)
- **Project namespacing** — Multi-tenant data isolation without full auth rebuild (Issue #45)
- **Cross-encoder reranking** — 15–40% precision improvement; adds latency (benchmarked, not implemented)
- **Contextual retrieval** — Prepend document context to chunks before embedding; 67% reduction in retrieval failures (Anthropic research)
- **Evaluation-driven weight tuning** — Grid-search hybrid weights (70/30 are defaults) once evaluation runs on the full corpus
- **LiteLLM model abstraction** — Swap generation and embedding models per query type; compare providers (Issues #20, #21)
- **Observability** — Token usage tracking, retrieval quality monitoring, latency dashboards

---

## AI Tool Usage

This project was built using Claude Code as an AI development assistant:

- **Architecture decisions** were mine, informed by research into RAG systems and the specific constraints of this assignment.
- **The evaluation framework design** — the cross-check approach (RAG vs context-stuffing comparison) — was my idea for honestly measuring where RAG adds value rather than assuming it always does.
- **The query routing design** (knowing when NOT to use RAG) is a deliberate architectural choice, not something an AI suggested.
- **Implementation** was AI-assisted — Claude Code generated code; I reviewed, iterated, and made engineering judgement calls at each stage.

For a lead role, the relevant signal isn't whether AI tools were used — it's whether the engineering judgement is present in the output. I believe it is, and I'm happy to discuss any decision in this codebase.
