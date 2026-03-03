# Worktree WT18 — Issue #66
**Status:** `MERGED` — PR #74 merged 2026-03-03. Branch deleted.

---

## Context

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. Use `settings.x` not `os.getenv("X")`.
- Embeddings: `src/ingestion/embeddings.py` — `embed_chunks()` takes `list[tuple[Chunk, str]]` and returns embeddings.
- Pipeline: `src/ingestion/pipeline.py` — `ingest_transcript()` orchestrates parse → chunk → embed → store.
- `PipelineConfig` in `src/api/models.py` — controls chunking strategy etc.
- Claude API: direct SDK calls (`anthropic.Anthropic()`), no LangChain.
- All tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8180 make api`
- mypy is passing — run `ruff check src/ tests/` AND `mypy src/` before committing.

## Goal

Add contextual retrieval: before embedding each chunk, prepend a 1–2 sentence Claude-generated context summary to the text. The stored chunk text is unchanged — only the text passed to the embedding API is enriched.

This is a **demo branch** — no merge required. Focus on getting it working and testable via the API on port 8180.

## Implementation

### Step 1 — Read the existing code first
Read these files in full before writing anything:
- `src/ingestion/embeddings.py`
- `src/ingestion/pipeline.py`
- `src/api/models.py` (find `PipelineConfig`)
- `src/ingestion/models.py` (find `Chunk`)

### Step 2 — Add `generate_chunk_context()` to `src/ingestion/embeddings.py`

```python
def generate_chunk_context(chunk: Chunk, meeting_title: str) -> str:
    """Call Claude to generate a 1–2 sentence retrieval context for a chunk."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Meeting title: {meeting_title}\n\n"
        f"Chunk text:\n{chunk.text}\n\n"
        "Write 1–2 sentences of context that would help someone retrieve this chunk "
        "when searching the meeting. Include the meeting topic, speaker if known, and "
        "what this excerpt is about. Be concise."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
```

Use Haiku (cheapest, fast) — ~$0.001 per chunk.

### Step 3 — Add `embed_chunks_with_context()` to `src/ingestion/embeddings.py`

New function alongside `embed_chunks()`:
```python
def embed_chunks_with_context(
    chunks: list[Chunk],
    meeting_title: str,
) -> list[tuple[Chunk, list[float]]]:
    """Embed chunks with Claude-generated context prepended to each chunk text."""
    results = []
    for chunk in chunks:
        context = generate_chunk_context(chunk, meeting_title)
        enriched_text = f"{context}\n\n{chunk.text}"
        embedding = _embed_single(enriched_text)  # reuse existing embed helper
        results.append((chunk, embedding))
    return results
```

Read `embed_chunks()` carefully first to understand the existing pattern and reuse the embedding call logic.

### Step 4 — Add toggle to `PipelineConfig`

In `src/api/models.py`, find `PipelineConfig` and add:
```python
contextual_retrieval: bool = False
```

### Step 5 — Wire into `src/ingestion/pipeline.py`

In `ingest_transcript()`, after chunking and before storing, check the flag:
```python
if config.contextual_retrieval:
    chunks_with_embeddings = embed_chunks_with_context(chunks, title)
else:
    chunks_with_embeddings = embed_chunks(chunks)
```

### Step 6 — Tests (mock the Claude call)

Add to `tests/test_ingestion.py` or a new `tests/test_contextual_retrieval.py`:
```python
@patch("src.ingestion.embeddings.anthropic.Anthropic")
def test_generate_chunk_context_calls_claude(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value.content = [
        MagicMock(text="Context sentence.")
    ]
    from src.ingestion.embeddings import generate_chunk_context
    from src.ingestion.models import Chunk
    chunk = Chunk(text="The motion passed.", chunk_index=0, strategy="naive")
    result = generate_chunk_context(chunk, "Budget Meeting")
    assert "Context sentence." in result
```

Mark any test that calls the real Claude API as `@pytest.mark.expensive`.

### Step 7 — Run and verify
```bash
cd /c/meeting-intelligence-wt18-issue-66
PORT=8180 make api
# In another terminal, ingest a meeting with contextual_retrieval=true
curl -X POST http://localhost:8180/api/ingest \
  -F "file=@data/sample_transcript.vtt" \
  -F "title=Test Meeting" \
  -F "contextual_retrieval=true"
```

## Definition of done (for demo)
- [ ] `generate_chunk_context()` implemented
- [ ] `embed_chunks_with_context()` implemented
- [ ] `PipelineConfig.contextual_retrieval` toggle wired through pipeline
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check` + `mypy src/` clean
- [ ] API running on port 8180, ingest with `contextual_retrieval=true` works

## Port
- API: `PORT=8180 make api`
