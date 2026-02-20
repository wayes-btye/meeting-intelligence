# How It Works — Step by Step

## What happens when you upload a transcript

```
You click "Upload" in Streamlit
         │
         ▼
┌─────────────────────────────┐
│  Streamlit (UI)             │
│  Sends file + title +       │
│  chunking_strategy to API   │
└────────────┬────────────────┘
             │  HTTP POST /api/ingest
             ▼
┌─────────────────────────────┐
│  FastAPI (ingest endpoint)  │
│  1. Reads file bytes        │
│  2. Decodes as UTF-8 text   │
│  3. Detects format (.vtt)   │
│  4. Calls ingest_transcript │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Pipeline                   │
│                             │
│  PARSE: .vtt file →         │
│    8 segments with speaker, │
│    text, timestamps         │
│                             │
│  CHUNK: strategy decides    │
│    how to split the text    │
│    (see below)              │
│                             │
│  EMBED: sends chunk text    │  ──→  OpenAI API
│    to OpenAI, gets back     │  ←──  1536-dim vector
│    a 1536-number vector     │
│                             │
│  STORE: writes to Supabase  │  ──→  Supabase
│    meetings table (metadata)│       (Postgres)
│    chunks table (text +     │
│    embedding + speaker)     │
└─────────────────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Response back to Streamlit │
│  meeting_id: 59a7cad1-...   │
│  num_chunks: 1              │
└─────────────────────────────┘
```

## Chunking strategies explained

### Naive chunking
Takes all the text from every speaker, concatenates it into one long string, then chops it into fixed-size pieces (default 500 words per chunk, 50-word overlap between chunks). Speakers are ignored — a chunk might contain text from multiple speakers cut mid-sentence.

For a small file (< 500 words), you get 1 chunk with everything in it. Speaker info is lost.

### Speaker-turn chunking
Groups consecutive segments by the same speaker. Each speaker turn becomes its own chunk, preserving who said what. If a single speaker talks for more than 500 words, their turn gets split into multiple chunks.

For the sample.vtt (8 segments, 4 speakers), you get 8 chunks — each with a named speaker.

## What is an embedding?

An embedding is a list of 1536 numbers (a "vector") that represents the *meaning* of a piece of text. Similar meanings produce similar numbers.

Example:
- "budget concerns" → [0.12, -0.34, 0.56, ...]
- "financial worries" → [0.11, -0.33, 0.55, ...]  (very similar numbers)
- "pizza recipes" → [-0.89, 0.22, -0.01, ...]  (very different numbers)

When you ask a question, your question gets embedded too, and Supabase finds chunks whose vectors are mathematically closest to your question's vector. That's **semantic search** — matching by meaning, not just keywords.

## What happens when you ask a question

```
You type a question in the UI
         │
         ▼
┌─────────────────────────────┐
│  Query Router               │
│  Is this a structured       │
│  question? (action items,   │
│  decisions, topics)         │
└──────┬──────────┬───────────┘
       │          │
   Structured   Open-ended
       │          │
       ▼          ▼
┌──────────┐  ┌──────────────────┐
│ DB lookup │  │ RAG Pipeline     │
│ extracted │  │ 1. Embed question│ ──→ OpenAI
│ _items    │  │ 2. Search chunks │ ──→ Supabase
│ table     │  │ 3. Send chunks + │
│           │  │    question to   │ ──→ Claude
│           │  │    Claude        │
│           │  │ 4. Return answer │
│           │  │    with sources  │
└──────────┘  └──────────────────┘
```

## Retrieval strategies

### Semantic search
Finds chunks by vector similarity only — "what text means the same thing as the question?"

### Hybrid search
Combines vector similarity (70% weight) with keyword matching (30% weight). Better for specific terms like names, numbers, or jargon that might not have strong semantic similarity but are exact keyword matches.

## How to check things manually

### Supabase Dashboard
1. Go to https://supabase.com/dashboard → your project
2. Click **Table Editor** in the left sidebar
3. `meetings` — uploaded meetings with metadata
4. `chunks` — text pieces with embeddings, speaker, strategy
5. `extracted_items` — action items, decisions, topics (populated after calling extract endpoint)

### API Swagger docs
Open http://localhost:8000/docs — interactive UI where you can try every endpoint directly.

### Key API endpoints
| Endpoint | What it does |
|----------|-------------|
| `GET /health` | Check API is running |
| `POST /api/ingest` | Upload a transcript |
| `POST /api/query` | Ask a question |
| `GET /api/meetings` | List all meetings |
| `GET /api/meetings/{id}` | Full meeting detail with chunks |
| `POST /api/meetings/{id}/extract` | Extract action items, decisions, topics |
