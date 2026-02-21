# Worktree WT8 — Issue #34
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt8-issue-34`
**Branch:** `feat/34-zip-teams-vtt`
**Created from:** main @ 75209d7
**Worktree path:** `C:\meeting-intelligence-wt8-issue-34`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. Use `settings.x` not `os.getenv("X")`.
- Ingest route: `src/api/routes/ingest.py` — `POST /api/ingest` accepts `UploadFile + Form fields`.
- Parsers: `src/ingestion/parsers.py` — `VTTParser`, `TextParser`, `JSONParser` classes. Parse transcript bytes → list of `Chunk` objects.
- Chunkers: `src/ingestion/chunker.py` — `NaiveChunker`, `SpeakerTurnChunker`.
- Storage: `src/ingestion/storage.py` — `store_meeting()`, `store_chunks()`.
- Tests: `tests/test_ingestion.py` (parsers), `tests/test_api.py` (API routes).
- All 113 tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8080 make api`
- Do not run `mypy` — pre-existing 218 errors being fixed in wt6. Run `ruff check src/ tests/` only.

---

## Your mission

Two independent features. Implement both.

---

## Part 1 — Zip file upload for bulk ingestion

### What to build

`POST /api/ingest` currently accepts a single file. Extend it to also accept `.zip` files. When a `.zip` is uploaded, extract each `.vtt`/`.txt`/`.json` file inside and ingest each as a separate meeting.

**New response shape for zip uploads:**
```json
{
  "meetings_ingested": 3,
  "meeting_ids": ["uuid1", "uuid2", "uuid3"],
  "errors": []
}
```

### Where to make changes

**`src/api/routes/ingest.py`:**
- Detect if `file.filename` ends with `.zip`
- If zip: extract contents using `zipfile.ZipFile`, iterate files, call the existing ingest logic for each
- If not zip: existing single-file path (no change)
- The title for each sub-meeting: `"{zip_name}/{filename_without_ext}"` e.g. `"batch_upload/council_jan.vtt"`

**`src/api/models.py`** (if needed):
- Add a `BatchIngestResponse` model for the zip response shape

### TDD — write tests first

In `tests/test_api.py`, add before touching implementation:

```python
def test_zip_upload_ingests_multiple_meetings(client):
    """Uploading a zip with 2 .vtt files creates 2 meetings."""
    import io, zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("meeting_a.vtt", "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nSpeaker A: Hello.\n")
        z.writestr("meeting_b.vtt", "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nSpeaker B: World.\n")
    buf.seek(0)

    response = client.post(
        "/ingest",
        files={"file": ("batch.zip", buf, "application/zip")},
        data={"title": "Batch Upload"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meetings_ingested"] == 2
    assert len(data["meeting_ids"]) == 2
    assert data["errors"] == []
```

Confirm it fails (red) before implementing.

---

## Part 2 — Microsoft Teams VTT format support

### What to build

Microsoft Teams exports `.vtt` files with `<v SpeakerName>` inline voice tags:

```
WEBVTT

00:00:01.000 --> 00:00:08.000
<v John Smith>Hello everyone, let's get started.

00:00:09.000 --> 00:00:18.000
<v Jane Doe>Thanks John. I want to discuss the Q4 targets.
```

The current `VTTParser` in `src/ingestion/parsers.py` likely strips or ignores these tags, losing the speaker name.

**Fix:** Update `VTTParser.parse()` to:
1. Detect `<v SpeakerName>` at the start of a cue text line
2. Extract the speaker name from the tag
3. Strip the tag from the content text
4. Set `speaker` field on the chunk

### Add a fixture

Create `tests/fixtures/teams_sample.vtt`:
```
WEBVTT

00:00:01.000 --> 00:00:08.000
<v Mayor Johnson>Good evening everyone. I'd like to call this meeting to order.

00:00:09.000 --> 00:00:18.000
<v Council Member Davis>Thank you, Mayor. I move that we approve the minutes.

00:00:19.000 --> 00:00:25.000
<v Mayor Johnson>We have a motion on the floor. All in favor?
```

### TDD — write tests first

In `tests/test_ingestion.py`, add:

```python
def test_vtt_parser_teams_format_extracts_speaker():
    """VTTParser handles <v SpeakerName> Teams inline tags."""
    vtt_content = b"""WEBVTT

00:00:01.000 --> 00:00:08.000
<v Mayor Johnson>Good evening everyone.

00:00:09.000 --> 00:00:18.000
<v Council Member Davis>Thank you, Mayor."""

    from src.ingestion.parsers import VTTParser
    chunks = VTTParser().parse(vtt_content)
    assert len(chunks) == 2
    assert chunks[0].speaker == "Mayor Johnson"
    assert chunks[0].content == "Good evening everyone."
    assert chunks[1].speaker == "Council Member Davis"
    assert "Council Member Davis" in chunks[1].content or chunks[1].speaker == "Council Member Davis"
```

Confirm it fails before implementing.

---

## Definition of done

- [ ] `pytest tests/ -m "not expensive"` — all pass including new tests
- [ ] `ruff check src/ tests/` — clean
- [ ] Zip upload: upload a zip with 3 .vtt files → 3 meetings created, correct response shape
- [ ] Teams VTT: `teams_sample.vtt` fixture exists, test passes, speaker names extracted
- [ ] No changes to unrelated files

---

## How to raise the PR

```bash
git add src/api/routes/ingest.py src/api/models.py src/ingestion/parsers.py \
        tests/test_api.py tests/test_ingestion.py tests/fixtures/teams_sample.vtt
git commit -m "feat: zip bulk upload + Microsoft Teams VTT speaker tag support (#34)"
gh pr create \
  --title "feat: zip upload + Teams VTT format support (#34)" \
  --body "Closes #34

## Part 1 — Zip bulk upload
POST /api/ingest now accepts .zip files. Each .vtt/.txt/.json inside is ingested as a separate meeting. Returns {meetings_ingested, meeting_ids, errors}.

## Part 2 — Teams VTT speaker tags
VTTParser now detects and strips <v SpeakerName> inline voice tags, extracting the speaker name correctly.

## Test plan
- pytest tests/ -m 'not expensive' — all pass
- ruff clean"
```
