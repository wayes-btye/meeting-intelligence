# Worktree WT12 — Issues #42 + #43
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt12-issues-42-43`
**Branch:** `feat/42-43-delete-and-meeting-title`
**Created from:** main @ dd2d6ab
**Worktree path:** `C:\meeting-intelligence-wt12-issues-42-43`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js 14 frontend (`/frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`. Use `settings.x` not `os.getenv("X")`.
- API routes: `src/api/routes/` — meetings route is `src/api/routes/meetings.py`
- Search functions: `src/retrieval/search.py` — `semantic_search()` and `hybrid_search()`
- API models: `src/api/models.py`
- Frontend API helpers: `frontend/lib/api.ts`
- Frontend pages: `frontend/app/meetings/page.tsx`, `frontend/app/chat/page.tsx`
- 115 tests pass on main. Do not break them (`pytest tests/ -m "not expensive"`).
- mypy is now passing (PR #40) — run `ruff check src/ tests/` AND `mypy src/` before PR.
- **Port for this worktree:** `PORT=8120 make api` (needed — this has backend changes)
- Frontend: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8120 npm run dev`

---

## Your mission

Two features: delete meeting from UI, and show meeting title on source cards in chat.

---

## Issue #42 — Delete meeting (API + UI)

### Backend — `src/api/routes/meetings.py`

Add a `DELETE /api/meetings/{meeting_id}` endpoint:

```python
@router.delete("/api/meetings/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: str) -> None:
    """Delete a meeting and all its associated chunks and extracted items."""
    client = get_supabase_client()
    # Delete dependent rows first (Supabase may or may not have CASCADE set up)
    client.table("chunks").delete().eq("meeting_id", meeting_id).execute()
    client.table("extracted_items").delete().eq("meeting_id", meeting_id).execute()
    result = client.table("meetings").delete().eq("id", meeting_id).execute()
    data = cast(list[dict[str, Any]], result.data)
    if not data:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
```

### Frontend — `frontend/lib/api.ts`

Add helper:
```typescript
export async function deleteMeeting(meetingId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/meetings/${meetingId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
}
```

### Frontend — `frontend/app/meetings/page.tsx`

Add a trash icon button per meeting row. Use shadcn's `AlertDialog` for confirmation before firing.

Pattern:
```tsx
import { Trash2 } from 'lucide-react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

// In each meeting row:
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive">
      <Trash2 className="h-4 w-4" />
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete meeting?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently delete "{meeting.title}" and all its chunks. This cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={() => handleDelete(meeting.id)} className="bg-destructive text-destructive-foreground">
        Delete
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

On successful delete, remove the meeting from local state (no full page reload needed).

### Unit test — `tests/test_api.py`

```python
def test_delete_meeting(client):
    """DELETE /meetings/{id} returns 204 and removes the meeting."""
    # First create a meeting
    from tests.conftest import SAMPLE_VTT
    response = client.post("/ingest", files={"file": ("test.vtt", SAMPLE_VTT, "text/vtt")},
                           data={"title": "Delete Test"})
    assert response.status_code == 200
    meeting_id = response.json()["meeting_id"]

    # Delete it
    response = client.delete(f"/meetings/{meeting_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(f"/meetings/{meeting_id}")
    assert response.status_code == 404


def test_delete_nonexistent_meeting_returns_404(client):
    response = client.delete("/meetings/nonexistent-id")
    assert response.status_code == 404
```

---

## Issue #43 — Meeting title on source cards in chat

### Problem
Source cards show speaker, content, timestamp, and similarity — but not which meeting the chunk came from. When querying "All meetings", there's no attribution.

### Backend — `src/api/models.py`

Add `meeting_title` field to `ChunkResult`:

```python
class ChunkResult(BaseModel):
    id: str | None = None
    content: str
    speaker: str | None
    start_time: float | None
    end_time: float | None
    similarity: float | None
    combined_score: float | None = None
    meeting_id: str | None = None
    meeting_title: str | None = None   # ← add this
```

### Backend — `src/retrieval/search.py`

Both `semantic_search()` and `hybrid_search()` currently query the `chunks` table. Add a join to pull `meetings.title`.

For `semantic_search()`, update the RPC call — OR join in Python after the fact using a follow-up query:

```python
def _enrich_with_meeting_titles(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add meeting_title to each chunk by fetching meeting metadata."""
    if not chunks:
        return chunks
    meeting_ids = list({c["meeting_id"] for c in chunks if c.get("meeting_id")})
    client = get_supabase_client()
    result = client.table("meetings").select("id,title").in_("id", meeting_ids).execute()
    title_map = {r["id"]: r["title"] for r in cast(list[dict[str, Any]], result.data)}
    for chunk in chunks:
        chunk["meeting_title"] = title_map.get(chunk.get("meeting_id", ""), None)
    return chunks
```

Call `_enrich_with_meeting_titles()` at the end of both `semantic_search()` and `hybrid_search()`.

**Note:** This adds one extra DB query per search. Acceptable at this scale. A join in the RPC SQL function would be cleaner long-term — but this avoids touching the Supabase migration system.

### Frontend — `frontend/app/chat/page.tsx`

In the source card, show meeting title when present:

```tsx
{chunk.meeting_title && (
  <span className="text-xs text-muted-foreground">
    from: {chunk.meeting_title}
  </span>
)}
```

Show it prominently when querying "All meetings" — this is the main value. When querying a specific meeting it's redundant but harmless.

---

## Definition of done

- [ ] `DELETE /api/meetings/{id}` returns 204 and meeting disappears from list
- [ ] Deleting a meeting also removes its chunks and extracted_items
- [ ] Confirmation dialog shown before delete
- [ ] `test_delete_meeting` and `test_delete_nonexistent_meeting_returns_404` pass
- [ ] `meeting_title` field present in query response chunks
- [ ] Source cards show meeting title in chat (visible for "All meetings" queries)
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check src/ tests/` — clean
- [ ] `mypy src/` — clean

---

## How to raise the PR

```bash
git add src/api/routes/meetings.py src/api/models.py \
        src/retrieval/search.py \
        frontend/lib/api.ts frontend/app/meetings/page.tsx \
        frontend/app/chat/page.tsx \
        tests/test_api.py
git commit -m "feat: delete meeting endpoint + meeting title on source cards (#42 #43)"
gh pr create \
  --title "feat: delete meeting + meeting title on chat source cards (#42, #43)" \
  --body "Closes #42
Closes #43

## Changes

**#42 — Delete meeting**
- DELETE /api/meetings/{id} — removes meeting, chunks, extracted_items; 404 if not found
- frontend/lib/api.ts: deleteMeeting() helper
- Meetings page: trash icon with AlertDialog confirmation per row

**#43 — Meeting title on source cards**
- ChunkResult model: meeting_title field added
- search.py: _enrich_with_meeting_titles() adds meeting title to every chunk result (one extra DB query per search)
- Chat source cards: meeting title shown when present

## Test plan
- test_delete_meeting passes
- test_delete_nonexistent_meeting_returns_404 passes
- Query 'All meetings' → each source card shows its meeting title
- All 115+ tests pass"
```
