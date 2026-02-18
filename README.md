# Meeting Intelligence

A RAG-powered conversational AI system that ingests meeting transcripts (text and audio), extracts structured insights, and answers natural language queries across a corpus of meetings.

## Why This Exists

Single-meeting summarisation is a solved problem — you can paste a transcript into any LLM's context window and get decent answers. The interesting challenge starts when you have **50+ meetings** and need to answer questions like:

- *"What action items were assigned to Sarah across all Q1 planning meetings?"*
- *"How has the team's position on the migration timeline evolved over the last 3 months?"*
- *"Which meetings discussed budget concerns, and what decisions were reached?"*

At that scale, context-stuffing breaks down and you genuinely need retrieval. This project builds that retrieval layer — with an honest evaluation of where RAG helps and where it doesn't.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Streamlit  │────▶│   FastAPI    │────▶│    Claude API     │
│   Frontend   │◀────│   Backend    │◀────│   (Generation)    │
└──────────────┘     └──────┬───────┘     └──────────────────┘
                            │
                    ┌───────┴───────┐
                    │               │
              ┌─────▼─────┐  ┌─────▼──────┐
              │  Supabase  │  │ AssemblyAI  │
              │  pgvector  │  │(Transcribe) │
              │  + hybrid  │  └────────────┘
              │   search   │
              └────────────┘
```

### Core Pipeline

1. **Ingest** — Upload audio files or text transcripts (.vtt, .txt, .json). Audio is transcribed via AssemblyAI with speaker diarization.
2. **Chunk** — Transcripts are split using configurable strategies (naive fixed-size, speaker-turn based). Each chunk retains speaker labels, timestamps, and meeting metadata.
3. **Embed & Store** — Chunks are embedded with OpenAI `text-embedding-3-small` and stored in Supabase (Postgres + pgvector) alongside structured metadata.
4. **Retrieve** — Queries use hybrid search (semantic similarity + keyword matching) with metadata pre-filtering (by meeting, speaker, date range).
5. **Generate** — Retrieved context is passed to Claude for answer generation with source attribution.

### Strategy Toggle System

The system supports swappable strategies at each pipeline stage, configured via a single `PipelineConfig`:

| Layer | Strategies | Default |
|-------|-----------|---------|
| Chunking | Naive (fixed-size), Speaker-turn | Speaker-turn |
| Retrieval | Semantic, Hybrid (semantic + keyword) | Hybrid |
| Transcription | AssemblyAI, Manual upload | AssemblyAI |

This isn't about having the "best" strategy — it's about being able to **compare them systematically** and explain the trade-offs.

## Tech Stack Decisions

| Choice | Why |
|--------|-----|
| **Python + FastAPI** | Standard for ML/AI pipelines. FastAPI gives typed endpoints without boilerplate. |
| **Streamlit** | Fast to build, good enough for a demo UI. Not production frontend material, but that's not the point here. |
| **Supabase (pgvector)** | Postgres-native vector search means one database for vectors, metadata, and structured data. No separate vector DB to manage. Hybrid search (semantic + full-text) comes free with Postgres. |
| **Claude API (direct)** | Direct SDK calls, no LangChain/LlamaIndex wrapper. For a lead role, demonstrating you understand what's happening under the hood matters more than using an orchestration framework. |
| **OpenAI text-embedding-3-small** | Good balance of quality, speed, and cost for this use case. 1536 dimensions. |
| **AssemblyAI** | Best developer experience for transcription + speaker diarization. 30-minute setup vs half a day for self-hosted Whisper + pyannote. For production in regulated industries (pharma/healthcare), you'd want WhisperX self-hosted — documented in the roadmap. |

## Evaluation

The evaluation framework is a core part of the project, not an afterthought.

### Approach

- **Auto-generated test set** from MeetingBank reference summaries — Claude generates Q&A pairs from professional meeting minutes, producing 150-250 test questions across difficulty levels.
- **RAGAS + DeepEval metrics** — Faithfulness, answer relevancy, context precision/recall measured systematically.
- **Cross-check evaluation** — Every test question runs through both the RAG pipeline and full-transcript context-stuffing. Disagreements are categorised to understand where RAG genuinely helps vs where simpler approaches work fine.
- **Strategy comparison** — Side-by-side metrics for different chunking and retrieval configurations, with honest analysis of what actually moved the needle.

### What the Evaluation Showed

> *This section will be populated with actual results after running the evaluation framework.*

## Data

Uses [MeetingBank](https://huggingface.co/datasets/huuuyeah/MeetingBank) — 1,366 city council meetings with word-level alignment, speaker diarization, and reference summaries. A curated subset of 30-50 meetings is used for the demo corpus.

City council meetings work well for this because they have clear structure: motions, votes, named speakers with titles, and reference summaries that enable automated evaluation without manually reading every transcript.

## Setup

### Prerequisites

- Python 3.11+
- Supabase account (free tier works)
- API keys: Anthropic (Claude), OpenAI (embeddings), AssemblyAI (transcription)

### Quick Start

```bash
# Clone and setup
git clone https://github.com/wayes-btye/meeting-intelligence.git
cd meeting-intelligence

# Environment
cp .env.example .env
# Add your API keys to .env

# Install dependencies
pip install -e ".[dev]"

# Database setup
# Run the SQL migrations in supabase/migrations/ against your Supabase project

# Start the application
docker compose up
```

### Environment Variables

```
ANTHROPIC_API_KEY=        # Claude API
OPENAI_API_KEY=           # Embeddings
ASSEMBLYAI_API_KEY=       # Transcription
SUPABASE_URL=             # Your Supabase project URL
SUPABASE_KEY=             # Your Supabase anon/service key
```

## Project Structure

```
meeting-intelligence/
├── src/
│   ├── api/              # FastAPI endpoints
│   ├── ingestion/        # Transcript parsing, chunking, embedding
│   ├── retrieval/        # Search strategies, query processing
│   ├── extraction/       # Structured data extraction (action items, decisions)
│   ├── evaluation/       # Test set generation, metrics, cross-check
│   └── ui/               # Streamlit application
├── tests/
├── data/                 # Sample transcripts, MeetingBank subset
├── supabase/             # Database migrations
├── docker-compose.yml
└── README.md
```

## Production Roadmap

This is an MVP. For production deployment in a regulated environment (pharma/healthcare), you'd need:

- **Self-hosted transcription** — WhisperX instead of AssemblyAI, so audio never leaves your infrastructure. Critical for HIPAA/pharma compliance.
- **Authentication & RBAC** — Meeting access controls, team-based permissions.
- **Incremental ingestion** — Watch folders or webhook-triggered processing for new meeting recordings.
- **Cross-encoder reranking** — Improves retrieval precision by 15-40% in benchmarks. Straightforward to add but adds latency.
- **Contextual retrieval** — Prepending document-level context to each chunk before embedding (Anthropic's research shows 67% reduction in retrieval failures when combined with reranking).
- **Caching layer** — Repeated questions across users, prompt caching for cost reduction.
- **Observability** — Token usage tracking, retrieval quality monitoring, latency dashboards.

## AI Tool Usage

This project was built using Claude Code as an AI development assistant. Specifically:

- **Architecture decisions** were made by me, informed by research into the RAG landscape, production meeting intelligence systems, and the specific constraints of this assignment.
- **Implementation** was accelerated using Claude Code for code generation, with review and iteration at each stage.
- **Evaluation framework design** — the cross-check approach (RAG vs context-stuffing comparison) was my idea for honestly measuring where RAG adds value. Implementation was AI-assisted.
- **README** — drafted collaboratively, but the opinions and trade-off reasoning are mine.

I believe the interesting signal for a lead role isn't whether you used AI tools — it's whether you can direct them effectively and maintain engineering judgment about the output.

## Engineering Standards

- Type hints throughout, validated with mypy
- Tests for each pipeline stage (ingestion, chunking, retrieval, generation)
- Docker Compose for reproducible local setup
- Configuration via environment variables, no hardcoded secrets
- Git workflow with feature branches and descriptive commits
