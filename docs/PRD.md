# Product Requirements Document — Meeting Intelligence

**Status:** Living document — updated as implementation progresses
**Last updated:** 2026-02-19
**Author:** Wayes Chawdoury

---

## 1. Problem Statement

Single-meeting summarisation is a solved problem. You can paste any transcript into a modern LLM's context window and get a decent summary. The problem starts when you have **50+ meetings across multiple teams, spanning months**.

At that scale:

- **Context windows fail.** You cannot stuff 50 transcripts into a prompt. Even with Claude's 200K context, a large meeting corpus quickly exceeds any single window.
- **Cross-meeting patterns become invisible.** Which meetings discussed the same risk? How has the team's position on a decision evolved across quarters?
- **Action item tracking breaks down.** Who committed to what, across which meetings, and did they follow through?
- **Institutional memory degrades.** Key decisions get buried in old transcripts that nobody revisits.

This project builds the retrieval layer that makes this tractable — a Meeting Intelligence system that ingests, indexes, and answers natural language questions across a corpus of meeting transcripts, with an honest evaluation of where retrieval genuinely helps versus where simpler approaches work just as well.

The choice to build this over the other options (code documentation assistant, career intelligence, chat with docs) was deliberate. Meeting intelligence is directly applicable to the kinds of regulated enterprise environments (pharma, healthcare, financial services) where the architecture needs to handle: data residency concerns, structured data extraction for compliance, and cross-temporal reasoning across long document histories.

---

## 2. Scope and Goals

### Goals

1. Deliver a working, demonstrable RAG pipeline end-to-end that can be run from a fresh clone
2. Implement multiple retrieval strategies and make their differences **visible and measurable**, not just theoretical
3. Demonstrate when RAG is and isn't the right tool — the query router and cross-check evaluation both address this
4. Show that the codebase is something a team could build on: typed, tested, containerised, documented
5. Communicate trade-offs honestly — no hand-waving about what was skipped

### Explicitly Out of Scope (Prototype)

- **Real-time transcription during live meetings** — batch ingestion only
- **Meeting scheduling, calendar, or workflow integration** — pure analysis
- **Speaker identification from voice** — we use diarization labels, not voice fingerprinting
- **Fine-tuning models on meeting content** — retrieval is the right tool for instance recall; fine-tuning is for domain adaptation
- **Multi-tenant SaaS with billing and row-level isolation** — auth and data isolation are production concerns documented in the roadmap, not implemented here

### Non-Goals

- Perfect UI/UX — Streamlit is intentionally thin
- Handling every edge case in transcript parsing — acknowledged in code comments
- The "best possible" RAG system — the goal is a well-reasoned one with visible, explainable decisions

---

## 3. Users

### Primary: The Assessor / Technical Reviewer

**What they want:** Evidence that the engineer demonstrates lead-level thinking — not just the ability to wire together API calls, but the ability to make architectural decisions, understand trade-offs, evaluate outcomes, and communicate all of it clearly.

**How they'll engage:** Read the README and docs first, then clone and run. They'll upload a transcript, ask a question, toggle the strategy selector, compare the retrieved chunks, and look at the evaluation output.

### Secondary (Production Persona): The Knowledge Worker

**Who:** A project manager, team lead, or analyst at an organisation with 3+ months of recorded meetings.

**Core need:** "I know we discussed X six weeks ago — who said it, what was decided, and does it conflict with the decision we made last week?"

**Current frustration:** They search Slack, skim meeting notes that were never written, or simply give up and re-litigate decisions that were already made.

**What they'd value:** Searchable, attributed answers across their entire meeting history — without needing to know which meeting to look in.

### Tertiary (Production Persona): The AI/Data Engineer at a Consultancy

**Who:** Someone building this type of system for a life sciences or professional services client.

**What they need:** A reference implementation — chunking patterns, hybrid search, query routing, evaluation framework — that can be adapted to clinical call notes, regulatory meeting records, or board minutes without rebuilding from scratch.

**Why this matters for the design:** The architecture prioritises readability and modularity over brevity. The strategy toggle system is designed to be extended, not just toggled. This is deliberate.

---

## 4. Functional Requirements

### 4.1 Ingestion

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F01 | Accept plain text transcript files (.txt) with speaker labels | Must | ✅ Done |
| F02 | Accept WebVTT format (.vtt) with timestamps | Must | ✅ Done |
| F03 | Accept AssemblyAI JSON format with speaker diarization | Must | ✅ Done |
| F04 | Accept MeetingBank JSON format | Must | ✅ Done |
| F05 | Transcribe audio files (.mp3, .wav, .m4a) via AssemblyAI | Should | ❌ Broken — binary input crashes ingest endpoint; Issue #22 |
| F06 | Parse and normalise all formats to a uniform `TranscriptSegment` structure | Must | ✅ Done |
| F07 | Extract meeting-level metadata (title, speakers, duration) on ingest | Must | ✅ Done |

**Note on F05:** The `assemblyai` package is a dependency and AssemblyAI is configured, but the current ingest endpoint calls `.decode("utf-8")` on binary file content, crashing immediately for audio. Two options are being evaluated: implement the transcription flow properly, or remove audio file types from the UI and document this as a roadmap item. Either is preferable to the current silent crash.

### 4.2 Chunking

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F08 | Naive fixed-size chunking with configurable token window and overlap | Must | ✅ Done |
| F09 | Speaker-turn chunking: one chunk per continuous speaker segment, capped at a configurable max | Must | ✅ Done |
| F10 | All chunks preserve speaker label, timestamp range, meeting reference, and chunk index | Must | ✅ Done |
| F11 | Chunking strategy configurable at ingest time via `PipelineConfig` | Must | ✅ Done |

### 4.3 Embedding and Storage

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F12 | Embed chunks using OpenAI `text-embedding-3-small` (1536 dimensions) | Must | ✅ Done |
| F13 | Store embeddings in Supabase pgvector with HNSW index for fast cosine search | Must | ✅ Done |
| F14 | Maintain a full-text search (GIN/tsvector) index alongside the vector index | Must | ✅ Done |
| F15 | Track which embedding model produced each chunk's vector | Should | 🔲 Planned — Issue #21 |
| F16 | Support configurable embedding model via LiteLLM abstraction | Should | 🔲 Planned — Issue #21 |

### 4.4 Retrieval

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F17 | Semantic retrieval using vector cosine similarity | Must | ✅ Done |
| F18 | Hybrid retrieval: vector similarity + full-text scoring, combined with configurable weights | Must | ✅ Done |
| F19 | Filter retrieval by meeting ID, speaker label, or date range | Should | ✅ Done |
| F20 | Return similarity scores with each retrieved chunk | Must | ✅ Done |
| F21 | Configurable top-K retrieval count | Should | ✅ Done |
| F22 | Cross-encoder reranking as optional post-retrieval stage | Could | 🔲 Not started — documented in architecture |

### 4.5 Query Routing

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F23 | Detect whether a query is structured ("list all action items") vs open-ended ("what was discussed about X") | Must | ✅ Done |
| F24 | Route structured queries to direct database lookup — not through RAG | Must | ✅ Done |
| F25 | Route open-ended queries through the full RAG retrieval and generation pipeline | Must | ✅ Done |

**Design note on F23–F25:** This is one of the more important architectural decisions in the system. It demonstrates understanding that RAG is not universally the right tool. Structured queries for known entities (action items with assignees, decisions with dates) are better served by direct SQL than by probabilistic retrieval. The router makes this distinction explicit rather than routing everything through the vector pipeline.

### 4.6 Generation

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F26 | Generate answers using Claude with retrieved context injected | Must | ✅ Done |
| F27 | Include source attribution in every answer (speaker, timestamp, meeting) | Must | ✅ Done |
| F28 | Configurable system prompt for answer style and guardrails | Must | ✅ Done |
| F29 | Handle queries that span multiple meetings | Should | ✅ Done |
| F30 | Handle no-results queries gracefully — decline rather than hallucinate | Must | ✅ Done |
| F31 | Configurable LLM model via `PipelineConfig` (LiteLLM abstraction) | Should | 🔲 Planned — Issue #20 |

### 4.7 Structured Extraction

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F32 | Extract action items from a meeting (who, what, target date) | Should | ✅ Done |
| F33 | Extract key decisions from a meeting | Should | ✅ Done |
| F34 | Extract key topics discussed | Should | ✅ Done |
| F35 | Extraction uses the full transcript as context — direct LLM call, not RAG | Must | ✅ Done |
| F36 | Extracted items stored in database | Must | ✅ Done |
| F37 | Extracted items surfaced in the meeting detail view | Should | ⚠️ Partial — DB storage works; UI field name mismatches prevent display (Issue #24) |

**Design note on F35:** Extraction from a single known document is better handled by direct LLM call than by retrieval. The transcript is small enough to fit in context, and you want the model to see the complete picture. This is an explicit design choice, not a shortcut — and it's in the same category as the query routing decision above.

### 4.8 Evaluation

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F38 | Auto-generate Q&A test set from MeetingBank reference summaries using Claude | Must | ✅ Done — generator implemented |
| F39 | Evaluate answer quality using Claude-as-judge: faithfulness, answer relevancy, context precision/recall | Must | ✅ Done — metrics implemented |
| F40 | Strategy comparison: run evaluation across all chunking × retrieval combinations | Must | ✅ Done — comparison logic implemented |
| F41 | Cross-check: run the same questions through RAG and full-transcript context-stuffing, compare results | Should | ✅ Done — cross-check implemented |
| F42 | Functional evaluation runner that can be executed end-to-end | Must | ❌ Broken — `runner.py` has no `__main__` entry point; Issue #23 |
| F43 | Actual evaluation results saved to `reports/` | Must | 🔲 Blocked by F42 |

**Note on evaluation approach:** The implementation uses Claude-as-judge rather than the RAGAS or DeepEval libraries. This was a deliberate choice: Claude-as-judge is more flexible for domain-specific quality criteria, requires no additional frameworks, and produces more interpretable output. The README currently (incorrectly) claims "RAGAS + DeepEval metrics" — this needs to be corrected as part of Issue #23.

### 4.9 API

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F44 | `POST /ingest` — upload and process a transcript file | Must | ✅ Done |
| F45 | `POST /query` — ask a natural language question, get attributed answer | Must | ✅ Done |
| F46 | `GET /meetings` — list all ingested meetings | Must | ✅ Done |
| F47 | `GET /meetings/{id}` — meeting detail including extracted items | Should | ✅ Done |
| F48 | `POST /meetings/{id}/extract` — run structured extraction on a meeting | Should | ✅ Done |
| F49 | Duplicate GET `/meetings/{id}/extract` endpoint removed | Must | ❌ Not done — Issue #25; currently returns malformed response |
| F50 | Strategy configurable per request via request body | Should | ✅ Done |
| F51 | OpenAPI docs available at `/docs` | Should | ✅ Done (FastAPI default) |

### 4.10 UI

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F52 | Upload tab: transcript file upload with progress feedback | Must | ✅ Done |
| F53 | Chat tab: question input, answer display with source citations | Must | ✅ Done |
| F54 | Meetings browser: list meetings, click to see detail and extracted items | Should | ⚠️ List works; detail view broken due to field name mismatches (Issue #24) |
| F55 | Strategy selector in sidebar: toggle chunking and retrieval strategies | Should | ✅ Done |
| F56 | Audio upload flow with AssemblyAI transcription | Should | ❌ Broken — crashes on binary input (Issue #22) |

### 4.11 Infrastructure

| ID | Requirement | Priority | Phase 1 Status |
|----|-------------|----------|----------------|
| F57 | Docker Compose: single command brings up api + ui services | Must | ✅ Done |
| F58 | GitHub Actions CI: runs ruff, mypy, pytest on every push | Must | ✅ Done — added in PR #28 (Issue #25) |
| F59 | Pre-commit hooks: ruff format + ruff check | Should | ✅ Done |
| F60 | MeetingBank data loadable via `scripts/load_meetingbank.py` | Must | ⚠️ Script done; 30 JSON files downloaded; not yet loaded into live Supabase (Issue #26) |
| F61 | Type checking passes cleanly (`mypy src/`) | Must | ❌ 218 pre-existing type errors — Issue #30 |

---

## 5. Non-Functional Requirements

### Reliability
- The system produces consistent answers for the same query + strategy configuration
- Retrieval degrades gracefully when no relevant context exists: the model says "I don't know from the provided transcripts" rather than fabricating an answer
- External API calls (Claude, OpenAI, AssemblyAI, Supabase) all have error handling and surface failures clearly

### Observability
- Every pipeline step logs timing information
- Retrieval results include similarity scores in the API response
- API errors return structured responses with enough detail to debug without log access

### Testability
- Core pipeline logic (chunking, embedding, retrieval) is unit-testable without live API calls
- Expensive API-calling tests marked `@pytest.mark.expensive` and excluded by default
- 108 tests currently passing across unit and integration levels

### Portability
- Environment variables control all external service configuration — no hardcoded values
- `.env.example` documents every required key
- `docker compose up` from a fresh clone is the intended setup path

### Maintainability
- Type hints required throughout (mypy strict mode — currently 218 errors to resolve)
- Ruff for linting and formatting (currently passing cleanly)
- `CLAUDE.md` ensures any AI coding session understands the project constraints
- Strategy patterns are extensible — adding a new chunking strategy means implementing one interface, not changing call sites throughout the codebase

---

## 6. MVP Scope (Phase 1 — Prototype)

The MVP is a functional prototype demonstrating the core value proposition and all key architectural decisions. It is explicitly not a production system.

### What Phase 1 Delivers

1. **Working end-to-end pipeline** — upload transcript → chunk → embed → store → retrieve → answer with attributed citations
2. **Visible strategy differences** — toggle between naive and speaker-turn chunking, and semantic vs hybrid retrieval, and observe different chunks being retrieved for the same query
3. **Query routing** — structured queries go to the database directly; open-ended queries go through RAG; this is an explicit design choice with a clear rationale
4. **Structured extraction alongside RAG** — action items, decisions, and topics extracted by direct LLM call with the full transcript in context
5. **Evaluation infrastructure** — test set generation, Claude-as-judge metrics, cross-check logic, and strategy comparison all implemented (runner needs fixing to produce actual results)
6. **Production-aware documentation** — what would change for production is documented explicitly, not glossed over

### What Phase 1 Explicitly Defers

- **Audio transcription UI** — AssemblyAI is configured but the upload flow crashes on binary input; being fixed or removed
- **Actual evaluation results** — the framework is built; the runner entry point needs fixing; results will be generated once that's resolved
- **LLM and embedding model configurability** — hardcoded to Claude + OpenAI for now; LiteLLM abstraction planned for Phase 2
- **Clean type checking** — 218 mypy errors identified; fixing them is the current priority (Issue #30)
- **Cross-encoder reranking** — discussed in architecture documentation; not implemented
- **Auth and data isolation** — deliberate exclusion from prototype; documented in production roadmap

### Honest Assessment of Current State

The codebase is functional but has several known issues that are explicitly tracked as open GitHub issues. These are not hidden: they were identified through a systematic post-implementation audit and documented publicly. The approach throughout has been to build things that work and acknowledge things that don't — a partially implemented feature that crashes is worse than a well-documented gap.

The most significant outstanding item is the evaluation runner (Issue #23). The framework is there; generating actual numbers is the next immediate priority.

---

## 7. Phase 2 Roadmap

These are engineering decisions with concrete rationale — not aspirational padding.

### P2.1 — LiteLLM Model Abstraction (Issues #20, #21)

Replace direct Anthropic and OpenAI SDK calls with LiteLLM, enabling model comparison as a first-class feature. This unlocks: comparing GPT-4o vs Claude on generation quality for the same retrieved context, testing open-source models (Llama 3, Mixtral via HuggingFace) for cost-sensitive or data-residency-constrained deployments, and embedding model evaluation (Cohere embed-v3, Voyage AI voyage-3, sentence-transformers).

The embedding model change is harder than it sounds — different models produce incompatible vector spaces, different dimensions, and re-embedding requires dropping and rebuilding the HNSW index. Issue #21 documents the full migration approach.

### P2.2 — Evaluation Results and Reporting

Fix the runner entry point, run the full test set against all strategy combinations, and publish results in `reports/`. The infrastructure is all there; this is about getting real numbers to back up the architectural narrative.

### P2.3 — Cross-Encoder Reranking

Add an optional post-retrieval reranking step using a cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`). Reranking reorders the top-K retrieved chunks by the actual query-chunk pair relevance, not just embedding similarity. This is particularly valuable when queries are long or multi-part, and when the corpus has many topically similar chunks from different meetings.

### P2.4 — Production Hardening for Enterprise Deployment

For a deployment serving a life sciences team:
- **Frontend:** Replace Streamlit with a proper frontend (React/Next.js or similar). Streamlit is a great prototyping tool and a poor production UI.
- **Auth + data isolation:** JWT authentication with Supabase RLS policies. Each user or team should only see their own meeting data.
- **Transcription:** Replace AssemblyAI with self-hosted WhisperX + pyannote for data residency. In pharma/healthcare, you cannot send meeting audio to a third-party SaaS without a DPA at minimum, and often without on-premise processing.
- **Observability:** Structured JSON logging, OpenTelemetry traces, Prometheus metrics on retrieval latency and quality. Without this, you cannot diagnose why a query returned the wrong answer.
- **Caching:** Redis for query result caching. The same question gets asked repeatedly in any team context; caching cuts both latency and cost significantly.
- **Cost controls:** Token usage tracked per query and per user. An unconstrained RAG system can become expensive quickly if queries retrieve large chunks with generous context windows.

### P2.5 — Agentic Extraction Pipeline

The current extraction is a single LLM call. A multi-step agent would: identify action items, validate assignees against a confirmed speaker list, cross-reference with action items from previous meetings to detect repetition or contradiction, and flag items without clear deadlines or owners. This is where the extraction pipeline would go in a production system that needs to track accountability over time.

### P2.6 — Enterprise Transcript Source Adapters

The current pipeline accepts uploaded text files. With thin adapters for Teams Graph API, Zoom meeting cloud recordings API, and Google Meet transcription exports, the same pipeline works on actual enterprise meeting data without modifying the core retrieval or generation logic. This is what makes the architecture reusable rather than a one-off demo.

---

## 8. Success Metrics

### For the Prototype

- All must-priority functional requirements implemented and working
- `docker compose up` from a fresh clone succeeds in under 2 minutes
- Can load MeetingBank sample data and answer cross-meeting questions correctly
- Strategy toggle produces visibly different retrieved chunks for the same query
- Evaluation framework produces interpretable output
- No unhandled crashes in the main user flows

### For a Production Deployment

- P95 query latency < 3 seconds end-to-end (retrieval + generation)
- Faithfulness > 0.85 on held-out test set (answers stay within retrieved context)
- Context precision > 0.75 (retrieved chunks are relevant to the query)
- Zero PII leakage incidents across meeting data (requires auth + RLS)
- System handles 50 concurrent users without latency degradation

---

## 9. Open Questions and Decisions Log

| Question | Decision | Date |
|----------|----------|------|
| Which assignment option to build? | Option 3 (Meeting Intelligence) — lower execution risk, explicitly rewards audio bonus, most applicable to Newpage's regulated industry clients | 2026-02-17 |
| Use LangChain/LlamaIndex or direct SDKs? | Direct SDKs — want every pipeline step to be explicit code, not hidden in abstractions. Easier to explain, easier to extend, aligns with understanding what's happening under the hood | 2026-02-17 |
| Which vector database? | Supabase pgvector — single database for vectors + metadata + full-text search. Hybrid search comes free with Postgres. No separate vector DB to manage. At production scale, would evaluate dedicated vector store. | 2026-02-17 |
| Evaluation approach: library or Claude-as-judge? | Claude-as-judge — more flexible for domain-specific quality criteria, no additional dependencies, interpretable output. RAGAS/DeepEval would be appropriate for a longer-running project with more standardised benchmarks. | 2026-02-18 |
| Context-stuffing vs RAG for single meetings? | Explicit cross-check evaluation addresses this. For a single meeting, context-stuffing is often better. The system makes this visible rather than hiding it. | 2026-02-18 |
| Query routing: RAG for everything vs router? | Router — structured queries for known entities (action items, decisions) go directly to the database. More accurate, faster, and cheaper than running structured queries through a probabilistic retrieval pipeline. | 2026-02-18 |
