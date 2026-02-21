# Worktree WT14 — Issue #48
**Status:** `PLANNED` — worktree not yet created

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. Use `settings.x` not `os.getenv("X")`.
- Ingest route: `src/api/routes/ingest.py` — `POST /api/ingest`.
- Storage: `src/ingestion/storage.py` — `store_meeting()`, `store_chunks()`.
- Meetings route: `src/api/routes/meetings.py` — `GET /api/meetings`, `GET /api/meetings/{id}`.
- Models: `src/api/models.py` — `MeetingResponse` etc.
- All 117 tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8130 make api`
- mypy is passing — run `ruff check src/ tests/` AND `mypy src/` before PR.

---

## ⚠️ Migration Warning

This issue requires a schema change. **Do not apply the migration without explicit user instruction.**

Write the migration file and stop. State clearly in your PR and issue comment: "Migration written but NOT applied — awaiting user instruction."

**Coordinate with #45 (projects/namespacing)** — that issue also adds a column to `meetings`. If both are running simultaneously, their migrations must not be applied concurrently. Check with the user before applying.

---

## Your mission

Show the chunking strategy (naive vs speaker-turn) used for each meeting in the meetings list. This requires:
1. A new `chunking_strategy` column on the `meetings` table
2. `store_meeting()` to write the value on ingest
3. `GET /api/meetings` to return the value
4. Meetings list UI to display it

---

## Implementation

### Step 1 — Write the migration (do NOT apply it)

Create the migration file:
```bash
cd /c/meeting-intelligence-wt14-issue-48
supabase migration new add_chunking_strategy_to_meetings
```

Edit the generated file in `supabase/migrations/` to contain:
```sql
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS chunking_strategy text;
```

**Stop here on migrations.** Do not run `supabase db push`. Note in PR/issue comment that the migration is written but not applied.

### Step 2 — Update `src/ingestion/storage.py`

Read the file first. Find `store_meeting()`. Add `chunking_strategy` to the insert payload:
```python
def store_meeting(
    title: str,
    raw_transcript: str,
    num_speakers: int | None = None,
    chunking_strategy: str | None = None,
) -> str:
```
And in the Supabase insert dict:
```python
"chunking_strategy": chunking_strategy,
```

### Step 3 — Update `src/api/routes/ingest.py`

Read the file first. Find where `store_meeting()` is called. Pass the chunking strategy through:
```python
# Get strategy from PipelineConfig
strategy_name = config.chunking_strategy.value  # or .name — check the enum
meeting_id = store_meeting(
    title=title,
    raw_transcript=content,
    num_speakers=num_speakers,
    chunking_strategy=strategy_name,
)
```
Check `src/ingestion/chunker.py` and `src/api/models.py` for the actual enum name/value.

### Step 4 — Update API response models

Read `src/api/models.py`. Add `chunking_strategy: str | None = None` to `MeetingResponse` (or equivalent meeting list response model).

Update `GET /api/meetings` in `meetings.py` to include `chunking_strategy` in the returned data. Read `meetings.py` first.

### Step 5 — Update Frontend

Read `frontend/app/meetings/page.tsx` in full first.

Add a "Strategy" column to the meetings table:
```tsx
<TableHead>Strategy</TableHead>
// ...in the row:
<TableCell>
  {m.chunking_strategy ? (
    <Badge variant="outline" className="text-xs">
      {m.chunking_strategy}
    </Badge>
  ) : (
    <span className="text-muted-foreground text-xs">—</span>
  )}
</TableCell>
```

Add `chunking_strategy?: string | null` to the meeting TypeScript interface.

---

## Testing

### Backend (automated)
```bash
python -m pytest tests/ -m "not expensive" -q
ruff check src/ tests/
mypy src/
```

Add a test to verify `store_meeting()` accepts and the ingest response works:
```python
def test_ingest_stores_chunking_strategy(client: TestClient) -> None:
    """Ingest with a strategy stores it on the meeting."""
    from tests.conftest import SAMPLE_VTT
    response = client.post(
        "/ingest",
        files={"file": ("test.vtt", SAMPLE_VTT, "text/vtt")},
        data={"title": "Strategy Test", "chunking_strategy": "naive"},
    )
    assert response.status_code == 200
    # Verify via GET /meetings/{id}
    meeting_id = response.json()["meeting_id"]
    detail = client.get(f"/meetings/{meeting_id}")
    assert detail.status_code == 200
    assert detail.json().get("chunking_strategy") in ("naive", None)  # None if migration not applied
```

### Frontend (visual)
`npm run build` — TypeScript must compile cleanly.

**The Strategy column will show `—` for all existing meetings** (column defaults to NULL). Only new ingests after the migration is applied will show a strategy value. Document this in the PR.

### Migration testing
**Do not apply the migration.** The UI gracefully handles NULL with `—`. The PR description should note exactly what to do to enable the feature end-to-end:
1. `supabase db push --linked` from the main workspace
2. Re-ingest a meeting
3. Verify strategy column appears

---

## Definition of done

- [ ] Migration file written (NOT applied)
- [ ] `store_meeting()` accepts `chunking_strategy` param
- [ ] Ingest route passes strategy through to storage
- [ ] `MeetingResponse` includes `chunking_strategy` field
- [ ] Meetings list UI shows Strategy column (gracefully shows `—` for null)
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check` clean, `mypy src/` clean
- [ ] `npm run build` clean
- [ ] PR comment explicitly states: "Migration NOT applied — apply with `supabase db push --linked` from main workspace"

---

## Port allocation
- API: `PORT=8130 make api`
- Frontend: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8130 npm run dev`

---

## How to raise the PR

```bash
git add supabase/migrations/ src/ingestion/storage.py src/api/routes/ingest.py \
        src/api/models.py src/api/routes/meetings.py \
        frontend/app/meetings/page.tsx tests/test_api.py
git commit -m "feat: show chunking strategy on meetings list (#48)"
gh pr create \
  --repo wayes-btye/meeting-intelligence \
  --base main \
  --head feat/48-chunking-strategy-column \
  --title "feat: chunking strategy column on meetings list (#48)" \
  --body "Closes #48

## What this adds
- Migration: \`chunking_strategy text\` column on meetings table (NOT applied — see below)
- \`store_meeting()\` now accepts and persists \`chunking_strategy\`
- Ingest route passes strategy name through to storage
- \`MeetingResponse\` includes \`chunking_strategy\` field
- Meetings list shows Strategy badge column (shows — for historical meetings with NULL)

## ⚠️ To activate end-to-end
Run from main workspace: \`supabase db push --linked\` then re-ingest a meeting.

## Test plan
- pytest passing
- ruff + mypy clean
- npm build clean
- Strategy column visible in UI (shows — for existing meetings until migration applied)"
```
