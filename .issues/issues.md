# GitHub Issues & PRs

_Auto-exported on 2026-02-19 22:49 UTC_

## Open Issues

### #30 — fix: resolve 218 mypy type errors across src/

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/30  
**Created:** 2026-02-19  
**Labels:**   

## Summary

CI (introduced in #28) runs \`mypy src/\` and found **218 pre-existing type errors** across 15 files. Ruff passes cleanly — this is mypy only.

## Error Categories

**1. Claude API content block union-attr (~150 errors)**
Files: \`src/retrieval/generation.py\`, \`src/evaluation/metrics.py\`, \`src/evaluation/generate_test_set.py\`, \`src/evaluation/cross_check.py\`

Pattern: code accesses \`.text\` directly on \`response.content[0]\` without narrowing the type:
```python
# current (fails mypy — block could be ThinkingBlock, ToolUseBlock, etc.)
response.content[0].text

# fix — narrow with isinstance
from anthropic.types import TextBlock
block = response.content[0]
if isinstance(block, TextBlock):
    block.text
```

**2. Supabase JSON return type (~50 errors)**
Files: \`src/api/routes/meetings.py\`, \`src/ingestion/storage.py\`, \`src/retrieval/search.py\`, \`src/api/routes/extraction.py\`

Pattern: Supabase \`.data\` returns \`JSON\` (a broad union type), code indexes it with string keys directly. Needs cast or type narrowing after the query.

**3. Bare dict without type params (~15 errors)**
Files: various — \`dict\` should be \`dict[str, Any]\` or more specific.

**4. Misc (~3 errors)**
- \`src/api/main.py:21\` — missing return type annotation on a function
- \`src/ingestion/parsers.py:166\` — \`no-any-return\`
- \`src/extraction/extractor.py:128\` — \`call-overload\` mismatch on \`messages.create\`

## Acceptance Criteria
- \`mypy src/\` exits 0
- \`make lint\` passes fully
- No functional behaviour changes

---

### #26 — Load MeetingBank data into Supabase

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/26  
**Created:** 2026-02-18  
**Labels:** enhancement, data  

The download script has been run (30 JSON files in `data/meetingbank/`) but data was never loaded into the live Supabase instance. Issue #5 acceptance criteria required "30+ meetings queryable in the system."

Run `python scripts/load_meetingbank.py --max 30` against the live Supabase instance so the demo has actual data to query.

---

### #25 — Remove duplicate GET extract endpoint and add CI pipeline

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/25  
**Created:** 2026-02-18  
**Labels:** bug, infrastructure  

Two cleanup items:

### 1. Duplicate extract endpoint
There's a buggy GET `/api/meetings/{id}/extract` in `meetings.py` alongside the correct POST version in `extraction.py`. The GET version has a serialization bug (returns dataclass instances instead of Pydantic models) and is semantically wrong (extraction is a write operation). Remove the GET version.

### 2. Missing CI pipeline
`.github/workflows/ci.yml` was specified in Issue #1 acceptance criteria but never created. Add a basic GitHub Actions workflow running:
- `ruff check`
- `mypy`
- `pytest`

---

### #24 — Fix UI field name mismatches in meetings page

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/24  
**Created:** 2026-02-18  
**Labels:** bug, ui  

The Streamlit Meetings page uses incorrect field names that don't match the API response:

- `date` should be `created_at`
- `num_chunks` should be `chunk_count`
- `owner` should be `assignee`
- `text` should be `content`
- `action_items`/`decisions`/`topics` lists don't match the flat `extracted_items` API response

**Result:** Meetings browser shows "N/A" for date and chunk count, and never displays extracted items.

**Affects:** `src/ui/app.py` (lines 166-216)

---

### #23 — Fix evaluation runner entry point and update README claims

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/23  
**Created:** 2026-02-18  
**Labels:** bug, evaluation  

Multiple evaluation-related gaps:

- `python -m src.evaluation.runner` has no `__main__` block — the documented command fails
- README claims "RAGAS + DeepEval metrics" but neither library is used — implementation is Claude-as-judge (which is actually a good approach, but the claim is misleading)
- No evaluation results have ever been generated
- No `scripts/run_evaluation.py` CLI script

**Needs:**
- Add `__main__` block to `runner.py`
- Update README to accurately describe Claude-as-judge approach
- Consider generating actual evaluation results

---

### #22 — Fix audio upload — remove AssemblyAI references or implement transcription

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/22  
**Created:** 2026-02-18  
**Labels:** bug, critical  

The UI accepts audio files (mp3/wav/m4a) and displays an AssemblyAI message, but no transcription code exists. The ingest endpoint does `.decode("utf-8")` which crashes on binary files. The `assemblyai` package is a dependency but never imported.

**Options:**
1. Implement AssemblyAI transcription (medium effort)
2. Remove audio file types from UI, add clear error for non-text uploads, update README (small effort)

Either way, the current state of silently crashing is not acceptable.

**Affects:** `src/api/routes/ingest.py`, `src/ui/app.py`, `README.md`

---

### #21 — feat: configurable embedding models with migration support

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/21  
**Created:** 2026-02-18  
**Labels:** enhancement  

## Problem

We're locked to OpenAI `text-embedding-3-small` (1536 dimensions). We can't test whether Cohere, Voyage AI, or other embedding models produce better retrieval results — which is arguably more impactful than swapping LLMs, since retrieval quality is the bottleneck in RAG.

## The Compatibility Problem (this is the hard part)

Changing embedding models is **not** like swapping LLMs. Here's why:

### 1. Different models = different vector spaces
Even if two models both output 1536 dimensions, the vectors are **incompatible**. You cannot mix embeddings from different models in the same search — cosine similarity between vectors from different models is meaningless.

### 2. Dimension changes break the schema
Our Supabase schema is hardcoded:
\`\`\`sql
embedding halfvec(1536)              -- fixed dimension
CREATE INDEX chunks_embedding_idx ON chunks
USING hnsw (embedding halfvec_cosine_ops);  -- index is dimension-specific
\`\`\`

Changing to a model with different dimensions (e.g., Cohere embed-v3 at 1024, or text-embedding-3-large at 3072) requires:
- ALTER the column type
- DROP and rebuild the HNSW index
- Re-embed ALL existing chunks

### 3. pgvector dimension limits
pgvector caps at ~2000 dimensions for indexed vectors (8KB block limit). Models like `text-embedding-3-large` (3072 dims) need dimension reduction via the API's \`dimensions\` parameter or won't work with HNSW indexing.

### 4. Re-embedding is expensive
With 50 meetings × ~60 chunks each = ~3,000 chunks. Re-embedding all of them costs:
- OpenAI: ~$0.01 (cheap)
- Cohere: ~$0.01 (cheap)
- Voyage AI: ~$0.02 (cheap)

Actually not bad for our dataset size. The real cost is time and complexity.

## Proposed Solution: LiteLLM Embeddings + Metadata Tracking

### Approach: Use LiteLLM for embeddings too (pairs with #20)

LiteLLM supports embeddings from all major providers with a unified API:
\`\`\`python
import litellm

# OpenAI
response = litellm.embedding(model="text-embedding-3-small", input=["text"])

# Cohere  
response = litellm.embedding(model="cohere/embed-english-v3.0", input=["text"])

# Voyage AI
response = litellm.embedding(model="voyage/voyage-3", input=["text"])
\`\`\`

### Implementation Plan

#### 1. Add embedding model to Settings + PipelineConfig
\`\`\`python
class Settings(BaseSettings):
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
\`\`\`

#### 2. Replace direct OpenAI calls with LiteLLM
\`\`\`python
# Before (embeddings.py)
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(model="text-embedding-3-small", input=texts)

# After
import litellm
response = litellm.embedding(model=settings.embedding_model, input=texts)
\`\`\`

#### 3. Track embedding model per chunk
Add \`embedding_model\` column to chunks table:
\`\`\`sql
ALTER TABLE chunks ADD COLUMN embedding_model TEXT DEFAULT 'text-embedding-3-small';
\`\`\`

This lets us know which model produced each vector, critical for:
- Filtering search to only match chunks with the same embedding model
- Knowing when re-embedding is needed

#### 4. Handle dimension changes via migration script
\`\`\`python
# scripts/re_embed.py
# Re-embeds all chunks with a new model
# Steps: 
#   1. Alter column dimension if needed
#   2. Drop HNSW index
#   3. Re-embed all chunks in batches
#   4. Rebuild HNSW index
\`\`\`

#### 5. Update search to filter by embedding model
\`\`\`sql
-- match_chunks() should filter: WHERE embedding_model = p_embedding_model
\`\`\`

This prevents accidentally comparing vectors from different models.

#### 6. Side-by-side comparison (stretch goal)
For the evaluation framework, the ideal approach is:
- Ingest the same meetings with two different embedding models (stored with different \`embedding_model\` values)
- If dimensions differ, use separate columns or a second table
- Run the same eval questions against both and compare retrieval metrics

**For same-dimension models** (e.g., text-embedding-3-small vs Cohere embed-v3 with \`dimensions=1536\`): Can coexist in the same column if search filters by \`embedding_model\`.

**For different-dimension models**: Would need either:
- A separate \`embedding_alt halfvec(1024)\` column (messy)
- A separate table (cleaner but more complex)
- Just re-embed and compare sequentially (simplest — recommended for MVP)

## Embedding Models Worth Testing

| Model | Provider | Dimensions | Notes |
|-------|----------|-----------|-------|
| text-embedding-3-small | OpenAI | 1536 | Current default, good baseline |
| text-embedding-3-large | OpenAI | 3072 (or 1536 via API) | Can request 1536 dims via \`dimensions\` param |
| embed-english-v3.0 | Cohere | 1024 | Strong on retrieval benchmarks |
| voyage-3 | Voyage AI | 1024 | Top MTEB scores, designed for RAG |
| e5-mistral-7b-instruct | HuggingFace | 4096 | Open-source, very high quality but large |

**Note on Matryoshka embeddings**: OpenAI's v3 models support requesting fewer dimensions (e.g., 512 or 256 from a 1536-dim model). This is useful for testing dimension vs quality trade-offs without changing models.

## Compatibility Matrix

| Change | Schema impact | Re-embed needed? | Index rebuild? |
|--------|-------------|-------------------|----------------|
| Same model, same dims | None | No | No |
| Different model, same dims (1536) | Add model tracking | Yes, all chunks | No (same index works) |
| Different model, different dims | ALTER column + model tracking | Yes, all chunks | Yes (drop + rebuild HNSW) |
| Same model, reduced dims (Matryoshka) | ALTER column | Yes, all chunks | Yes |

## Acceptance Criteria
- [ ] Embedding model configurable via Settings
- [ ] LiteLLM used for embedding calls (unified API)
- [ ] \`embedding_model\` column added to chunks table
- [ ] Search filters by embedding model to prevent cross-model comparison
- [ ] \`scripts/re_embed.py\` migration script for model changes
- [ ] Evaluation can compare retrieval quality across embedding models
- [ ] Streamlit sidebar has embedding model selector

## Depends on
- #20 (LiteLLM integration — shared dependency)

---

### #20 — feat: LLM routing layer — replace direct Anthropic SDK with LiteLLM for model flexibility

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/20  
**Created:** 2026-02-18  
**Labels:** enhancement  

## Problem

We're currently hardcoded to Claude via the Anthropic SDK for three functions:
1. **Answer generation** (`src/retrieval/generation.py`) — Claude Sonnet
2. **Structured extraction** (`src/extraction/extractor.py`) — Claude with `tool_use`
3. **Evaluation metrics** (`src/evaluation/`) — Claude as judge

This means we can't test whether GPT-4o, Gemini, or open-source models (Llama, Mistral) perform better or worse at any of these tasks. For the strategy toggle system to be truly useful, we should be able to swap LLMs the same way we swap chunking and retrieval strategies.

## Proposed Solution: LiteLLM

After researching the options:

| Option | Pros | Cons |
|--------|------|------|
| **OpenRouter** | 500+ models, managed, single billing | 5% markup, SaaS dependency, tool_use inconsistent across models |
| **LiteLLM** | Open-source, self-hosted, 100+ providers, unified API for both LLM + embeddings | Requires local proxy setup |
| **Portkey** | 1600+ models, enterprise compliance | $49/mo, overkill for this project |

**Recommendation: LiteLLM** because:
- It's open-source and free (no markup)
- Single `pip install litellm` — no external proxy needed for basic use
- Unified API covers **both** chat completions AND embeddings (relevant to #11)
- Supports tool_use/function calling across Claude, GPT-4, Gemini
- Can be used as a simple Python library (no proxy server needed)

## Implementation Plan

### 1. Add LiteLLM dependency
```toml
# pyproject.toml
"litellm>=1.0"
```

### 2. Add model config to Settings
```python
# src/config.py
class Settings(BaseSettings):
    llm_model: str = "anthropic/claude-sonnet-4-20250514"  # LiteLLM format
    eval_model: str = "anthropic/claude-sonnet-4-20250514"
    extraction_model: str = "anthropic/claude-sonnet-4-20250514"
```

### 3. Replace Anthropic SDK calls with LiteLLM
```python
# Before (generation.py)
from anthropic import Anthropic
client = Anthropic()
response = client.messages.create(model="claude-sonnet-4-20250514", ...)

# After
import litellm
response = litellm.completion(model=settings.llm_model, messages=[...])
```

### 4. Update extraction to use LiteLLM tool_use
```python
# Before (extractor.py) 
response = client.messages.create(tools=[...], tool_choice={...})

# After
response = litellm.completion(model=settings.extraction_model, tools=[...], tool_choice={...})
```

### 5. Add LLM model to strategy toggle UI
- Sidebar dropdown for model selection (Claude Sonnet, GPT-4o, Gemini 2.0, etc.)
- Separate model selectors for generation vs extraction vs evaluation

### 6. Add to PipelineConfig
```python
@dataclass(frozen=True)
class PipelineConfig:
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SPEAKER_TURN
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    llm_model: str = "anthropic/claude-sonnet-4-20250514"
```

## Compatibility Concerns

### Tool use across models
- **Claude**: Native `tool_use` — works perfectly
- **GPT-4o/4-turbo**: OpenAI `function_calling` — LiteLLM translates automatically
- **Gemini 2.0**: Supports function calling — LiteLLM handles translation
- **Open-source (Llama, Mistral)**: Tool use support is **inconsistent**. Some models claim support but produce malformed JSON. Extraction may fail with these.

### Mitigation
- Extraction (which requires reliable structured output) should default to Claude or GPT-4o
- Generation (free-form text) can use any model
- Evaluation (Claude-as-judge) could be compared across judge models — interesting meta-evaluation

### API key management
With LiteLLM, each provider needs its own key:
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
```
LiteLLM reads these automatically from env vars.

## Acceptance Criteria
- [ ] `litellm` added as dependency
- [ ] All three call sites (generation, extraction, evaluation) use LiteLLM
- [ ] Model is configurable via Settings / PipelineConfig
- [ ] Streamlit sidebar has model selector
- [ ] Tests pass with mocked LiteLLM calls
- [ ] Can switch to GPT-4o and get valid answers (manual test)

---

## Closed Issues

### #9 — README and documentation

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/9  
**Created:** 2026-02-18  
**Labels:** documentation

---

### #8 — Structured extraction: action items, decisions, topics

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/8  
**Created:** 2026-02-18  
**Labels:** pipeline

---

### #7 — Evaluation framework

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/7  
**Created:** 2026-02-18  
**Labels:** evaluation

---

### #6 — RAG strategy toggle system

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/6  
**Created:** 2026-02-18  
**Labels:** pipeline

---

### #5 — Load MeetingBank sample data

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/5  
**Created:** 2026-02-18  
**Labels:** pipeline

---

### #4 — Streamlit UI

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/4  
**Created:** 2026-02-18  
**Labels:** foundation

---

### #3 — Query pipeline + FastAPI endpoints

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/3  
**Created:** 2026-02-18  
**Labels:** pipeline

---

### #2 — Ingestion pipeline: transcript parsing, chunking, embedding

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/2  
**Created:** 2026-02-18  
**Labels:** pipeline

---

### #1 — Project foundation: Docker, config, database schema

**URL:** https://github.com/wayes-btye/meeting-intelligence/issues/1  
**Created:** 2026-02-18  
**Labels:** foundation

---

## Pull Requests

### PR #29 — Add Claude Code GitHub Workflow [CLOSED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/29  
**Branch:** add-claude-github-actions-1771501097839  
**Created:** 2026-02-19  

## 🤖 Installing Claude Code GitHub App

This PR adds a GitHub Actions workflow that enables Claude Code integration in our repository.

### What is Claude Code?

[Claude Code](https://claude.com/claude-code) is an AI coding agent that can help with:
- Bug fixes and improvements  
- Documentation updates
- Implementing new features
- Code reviews and suggestions
- Writing tests
- And more!

### How it works

Once this PR is merged, we'll be able to interact with Claude by mentioning @claude in a pull request or issue comment.
Once the workflow is triggered, Claude will analyze the comment and surrounding context, and execute on the request in a GitHub action.

### Important Notes

- **This workflow won't take effect until this PR is merged**
- **@claude mentions won't work until after the merge is complete**
- The workflow runs automatically whenever Claude is mentioned in PR or issue comments
- Claude gets access to the entire PR or issue context including files, diffs, and previous comments

### Security

- Our Anthropic API key is securely stored as a GitHub Actions secret
- Only users with write access to the repository can trigger the workflow
- All Claude runs are stored in the GitHub Actions run history
- Claude's default tools are limited to reading/writing files and interacting with our repo by creating comments, branches, and commits.
- We can add more allowed tools by adding them to the workflow file like:

```
allowed_tools: Bash(npm install),Bash(npm run build),Bash(npm run lint),Bash(npm run test)
```

There's more information in the [Claude Code action repo](https://github.com/anthropics/claude-code-action).

After merging this PR, let's try mentioning @claude in a comment on any PR to get started!

---

### PR #28 — chore: add GitHub Actions workflows [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/28  
**Branch:** chore/github-workflows  
**Created:** 2026-02-19  

## Summary
- **CI pipeline** (`ci.yml`): Runs `ruff check` + `mypy` (lint) and `pytest -m "not expensive"` (test) on every push/PR to main. No secrets needed.
- **Claude Code Review** (`claude-code-review.yml`): Auto-reviews PRs using `anthropics/claude-code-action@v1`. Needs `CLAUDE_CODE_OAUTH_TOKEN` secret.
- **Claude On-Demand** (`claude.yml`): Responds to `@claude` mentions in issues/PRs. Needs `CLAUDE_CODE_OAUTH_TOKEN` secret.
- **Issue Export** (`export-issues-to-markdown.yml`): Nightly cron (02:00 UTC) + manual dispatch, exports issues to `.issues/`. Needs `GH2MD_TOKEN` secret.

## Manual steps required
1. Add `CLAUDE_CODE_OAUTH_TOKEN` secret — run `/install-github-app` in Claude Code, or reuse from another repo
2. Add `GH2MD_TOKEN` secret — a GitHub PAT with `repo` scope

## Test plan
- [ ] CI workflow runs on this PR automatically (no secrets needed)
- [ ] After adding `CLAUDE_CODE_OAUTH_TOKEN`, Claude review triggers on next PR
- [ ] After merge, manually trigger issue export from Actions tab

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #27 — fix: settings, API keys, UI field names — core flow now working [OPEN]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/27  
**Branch:** fix/storage-settings  
**Created:** 2026-02-19  

## Summary

This PR fixes the issues discovered during manual end-to-end testing. Before this PR,
**no API endpoint that touched Supabase or external APIs actually worked** when running
locally with a `.env` file.

### Root cause

All SDK clients (`Supabase`, `Anthropic`, `OpenAI`) were constructed using `os.getenv()`
or with no arguments (relying on env vars). On Windows, `.env` files are NOT loaded into
`os.environ` automatically — the Pydantic `Settings` object handles this, but the code
wasn't using it consistently.

### Fixes

**Commit 1: Supabase client**
- `src/ingestion/storage.py` — replaced `os.getenv("SUPABASE_URL")` with `settings.supabase_url`
- This was causing 500 errors on every endpoint that touches the database (upload, query, meetings list)

**Commit 2: Anthropic and OpenAI clients**
- `src/retrieval/generation.py` — `Anthropic(api_key=settings.anthropic_api_key)` instead of `Anthropic()`
- `src/retrieval/search.py` — `OpenAI(api_key=settings.openai_api_key)` instead of `OpenAI()`
- `src/ingestion/embeddings.py` — same fix for the embeddings client
- Verified no remaining bare `Anthropic()` or `OpenAI()` calls exist anywhere in `src/`

**Commit 3: UI field name mismatches + documentation**
- Meetings page: `date` → `created_at`, `num_chunks` → `chunk_count`
- Extracted items: `owner` → `assignee`, `text` → `content`, flat list with `item_type` filter
- Sources display: shows speaker + similarity instead of "Unknown meeting"
- Added `docs/manual-testing-guide.md`, `docs/how-it-works.md`, `docs/understanding-the-system.md`

### What was verified manually
- Upload transcript via Streamlit → 200 OK, meeting + chunks stored in Supabase ✓
- Same transcript uploaded with naive (1 chunk) and speaker_turn (8 chunks) strategies ✓
- Query with meeting filter → semantic search finds relevant chunks → Claude generates answer with citations ✓
- Meetings page now shows correct dates, chunk counts, and speaker counts ✓

### What this PR does NOT fix (tracked separately)
- Audio upload still crashes (Issue #22)
- Evaluation runner has no entry point (Issue #23)
- Duplicate GET extract endpoint (Issue #25)
- MeetingBank data not loaded (Issue #26)

## Test plan
- [x] `pytest tests/ -x` — 108 passed
- [x] `ruff check src/` — clean
- [x] Manual: upload → query → answer with sources — full flow verified

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #19 — docs: update README — commands, test count, eval instructions (#9) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/19  
**Branch:** docs/9-readme-update  
**Created:** 2026-02-18  

## Summary
- Added "Available Commands" section with dev, data loading, and evaluation commands
- Updated test count to 108 (was generic)
- Replaced evaluation placeholder with instructions for running the evaluation pipeline

Closes #9

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #18 — fix: address code review findings — extract endpoint, hybrid search, lint [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/18  
**Branch:** fix/review-findings  
**Created:** 2026-02-18  

## Summary
Fixes from comprehensive code review audit:

**Critical:**
- Wire up POST `/api/meetings/{id}/extract` endpoint (was defined in models but never routed)
- Fix `hybrid_search` to support `meeting_id` filtering (was silently returning all meetings)

**Important:**
- Consolidate duplicate `get_supabase_client()` — single source in `src/ingestion/storage`
- Use `settings.llm_model` in `generation.py` instead of hardcoded model name
- Fix 3 ruff lint errors (StrEnum migration, import sorting, unused import)
- Fix README: `pip install -r requirements.txt` → `pip install -e ".[dev]"`
- Add 50MB file upload size limit to ingest endpoint

## Test plan
- [x] `pytest tests/ -x -v` — all 108 tests pass
- [x] `ruff check src/ tests/ scripts/` — clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #17 — feat: structured extraction — action items, decisions, topics (#8) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/17  
**Branch:** feat/8-extraction  
**Created:** 2026-02-18  

## Summary
- Claude-powered extraction using `tool_use` for structured output (action items, decisions, topics)
- Query router classifies structured vs open-ended questions (regex-based)
- Structured queries bypass RAG and go directly to DB lookup
- POST /api/meetings/{id}/extract endpoint triggers extraction
- Integration with ingestion pipeline (optional `extract` parameter)
- 31 new tests covering extraction parsing, query classification, and API endpoints

## Test plan
- [x] `pytest tests/test_extraction.py -v` — all 31 tests pass
- [x] Tool_use schema enforces consistent JSON structure
- [x] Query router correctly classifies action item, decision, topic, and open-ended queries
- [x] Extraction endpoint validates meeting exists before processing

Closes #8

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #16 — feat: evaluation framework — metrics, cross-check, strategy comparison (#7) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/16  
**Branch:** feat/7-evaluation  
**Created:** 2026-02-18  

## Summary
- Auto-generate Q&A test sets from meeting transcripts using Claude (150-250 questions across categories and difficulty levels)
- RAGAS-style metrics via Claude-as-judge: faithfulness, answer relevancy, context precision, context recall
- Cross-check evaluation: RAG vs context-stuffing comparison with verdict categorization
- Strategy comparison across all 4 combinations (naive/speaker_turn × semantic/hybrid) with markdown report
- Evaluation runner orchestrates full pipeline and generates markdown + JSON reports
- 31 new tests, all passing

## Test plan
- [x] `pytest tests/test_evaluation.py -v` — all 31 tests pass
- [x] Metric score clamping and edge cases tested
- [x] Cross-check summarization with per-category breakdowns tested
- [x] Report generation with strategy comparison tables tested

Closes #7

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #15 — feat: RAG strategy toggle system (#6) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/15  
**Branch:** feat/6-strategy-toggle  
**Created:** 2026-02-18  

## Summary
- `PipelineConfig` dataclass with `ChunkingStrategy` (NAIVE, SPEAKER_TURN) and `RetrievalStrategy` (SEMANTIC, HYBRID) enums
- Strategy enums wired through ingestion pipeline, retrieval search, and API endpoints
- Streamlit sidebar strategy selectors persistent across all pages
- FastAPI validates strategy values at request boundary (422 for invalid)
- 23 new tests, 46 total passing

## Test plan
- [x] `pytest tests/ -x` — all 46 tests pass
- [x] Enum values serialize correctly as strings
- [x] API rejects invalid strategy values with 422
- [x] PipelineConfig is immutable (frozen dataclass)

Closes #6

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #14 — feat: MeetingBank data loader scripts (#5) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/14  
**Branch:** feat/5-meetingbank-data  
**Created:** 2026-02-18  

## Summary
- `scripts/download_meetingbank.py` — downloads MeetingBank dataset from HuggingFace (30-50 meeting subset)
- `scripts/load_meetingbank.py` — parses and ingests meetings through the existing pipeline (parse → chunk → embed → store)
- Added `data/` to .gitignore for downloaded dataset files

## Test plan
- [x] Script imports and argument parsing validated
- [x] Compatible with existing ingestion pipeline

Closes #5

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #13 — feat: query pipeline + FastAPI endpoints (#3) [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/13  
**Branch:** feat/3-query-api  
**Created:** 2026-02-18  

## Summary
- Semantic search via Supabase `match_chunks()` RPC and hybrid search via `hybrid_search()` RPC
- Claude-powered answer generation with source attribution (claude-sonnet-4-20250514)
- FastAPI endpoints: POST /api/ingest, POST /api/query, GET /api/meetings, GET /api/meetings/{id}
- Pydantic request/response models for all endpoints
- 6 tests passing (5 API + 1 health)

## Test plan
- [x] `pytest tests/test_api.py` — all 5 API tests pass
- [x] `pytest tests/test_health.py` — health endpoint test passes

Closes #3

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

### PR #12 — feat: ingestion pipeline — parsers, chunking, embedding, storage [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/12  
**Branch:** feat/2-ingestion  
**Created:** 2026-02-18  

## Summary
- **Parsers**: VTT (regex-based, multi-line cues), plain text (speaker label extraction), JSON (AssemblyAI + MeetingBank formats)
- **Chunking**: Naive (fixed-size with overlap, configurable token count) and speaker-turn (groups consecutive same-speaker segments, splits long turns)
- **Embedding**: OpenAI text-embedding-3-small integration with batch support
- **Storage**: Supabase helpers for meetings and chunks (batched insert of 50)
- **Pipeline**: End-to-end `ingest_transcript()` — parse, chunk, embed, store
- **22 tests** covering all parsers and both chunking strategies
- **Test fixture**: sample.vtt with 8-segment council meeting transcript

## Files
- `src/ingestion/models.py` — TranscriptSegment + Chunk dataclasses
- `src/ingestion/parsers.py` — 3 parsers + dispatcher
- `src/ingestion/chunking.py` — naive_chunk + speaker_turn_chunk
- `src/ingestion/embeddings.py` — OpenAI embedding wrapper
- `src/ingestion/storage.py` — Supabase client + store functions
- `src/ingestion/pipeline.py` — end-to-end orchestrator
- `tests/test_ingestion.py` — 22 tests
- `tests/fixtures/sample.vtt` — test data

## Test plan
- [x] `pytest tests/test_ingestion.py -v` — 22/22 passed
- [x] `ruff check` — clean
- [x] `ruff format --check` — formatted
- [ ] Integration: embed + store requires API keys (tested manually or in Issue #3)

Closes #2

---

### PR #11 — feat: Streamlit UI — upload, query, meetings pages [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/11  
**Branch:** feat/4-streamlit-ui  
**Created:** 2026-02-18  

## Summary
- Multi-page Streamlit app with sidebar navigation
- **Upload page**: file uploader (.vtt/.txt/.json/.mp3/.wav/.m4a), chunking strategy selector, AssemblyAI transcription note for audio
- **Ask Questions page**: query input, meeting filter, strategy toggle (Hybrid/Semantic), answer display with source chunks
- **Meetings page**: list view with expandable cards, extracted items display
- HTTP client wrapper (`api_client.py`) for all FastAPI calls
- Graceful handling when API endpoints don't exist yet

## Dependencies
- Requires Issue #3 (Query pipeline + API endpoints) for full functionality
- Currently shows warnings when API endpoints are missing — no crashes

## Test plan
- [x] `ruff check src/ui/` — clean
- [x] `ruff format --check src/ui/` — formatted
- [ ] Manual: `streamlit run src/ui/app.py` — verifies app loads without crash
- [ ] Integration: full flow after Issue #3 merges

Closes #4

---

### PR #10 — feat: project foundation — Docker, config, schema, tests [MERGED]

**URL:** https://github.com/wayes-btye/meeting-intelligence/pull/10  
**Branch:** feat/1-foundation  
**Created:** 2026-02-18  

## Summary
- Project structure with all src/ subdirectories and stubs
- Docker Compose with FastAPI + Streamlit services
- Pydantic BaseSettings config (lazy-loaded for CI)
- Supabase schema: meetings, chunks (pgvector + FTS), extracted_items
- SQL functions: match_chunks (semantic) + hybrid_search (vector + text)
- pyproject.toml, Makefile, .env.example
- Health endpoint with passing test, lint clean

## Test plan
- [x] `pytest tests/test_health.py` — passes
- [x] `ruff check src/ tests/` — all clean
- [x] `ruff format --check` — all formatted
- [x] Supabase migration applied and verified

Closes #1

---

