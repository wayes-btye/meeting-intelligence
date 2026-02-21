# Feedback Session — 21 Feb 2026

Structured responses to all questions raised in the session. Each section ends with a
**verdict** (quick win / medium effort / parking lot) to help prioritise what becomes
a GitHub issue.

### Overlap with existing open issues (check before creating new ones)
- **§1 (transcript examples / MeetingBank data)** → already partially covered by **#26** (Load MeetingBank into Supabase) and **#34** (Teams VTT format support). Inform those issues rather than opening new ones.
- **§4c (meeting visualisation)** → already captured by **#35** (upload-time visual summary via Gemini). Add any detail there rather than a new issue.
- Everything else in this document (§2, §3a–d, §6, §7) is net-new and not yet tracked.

---

## 1. Teams Transcript Examples

### Problem
The existing sample transcripts feel artificial; better test data is needed.

### Best Sources Found

#### Immediately grabbable VTT files
| Repo | What's there |
|------|-------------|
| [ZhijingEu/VTT_File_Cleaner](https://github.com/ZhijingEu/VTT_File_Cleaner) | `SampleWorkshopTranscript.VTT` — real Teams recording, committed to repo |
| [tccgroup/VTTMeetingNoteGenerator](https://github.com/tccgroup/VTTMeetingNoteGenerator) | `ExampleTranscript/` folder with Teams/Zoom VTT samples |
| [valentinkm/MinervasMemo](https://github.com/valentinkm/MinervasMemo) | `sample.vtt` used in their pipeline tests |

#### Hugging Face datasets (structured JSON, multi-speaker)
| Dataset | Size | Notes |
|---------|------|-------|
| [lytang/MeetingBank-transcript](https://huggingface.co/datasets/lytang/MeetingBank-transcript) | 115 MB | 1,366 city-council meetings (Boston, Denver, Seattle…), word-level timestamps. **Best fit for this project.** |
| [huuuyeah/MeetingBank_Audio](https://huggingface.co/datasets/huuuyeah/MeetingBank_Audio) | Large | MP3 audio matched to the above transcripts — use to test AssemblyAI diarization with ground-truth comparison |
| [microsoft/MeetingBank-LLMCompressed](https://huggingface.co/datasets/microsoft/MeetingBank-LLMCompressed) | Smaller | Microsoft's own compressed-transcript variant |
| [ami / diarizers-community/ami](https://huggingface.co/datasets/ami) | ~100 h | AMI corpus — 4-person scenario meetings, CC BY 4.0. Research gold-standard for diarization |

#### Research corpora (audio + transcript, best for AssemblyAI tests)
- **AMI corpus** — [groups.inf.ed.ac.uk/ami/corpus](https://groups.inf.ed.ac.uk/ami/corpus/) — 100 hours, 4-person meetings, free download.
- **ICSI corpus** — [groups.inf.ed.ac.uk/ami/icsi](https://groups.inf.ed.ac.uk/ami/icsi/) — 75 real research meetings, 72 hours, 53 speakers.

#### Ongoing real government meetings
- **Council Data Project** — [councildataproject.org](https://councildataproject.org/) — continuously updated Seattle, Portland, King County meeting transcripts in structured JSON with speaker labels. Same domain as the existing Denver council samples.

#### GitHub's own open meetings
GitHub does not publish downloadable transcripts of their own meetings or YouTube videos in VTT/TXT form. The `OfficeDev/Microsoft-Teams-Samples` repo contains SDK code, not real transcript files. If you want to test with GitHub content, the easiest path is to download the audio from one of their public YouTube recordings and push it through AssemblyAI.

### Recommendation (priority order)
1. Grab the VTTs from `ZhijingEu/VTT_File_Cleaner` and `tccgroup/VTTMeetingNoteGenerator` today — zero setup.
2. Pull a handful of JSON records from `lytang/MeetingBank-transcript` — these are already council meetings, same domain as the current data.
3. For AssemblyAI diarization testing, pair `MeetingBank_Audio` with the transcript dataset for a direct accuracy comparison.

**Verdict:** No code changes needed. Data gathering task only.

---

## 2. Markdown Rendering in Chat Answers

### Problem
The answer text in the Chat page is rendered as plain text using `whitespace-pre-wrap`
(`chat/page.tsx:155`). Claude's responses contain markdown (bold headers, bullet lists,
numbered lists) that currently renders as raw symbols.

### What the AI_Image_Playground project uses
Checking `C:\Cursor_Projects\AI_Image_Playground\package.json`:
```
"react-markdown": "^10.1.0"
"remark-gfm": "^4.0.1"     ← GitHub-flavoured markdown (tables, strikethrough, etc.)
"rehype-slug": "^6.0.0"    ← anchor IDs on headings (optional, probably not needed here)
```

### What needs to change
- Install `react-markdown` and `remark-gfm` in `frontend/`.
- Replace the `<p className="... whitespace-pre-wrap">{result.answer}</p>` in
  `chat/page.tsx:155` with a `<ReactMarkdown>` component.
- Add light prose-style CSS so headings, lists, and bold text look clean (Tailwind's
  `prose` classes from `@tailwindcss/typography` are the cleanest solution, or inline
  className overrides).

**Verdict:** Quick win — ~20 lines of change, no API work needed.

---

## 3. Meetings Page — Chunks View, Speaker Count, Chunking Strategy, Delete

### 3a. Chunk viewer
**Current state:** Clicking a meeting shows extracted items (action items, decisions,
topics). There is no way to see the actual transcript chunks.

**What the API already returns:** `GET /api/meetings/{id}` returns a full `chunks` array
with `content`, `speaker`, `start_time`, `end_time` for every chunk
(`meetings.py:73-81`, `models.py:18-27`). The data is there; the UI doesn't display it.

**Proposed UI:** Add a collapsible "Chunks" section (or a second tab) in the
`MeetingDetailPanel`. Each chunk shown as a card: speaker badge, timestamp badge, chunk
index, and the text. This would let you verify chunking quality immediately after upload.

**Verdict:** Medium effort — pure frontend, ~50 lines, no API changes.

---

### 3b. Why `num_speakers` is null for some meetings
`num_speakers` in the `meetings` table comes from the transcript parser. It is `null`
when:
1. The file is a plain `.txt` without speaker labels — the parser finds no speaker
   identifiers and stores `null`.
2. The file was processed with **naive chunking** — naive chunks don't track speaker
   per segment, so if speaker counts weren't parsed from the raw file, the field stays
   `null`.

The council meetings you uploaded _should_ have speakers in the VTT headers, but if
they were uploaded as plain `.txt` exports (or if the VTT parser didn't recognise the
speaker-label format), the speaker count drops out.

**Short answer:** Null speakers = the transcript source had no parseable speaker labels,
OR the parser didn't pick them up. It does _not_ necessarily mean naive chunking was
used — it's an independent field.

---

### 3c. Displaying chunking strategy on the meetings list
**Current state:** `MeetingSummary` (`models.py:39-48`) does not include chunking
strategy. Each chunk row in the DB has a `strategy` column, but the list endpoint only
returns a count, not the strategy.

**Options:**
1. Add a `chunking_strategy` column to the `meetings` table and populate it on ingest
   (cleanest — one migration, no extra queries).
2. Infer it from the first chunk at query time (no migration, but an extra DB query per
   meeting in the list view — not great at scale).

Option 1 is the right fix. Until then the UI can't show it reliably.

**Verdict:** Medium effort — requires a Supabase migration + ingest change + UI column.
Worth doing as a standalone issue.

---

### 3d. Delete a meeting from the UI
**Current state:** No delete endpoint exists. You have to go into Supabase directly.

**What's needed:**
- `DELETE /api/meetings/{meeting_id}` — deletes from `meetings`, `chunks`, and
  `extracted_items` (Supabase cascade or explicit deletes).
- A delete button/icon in the meetings table row, with a confirmation prompt before
  firing.

This is straightforward and genuinely useful for cleaning up test uploads.

**Verdict:** Medium effort — one API route + small UI change. Good candidate for an issue.

---

## 4. Upload Page — Extraction Storage, Transcript Viewer, Visualisation

### 4a. Is extraction data stored?
**Yes.** The `POST /api/meetings/{id}/extract` endpoint writes action items, decisions,
and topics to the `extracted_items` table. The upload page appears to call this after
ingest (hence the breakdown you see). Once stored, that data is what powers the
`MeetingDetailPanel` on the Meetings page.

**The reason some meetings show "No extraction data yet"** is that some transcripts were
ingested before the extraction step was wired into the upload flow, or extraction was
run separately. Running extract on those meetings from the API Explorer (`/docs`) will
fix them.

---

### 4b. Full transcript viewer
**What the API has:** `raw_transcript` is returned in `GET /api/meetings/{id}`
(`meetings.py:71`). The raw content is already fetched when you click a meeting.

**Proposed UI:** A collapsible "Full Transcript" section in the detail panel (below
extraction data). Because transcripts can be long, wrapping it in a scrollable box
with a max-height is cleaner than expanding everything inline.

Alternatively, show it as the chunk viewer from §3a — chunks are the processed form of
the transcript and are arguably more useful than the raw file.

**Verdict:** Quick win (for raw transcript view using existing data) or included with
the chunk viewer work.

---

### 4c. "Gemini diagram" — meeting visualisation
There is no graph/mind-map visualisation in the current codebase. This would be a new
feature. A few interpretations of what you might mean:

- **Topic network graph:** nodes = topics/speakers, edges = co-occurrence. Could use
  D3.js or a React graph library (e.g. `react-force-graph`).
- **Timeline view:** chunks/speaker turns laid out on a horizontal timeline.
- **Summary mind map:** hierarchical diagram from the extracted topics → decisions →
  action items.

Since this uses API tokens (Claude to generate the structure), making it a
**"Generate Visualisation" button** (not auto-run on ingest) is correct.

Note: "Gemini" in this context seems to refer to the visual style/layout, not the
Google AI product. Worth confirming what specific output format you have in mind
before building this.

**Verdict:** Parking lot / future issue. Define the desired output format first.

---

## 5. Finding Microsoft Teams Transcript Examples

See §1 above for the full breakdown. Short summary:

- **Best immediate action:** grab VTT files from GitHub repos listed above.
- **Best dataset for council meetings:** `lytang/MeetingBank-transcript` on Hugging
  Face (115 MB, same domain as existing data, already JSON).
- **Best for AssemblyAI diarization accuracy testing:** `MeetingBank_Audio` audio +
  matching transcript dataset.
- **GitHub open meetings:** no downloadable transcripts found. Use YouTube audio +
  AssemblyAI as the workaround.
- **Hugging Face size concern:** The MeetingBank-transcript dataset at 115 MB is
  manageable — you don't need to ingest all 1,366 meetings. Download the dataset,
  pick 5–10 from different cities, convert their JSON to the format the ingest
  pipeline accepts, and test with those.

---

## 6. Chat Page — RAG Parameters, Source Metadata, UI Improvements

### 6a. What parameters are currently used?

#### Semantic search (`src/retrieval/search.py:19-37`)
| Parameter | Current value | Exposed in UI? |
|-----------|---------------|----------------|
| Embedding model | `text-embedding-3-small` (1536 dims) | No |
| `match_count` | 10 | No |
| Similarity metric | Cosine (pgvector default) | No |
| Similarity threshold | None — always returns top 10 | No |

#### Hybrid search (`src/retrieval/search.py:40-80`)
| Parameter | Current value | Exposed in UI? |
|-----------|---------------|----------------|
| `vector_weight` | 0.7 | No |
| `text_weight` | 0.3 | No |
| `match_count` | 10 | No |
| Full-text search engine | Postgres `tsvector` | No |

None of these are surfaced in the UI or exposed as API parameters.

---

### 6b. What metadata do chunks have?
Each source chunk in the query response (`models.py:18-27`) carries:

| Field | Shown in UI? |
|-------|-------------|
| `content` | Yes |
| `speaker` | Yes (badge) |
| `start_time` | Yes (timestamp badge) |
| `end_time` | No |
| `similarity` | Yes (% match badge) |
| `combined_score` | Yes (score badge, hybrid only) |
| `meeting_id` | No |

Missing from the source card: `meeting_id` / meeting title (useful when querying
across "All meetings" — which meeting did this chunk come from?), `end_time`
(would let you compute chunk duration), and the chunk's `strategy` tag (was this
a speaker-turn chunk or a naive chunk?).

For the assignment, showing **meeting title** on each source card when in "All
meetings" mode is the highest-value addition, because it directly demonstrates
cross-meeting retrieval.

---

### 6c. Displaying and tweaking retrieval parameters
**Proposed additions to the Chat UI:**

1. **Parameter info block** — shown below the "Retrieval Strategy" radio buttons,
   contextual to the selected strategy:
   - Semantic: `model: text-embedding-3-small · top_k: 10 · metric: cosine`
   - Hybrid: `vector_weight: 0.7 · text_weight: 0.3 · top_k: 10`

2. **Tweakable sliders (advanced panel)** — for the demo/assignment, exposing
   `vector_weight` / `text_weight` and `match_count` as UI controls would show
   real-time impact of parameter changes. This requires the API to accept these
   as optional query params (they're currently hardcoded in `search.py`).

3. **Strategy explanation tooltip** — a small `?` icon next to each strategy label
   with a one-liner:
   - Semantic: "Pure vector similarity — finds conceptually related chunks even
     without exact keyword matches."
   - Hybrid: "Combines vector similarity (70%) with keyword match (30%) — better
     for specific names, terms, or phrases."

---

### 6d. Other observations from the screenshot

- **Answer is rendered as plain text** — bold/bullet formatting from Claude is lost
  (see §2 above).
- **Source cards show `speaker` as a badge** — when naive chunking was used, speaker
  is `null` and the badge renders as empty/undefined. Should handle `null` speaker
  gracefully (e.g. show "Unknown speaker" or omit the badge).
- **No meeting title on source cards** — when querying "All meetings", you can't tell
  which meeting a chunk came from. Should show meeting title (requires passing it
  through from the DB query or joining on `meeting_id`).
- **Score display** — `combined_score` is shown as a raw float (e.g. `score: 0.743`).
  For semantic-only queries this field is `null` and disappears. Clear, but the `%
  match` badge alone could be misleading if users don't know it's cosine similarity
  capped near 1.0 — a tooltip explaining the scale would help.
- **No empty-state for sources** — if the router routes to structured lookup, `sources`
  is empty and nothing is shown. A small note ("Answer from structured database — no
  transcript chunks retrieved") would reduce confusion.
- **`model` and `usage` fields** returned by the API (token counts etc.) are not
  displayed anywhere. For a demo/assignment, showing model name + token usage below
  the answer adds credibility.

---

## 7. Projects / Data Namespacing (for Assessment Demo)

### Problem
There are no users and no data isolation. When an assessor evaluates the app they see
all dev test uploads mixed in with any demo data. Full authentication is not wanted —
it adds complexity and failure points for what is essentially a single-assessor demo.

### Recommendation: Projects (namespacing, no auth)

A **project** is just a name/slug stored in the DB. Every meeting belongs to a project.
The UI has a project selector in the nav — pick one and all meetings, queries, and
uploads are scoped to it. No login, no passwords, no sessions. The selected project
persists in `localStorage` (or the URL if you want shareable links).

### What this looks like for the assessor
- Create an `assessment` project pre-loaded with clean council meetings.
- Dev/test noise stays in a `default` or `dev` project.
- The assessor opens the app, selects `assessment` from the dropdown, and gets a tidy
  isolated experience without seeing any test clutter.

### Why not "users"
Users implies auth — even lightweight solutions (Clerk, magic links, Auth0) add a
meaningful dependency and a potential failure point. Projects with no auth achieves
the same data isolation in a fraction of the work, and is honest about what's actually
needed for a demo context.

### Implementation scope (keep it tight)

| Layer | Change |
|-------|--------|
| DB | One migration: add `project_id` column to `meetings` table, default `'default'` |
| API | `project_id` as optional param on `/api/ingest`, `/api/query`, `/api/meetings` (defaults to `'default'`) |
| UI | Project selector dropdown in the nav, selection saved to `localStorage` |

No new dependencies. No user management screens. Just a dropdown and a DB column.

**Verdict:** Medium effort — one migration + small API + small UI change. Should be done
before the assessment is scheduled.

---

## Summary Table

| # | Item | Effort | Recommended action |
|---|------|--------|--------------------|
| 1 | Better transcript examples | None (data task) | Grab VTTs + MeetingBank JSON |
| 2 | Markdown rendering in chat | Low | GitHub issue — ~20 lines |
| 3a | Chunk viewer in meetings | Medium | GitHub issue |
| 3b | Null speakers explanation | None | Understanding only |
| 3c | Show chunking strategy on list | Medium | GitHub issue (needs migration) |
| 3d | Delete meeting from UI | Medium | GitHub issue |
| 4a | Extraction storage confirmation | None | Already works; re-extract old meetings via `/docs` |
| 4b | Full transcript viewer | Low | Fold into chunk viewer issue |
| 4c | Meeting visualisation | High | Parking lot — define format first |
| 5 | Teams transcript sources | None | Data task — sources listed above |
| 6a/b | RAG parameter display | Low-Medium | GitHub issue |
| 6c | Parameter sliders (tweakable) | Medium | GitHub issue (API + UI) |
| 6d | Meeting title on source cards | Low | Fold into RAG metadata issue |
| 6d | Handle null speaker badge | Low | Quick fix |
| 6d | Model/token usage display | Low | Add to RAG metadata issue |
| 7 | Projects / data namespacing | Medium | GitHub issue — do before assessment |
