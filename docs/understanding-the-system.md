# Understanding the System

This document explains what happens under the hood when you use Meeting Intelligence —
what each number means, why results look the way they do, and where to check things yourself.

---

## What happened when you asked "What concerns were raised about the budget?"

Here is the exact sequence, step by step:

### Step 1: Query routing

The system first checks: is this a **structured** question (asking for action items, decisions,
topics) or an **open-ended** question?

Your question "what concerns were raised about the budget?" is open-ended, so it goes through
the **RAG pipeline** (not the DB lookup path).

### Step 2: Embed your question (OpenAI)

Your question gets sent to OpenAI's embedding API and comes back as a list of 1,536 numbers:

```
"what concerns were raised about the budget?"
    → [0.0296, 0.0044, 0.0771, 0.0061, -0.0096, ... 1,531 more numbers]
```

This is the same thing that happened when your transcript was uploaded — each chunk of text
was turned into 1,536 numbers. The key idea: **text with similar meaning produces similar
numbers.**

### Step 3: Search Supabase for similar chunks (vector search)

Your question's vector is sent to Supabase, which compares it against every chunk's vector
using **cosine similarity**. This is a mathematical formula that measures how "close" two
vectors are, on a scale from 0 to 1.

Supabase returned all 8 chunks from your meeting, ranked by similarity:

| Rank | Similarity | Speaker | What they said (abbreviated) |
|------|-----------|---------|-----|
| #1 | **0.5649** | Mayor Johnson | "These are valid concerns. I suggest we table the budget vote..." |
| #2 | **0.5527** | Council Member Davis | "I've reviewed the budget proposal and I have some concerns..." |
| #3 | **0.4068** | Council Member Park | "I agree with Council Member Davis. We should also consider the environmental..." |
| #4 | 0.3711 | Mayor Johnson | "Motion carries. Let's move to the first agenda item - the proposed bud..." |
| #5 | 0.2512 | Mayor Johnson | "We have a motion on the floor. All in favor?" |
| #6 | 0.2187 | Council Member Davis | "Thank you, Mayor. I move that we approve the minutes..." |
| #7 | 0.1458 | Council Member Smith | "I second the motion. Aye." |
| #8 | 0.1271 | Mayor Johnson | "Good evening everyone. I'd like to call this meeting to order." |

### What the similarity numbers mean

- **0.55-0.57** = Strong match. These chunks are clearly about budget concerns.
- **0.40** = Moderate match. Mentions the budget but less directly about "concerns."
- **0.20-0.37** = Weak match. Tangentially related (mentions budget, or is procedural).
- **0.12-0.15** = Very weak. "I second the motion. Aye." has almost nothing to do with
  budget concerns, but it's still returned because we asked for all chunks from this meeting.

In a real system with hundreds of meetings and thousands of chunks, only the top-scoring ones
would be returned (the default is top 10). The low-similarity chunks would be drowned out
by more relevant results from other meetings.

### Step 4: Send chunks + question to Claude (generation)

All 8 chunks are packaged into a prompt and sent to Claude, along with your question and
a system prompt that says:

> "You are a meeting intelligence assistant. Answer questions based on the provided meeting
> transcript excerpts. Only answer based on the provided context. Cite your sources using
> [Source N] notation."

Claude reads the chunks, writes an answer, and cites which sources it used.

### Step 5: Response comes back to the UI

The UI displays:
- **The answer** Claude wrote (with [Source N] citations)
- **All 8 sources** that were sent to Claude, with their similarity scores

### Why are there 8 sources but only 3 cited?

Claude received all 8 chunks as context, but only **cited the ones it actually used** in the
answer. Sources 1-3 were directly relevant to budget concerns. Sources 4-8 were sent to Claude
but Claude correctly ignored them because they weren't about concerns.

This is normal RAG behaviour. You send more context than strictly needed so the LLM has
enough to work with, and trust it to pick out what's relevant.

### Why does it say "Unknown meeting" next to each source?

This is a UI display issue (tracked in GitHub Issue #24). The meeting title isn't being
passed through in the source metadata correctly. The data is there in Supabase — it's just
not being shown in the UI.

---

## How similarity search actually works (the maths, simplified)

Imagine each piece of text as a point in space. Not 2D or 3D space — 1,536-dimensional space
(which is impossible to visualise, but the maths works the same).

```
    "budget concerns" ●────── close together = similar meaning
    "financial worries" ●

                                        ● "pizza recipes"
                                          far away = different meaning
```

**Cosine similarity** measures the angle between two points (vectors):
- **1.0** = pointing in exactly the same direction (identical meaning)
- **0.0** = perpendicular (completely unrelated)
- **-1.0** = pointing in opposite directions (opposite meaning, rare in practice)

In our results, 0.56 means "moderately similar direction" — the text is clearly related to
the question but not a perfect match (which would be weird unless the chunk literally
restated the question).

### Why not just use keyword search?

Keyword search would find "budget" — but it wouldn't find a chunk that says "the allocation
for infrastructure repairs seems low given material cost increases" because none of those
words are in your question. **Semantic search finds meaning, not keywords.**

That said, sometimes keywords matter (names, specific numbers, jargon). That's why **hybrid
search** exists — it combines vector similarity (70%) with keyword matching (30%).

---

## Where to check things manually

### Supabase Dashboard (your data)

Go to https://supabase.com/dashboard → your project → **Table Editor**

| Table | What to look for |
|-------|-----------------|
| `meetings` | Your 2 uploaded meetings. Click a row to see all fields including `raw_transcript`. |
| `chunks` | 9 rows (1 naive + 8 speaker-turn). The `embedding` column has the 1,536-number vector. The `strategy` column shows which chunking was used. The `speaker` column shows who said it. |
| `extracted_items` | Empty until you run extraction (`POST /api/meetings/{id}/extract`). |

### Supabase SQL Editor (run queries yourself)

Go to **SQL Editor** in the Supabase dashboard and try:

```sql
-- See all meetings
SELECT id, title, num_speakers, created_at FROM meetings;

-- See chunks for a specific meeting
SELECT chunk_index, speaker, strategy, LEFT(content, 80) as preview
FROM chunks
WHERE meeting_id = '3b4776bd-0e94-48bf-8bb2-368074c02a8a'
ORDER BY chunk_index;

-- See how many chunks per meeting
SELECT m.title, COUNT(c.id) as chunk_count
FROM meetings m
LEFT JOIN chunks c ON c.meeting_id = m.id
GROUP BY m.title;
```

### API Swagger UI (test endpoints)

Open http://localhost:8000/docs in your browser. You can:
- Try `GET /api/meetings` to see all meetings
- Try `POST /api/query` with different questions and strategies
- Try `POST /api/meetings/{id}/extract` to trigger extraction

### Comparing strategies

You uploaded the same transcript twice — once with naive, once with speaker-turn. You can now
compare what happens when you query each:

1. Ask the same question filtering by the **naive** meeting (1 chunk, no speakers)
2. Ask the same question filtering by the **speaker-turn** meeting (8 chunks, with speakers)

With naive: Claude gets one big blob of text with no speaker info.
With speaker-turn: Claude gets 8 labelled chunks and can say "Council Member Davis said..."

---

## Key concepts reference

| Term | What it means |
|------|--------------|
| **RAG** | Retrieval-Augmented Generation. Instead of sending the whole document to the LLM, you first *retrieve* the most relevant pieces, then send only those. |
| **Embedding** | A list of numbers representing the meaning of text. Similar text → similar numbers. |
| **Vector** | Another word for "list of numbers." A 1,536-dimensional vector is just a list of 1,536 numbers. |
| **Cosine similarity** | A score from -1 to 1 measuring how similar two vectors are. Higher = more similar. |
| **Chunk** | A piece of a transcript. Could be a fixed-size block (naive) or a speaker turn. |
| **Semantic search** | Finding text by meaning (using vector similarity). |
| **Hybrid search** | Combining meaning-based search (vectors) with keyword-based search (full-text). |
| **Context stuffing** | The alternative to RAG: just paste the entire transcript into the LLM prompt. Works for short docs, breaks for large corpora. |
| **Query routing** | Deciding whether to answer from structured data (DB) or through RAG, based on the question type. |
| **Extraction** | Using Claude to pull out structured items (action items, decisions, topics) from unstructured text. |
