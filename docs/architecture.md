# Architecture — Meeting Intelligence

**Last updated:** 2026-02-19

This document explains the key architectural decisions in this system: what was chosen, what was considered, what was deliberately not chosen, and why. The decisions here were made under time constraints with a prototype goal — the production implications of each are noted separately.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Streamlit UI                             │
│     Upload │ Chat │ Meetings browser │ Strategy sidebar          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP (JSON)
┌─────────────────────────▼───────────────────────────────────────┐
│                        FastAPI Backend                           │
│                                                                  │
│  POST /ingest    POST /query    GET /meetings    POST /extract   │
│                                                                  │
│  ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐  │
│  │  Ingestion   │   │  Query Router  │   │   Extraction     │  │
│  │  Pipeline    │   │                │   │   (direct LLM)   │  │
│  └──────┬───────┘   └───────┬────────┘   └──────────────────┘  │
│         │                   │                                    │
│         │            structured?──────────────────────────────┐ │
│         │                   │ no                              │ │
│         │           ┌───────▼────────┐                        │ │
│         │           │  RAG Pipeline  │                        │ │
│         │           │  retrieve→gen  │                        │ │
│         │           └───────┬────────┘                        │ │
└─────────┼───────────────────┼────────────────────────────┐    │ │
          │                   │                             │    ▼ │
┌─────────▼───────────────────▼─────────────────────────┐  │  ┌──▼─────┐
│                    Supabase (Postgres)                  │  │  │ DB     │
│                                                         │  │  │ direct │
│  meetings table    chunks table    extracted_items       │  │  │ query  │
│  (metadata)        (halfvec 1536   (action items,       │◄─┘  └────────┘
│                     + tsvector)     decisions,
│                                     topics)
│                                                         │
│  HNSW index (cosine similarity)                         │
│  GIN index (full-text search)                           │
│  match_chunks() — vector search function                │
│  hybrid_search() — combined vector + FTS function       │
└─────────────────────────────────────────────────────────┘
          │                   │
          │                   │
   ┌──────▼──────┐    ┌───────▼──────────┐
   │  OpenAI     │    │   Claude API     │
   │  Embeddings │    │  (Generation +   │
   │  (1536d)    │    │   Extraction +   │
   └─────────────┘    │   Evaluation)    │
                      └──────────────────┘
```

---

## 1. Single Database Architecture (Supabase + pgvector)

### Decision

Use Supabase (Postgres + pgvector) as the single data store for:
- Meeting metadata and raw transcripts
- Chunk text + speaker/timestamp metadata
- Vector embeddings (halfvec 1536)
- Full-text search indices (tsvector)
- Extracted structured items (action items, decisions, topics)

### Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **Qdrant** | Native vector operations, built-in filtering, fast | Separate DB to manage; need Postgres or SQLite for relational data; no MCP access for debugging |
| **Pinecone** | Managed, fast, metadata filtering | Expensive at scale; another external service; still need relational DB alongside |
| **Chroma** | Simple, local, no setup | Not production-grade; no hybrid search; poor Python async support |
| **Weaviate** | Hybrid search built-in | Complex setup; steep learning curve; overkill for this scale |
| **Supabase (chosen)** | Hybrid search with Postgres FTS; one DB for everything; MCP access for debugging; HNSW indexing via pgvector | pgvector has dimension limits; at very high scale, dedicated vector DB is faster |

### Why This Matters

Using Supabase means the hybrid search query (vector similarity + full-text) runs as a single SQL function, not as two queries that need result-merging in application code. This is simpler, faster, and easier to reason about. The `hybrid_search()` Postgres function combines both signals with configurable weights:

```sql
combined_score = (vector_score × vector_weight) + (text_score × text_weight)
```

Default weights: 70% vector, 30% full-text. Tunable per query type — keyword-heavy queries benefit from more text weight.

### Production Note

At scale (1M+ chunks), pgvector's HNSW index performance degrades and dedicated vector databases (Qdrant, Pinecone, Weaviate) become worth the operational overhead. The migration path is clear: the `chunks` table structure maps directly to a Qdrant collection schema. The application layer (retrieval functions) is the only thing that needs updating.

---

## 2. Direct SDK Calls vs Orchestration Frameworks

### Decision

Use direct Anthropic and OpenAI SDK calls. No LangChain. No LlamaIndex.

### Reasoning

Orchestration frameworks are valuable for teams who want to move fast on standard RAG patterns. They are a liability when you want to understand, measure, and modify what's happening at each stage. For this project specifically:

1. **The strategy toggle system requires full control.** Swapping chunking and retrieval strategies means instrumenting each stage independently. LangChain chains abstract this away — you'd need to hook into internals to measure the impact of a strategy change.

2. **The evaluation framework requires transparency.** Measuring faithfulness and context precision requires knowing exactly what context was passed to the generation step. Framework abstractions often obscure this.

3. **It's more honest as a lead-level demonstration.** Anyone can wire together LangChain components. Understanding what's happening under the hood — how the embedding call works, how the similarity function is computed, what the prompt structure looks like — is what differentiates a lead engineer from a framework integrator.

4. **Debugging is dramatically easier.** When a query returns the wrong answer, you can trace the exact context passed to Claude, the exact similarity scores, the exact chunks. With a framework, you're debugging the framework's internals.

### The Trade-off

Direct SDK calls mean more code. The retrieval and generation layers are explicit. For a one-person prototype on a deadline, frameworks are faster. For a codebase that a team will build on and modify, explicitness wins.

### Production Note

In a production CoE context, LiteLLM is worth adding as a thin model abstraction layer — it provides a unified API across providers without hiding the actual call structure. Issue #20 tracks this. LiteLLM is the right tool; LangChain at the orchestration level is not.

---

## 3. Chunking Strategy Design

### Two Strategies, Different Trade-offs

**Naive fixed-size chunking:**
- Split transcript text into overlapping windows (default: 500 tokens, 50 token overlap)
- Simple, fast, reproducible
- Problem: a single chunk often contains multiple speakers and half-finished thoughts, which dilutes semantic coherence

**Speaker-turn chunking:**
- One chunk per continuous speaker segment
- Preserves semantic coherence — each chunk represents a single person's complete thought
- Better for attribution queries ("what did Sarah say about X?")
- Problem: speaker turns vary wildly in length; a very long turn may exceed useful context for retrieval; short turns may have insufficient context to embed meaningfully

The system supports both, stored separately with a `strategy` column on the `chunks` table. Both versions of a meeting are stored simultaneously, so strategy comparisons don't require re-ingestion.

### Why This Matters for Meeting Data

Meeting transcripts have a property that makes chunking harder than standard documents: **speaker attribution is semantically load-bearing**. The question "what did the CTO commit to?" depends on which speaker said what. Naive chunking can put the commitment and the speaker label in different chunks. Speaker-turn chunking keeps them together.

This is a specific advantage of the Meeting Intelligence use case over generic RAG — the data has natural semantic boundaries (speaker turns) that a smarter chunking strategy can exploit.

---

## 4. Hybrid Search Implementation

### How It Works

Both a vector search and a full-text search run in parallel within a single Postgres function. Results are merged using a weighted combination of scores:

```sql
combined_score = (cosine_similarity × 0.7) + (ts_rank × 0.3)
```

Full-text search catches exact keyword matches that semantic search might miss — especially for proper nouns (names, project names, product names), technical terms, and short, specific phrases. Semantic search catches paraphrases and conceptually related content that keyword matching would miss.

### When Each Signal Dominates

- **"What did Janet say about the Q3 forecast?"** — Semantic search surfaces topic-relevant chunks; full-text catches "Janet" and "Q3" precisely.
- **"Budget concerns"** — Semantic search works well; keyword matching also helps for "budget" appearing verbatim.
- **"What was discussed in the meeting with McKinsey?"** — Full-text matching on "McKinsey" is essential; semantic alone might not surface meeting-specific proper nouns reliably.

### Production Note

The current hybrid weights (70/30) are defaults that haven't been tuned against evaluation data. With the evaluation framework working, it would be straightforward to grid-search over weight combinations and report the optimal setting for different query categories (factual, temporal, attribution, exploratory).

---

## 5. Query Routing: When Not to Use RAG

### The Decision

Not everything goes through the vector retrieval pipeline. A query router classifies each incoming query and directs it to the appropriate handler:

```
"List all action items assigned to James"
  → structured query → direct database lookup on extracted_items table
  → Result: fast, precise, no retrieval uncertainty

"What was the team's concern about the timeline?"
  → open-ended query → full RAG pipeline
  → Result: semantically retrieved chunks → Claude generation with attribution
```

### Why This Matters

This is arguably the most important design decision in the system for demonstrating lead-level thinking. RAG is a tool, not a solution. When the answer is a structured fact (an action item with an assignee, a decision that was recorded) that was extracted and stored at ingest time, retrieving it from a vector index is:
- Slower (embedding + vector search + LLM generation vs direct SQL)
- Less accurate (probabilistic retrieval vs exact match)
- More expensive (token cost for generation)

The failure mode is common: engineers learn RAG and route everything through it, including queries that should hit a database directly. A lead engineer knows the boundary.

### Implementation

The router uses a simple prompt classification (Claude-based) that determines whether a query is asking for structured data or open-ended exploration. In production, a fine-tuned classifier or a few-shot prompt trained on labelled query examples would be more reliable than a general-purpose LLM call for routing.

---

## 6. Structured Extraction: Direct LLM Call

### Decision

Extract action items, decisions, and key topics by passing the full meeting transcript to Claude with a structured output prompt using `tool_use`. This is a direct call, not RAG.

### Why Not RAG for Extraction

For extraction from a single document you already have:
1. The document fits in context (a typical meeting transcript is 5,000–40,000 tokens, well within Claude's 200K window)
2. You want the model to see the complete picture — an action item assigned in the first five minutes might only have its deadline mentioned in the last five minutes
3. Retrieval uncertainty adds noise; you want deterministic structured extraction

### The Pattern: `tool_use` for Structured Output

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=[action_item_tool, decision_tool, topic_tool],
    tool_choice={"type": "any"},
    messages=[{"role": "user", "content": transcript_text}]
)
```

Claude is forced to return structured JSON matching the tool schema, not free-form text. This gives you reliably parseable output without post-processing fragility.

### Production Note

For very long meetings (3+ hours), the transcript may exceed a comfortable context window. A sliding window approach — extract from overlapping segments and merge results — would handle this. The current implementation assumes meetings fit in context, which is true for the MeetingBank dataset used here.

---

## 7. Evaluation Architecture

### Approach: Claude-as-Judge

The evaluation framework uses Claude to assess the quality of answers produced by the RAG pipeline. Three metrics are evaluated per question:

- **Faithfulness:** Does the answer contain only claims that are supported by the retrieved chunks? (Hallucination detection)
- **Answer relevancy:** Does the answer actually address what was asked?
- **Context precision/recall:** Are the retrieved chunks relevant to the query? Were relevant chunks missed?

### Why Claude-as-Judge vs RAGAS/DeepEval

RAGAS and DeepEval are good frameworks. For a project with a longer runway and a need for standardised benchmarks, they'd be the right choice. For this prototype:
- Claude-as-judge is more flexible for meeting-specific quality criteria
- No additional library dependencies
- The evaluation logic is explicit Python code that can be inspected and modified
- Output is interpretable: the judge explains its reasoning, not just a score

The current README incorrectly claims "RAGAS + DeepEval metrics" — this is being corrected. The actual implementation is a Claude-as-judge approach that produces equivalent metrics.

### Cross-Check Evaluation

One of the more valuable features of the evaluation framework is the cross-check: every question in the test set is answered twice — once through RAG, once by passing the full meeting transcript directly to Claude (context-stuffing). The results are compared to categorise each question:

- **RAG wins:** The retrieved chunks contain enough context; the full transcript introduces noise that confuses the answer
- **Context-stuffing wins:** The answer requires holistic understanding of the meeting that retrieval misses
- **Equivalent:** Both approaches perform similarly

For a corpus of 50+ meetings, RAG is necessary. For queries about a single known meeting, context-stuffing is often better. This evaluation makes that visible with real numbers rather than hand-waving.

---

## 8. What Would Change for Production

This is not a complete production checklist — it's the decisions that would materially change the architecture, not just the configuration.

### Transcription

Replace AssemblyAI with self-hosted **WhisperX + pyannote**. In regulated industries (pharma, healthcare, financial services), sending meeting audio to a third-party SaaS requires a Data Processing Agreement at minimum and is often prohibited for sensitive discussions. Self-hosting gives you: data residency, better speaker diarization control, and per-word timestamps for finer-grained chunk attribution.

Cost trade-off: AssemblyAI at $0.37/hour of audio vs WhisperX on a GPU instance at ~$0.10/hour (GPU rental). The privacy argument is more compelling than the cost argument.

### Frontend

Replace Streamlit with a proper web frontend. Streamlit is excellent for prototypes — one file, instant UI, great for data exploration. It's not suitable for production because: it reruns the entire script on each interaction, session state is fragile, it's not designed for concurrent users, and the UX ceiling is low.

### Observability

Add OpenTelemetry instrumentation to trace each pipeline step. For a production RAG system, you need to know: which retrieval results were used, what context was injected, how long each stage took, and when the model declined to answer versus when it fabricated. Without this, diagnosing quality issues is guesswork.

Langfuse is a strong choice for LLM observability specifically — it captures prompt, completion, token counts, and cost in a queryable UI.

### Model Choice

The current system is hardcoded to Claude Sonnet for generation and `text-embedding-3-small` for embeddings. In a production context, this should be configurable:
- Different tasks may be better served by different models (Haiku for classification, Sonnet for generation, Opus for complex reasoning)
- Embedding model choice affects retrieval quality more than LLM choice does for most queries
- Open-source embedding models (sentence-transformers, E5, Voyage AI) enable data residency for the embedding step

Issue #20 (LiteLLM) and Issue #21 (configurable embeddings) address this.

### Caching

Add Redis for query result caching. In any team context, the same question gets asked repeatedly. A 24-hour TTL cache on (query_hash, strategy_config) tuples cuts both latency and API cost significantly. Cache invalidation happens when new meetings are ingested.

### Auth and Data Isolation

Supabase Row Level Security (RLS) policies enforce that users only see their own meeting data. Combined with JWT authentication, this is the primary security control for a multi-tenant deployment. Currently there is no auth at all — appropriate for a prototype, not for any real deployment.
