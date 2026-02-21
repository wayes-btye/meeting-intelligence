# Worktree WT13 — Issue #47
**Status:** `PLANNED` — worktree not yet created

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- Frontend pages: `frontend/app/`. Meetings browser: `frontend/app/meetings/page.tsx`.
- Meeting detail panel: look for `MeetingDetailPanel` component or inline detail rendering within `meetings/page.tsx` — read the file first to understand current structure.
- `GET /api/meetings/{id}` already returns `chunks` array and `raw_transcript` — no API changes needed.
- All 117 tests pass on main. Do not break them.
- **This is pure frontend work** — use main workspace API at `http://localhost:8000`, no separate API port needed.
- mypy is passing — run `ruff check src/ tests/` AND `mypy src/` if touching any Python.

---

## Your mission

Add a collapsible **Chunks** section to the meeting detail panel. The data is already returned by the API — this is a display-only change.

No API changes. No migrations. Frontend only.

---

## What to build

### Read the current meetings page first
Read `frontend/app/meetings/page.tsx` in full before writing a single line. Understand:
- How the meeting detail panel is structured (is it inline, a sidebar, a separate component?)
- What data is currently displayed (extracted items, metadata)
- Where `chunks` is already destructured from the API response (if at all)
- The existing TypeScript interfaces for meeting data

### Chunk card section
Below the existing extracted items, add a collapsible "Chunks" section (use a `<details>` / `<summary>` or shadcn `Accordion` — whichever is cleaner given existing component imports).

Each chunk rendered as a card showing:
```tsx
<div className="border rounded p-3 space-y-1">
  <div className="flex items-center gap-2">
    <Badge variant="outline">#{chunk.chunk_index}</Badge>
    {chunk.speaker && <Badge variant="secondary">{chunk.speaker}</Badge>}
    {chunk.start_time && (
      <span className="text-xs text-muted-foreground">
        {chunk.start_time} → {chunk.end_time}
      </span>
    )}
  </div>
  <p className="text-sm">{chunk.content}</p>
</div>
```

### Full transcript toggle
Below the chunks section, add a "Full Transcript" toggle (same collapsible pattern) showing `meeting.raw_transcript` in a `<pre>` or scrollable `<div>` with `whitespace-pre-wrap`.

### TypeScript types
The `chunk` items should already be typed if the meetings detail API response is typed. If not, add an inline interface:
```typescript
interface Chunk {
  chunk_index: number
  speaker: string | null
  start_time: string | null
  end_time: string | null
  content: string
}
```

---

## Testing approach

**This is a UI-only feature — testing is inherently visual.**

Automated checks:
- `npm run build` — TypeScript must compile cleanly (catches type errors, missing imports)
- `python -m pytest tests/ -m "not expensive" -q` — must still pass (no backend changes, so this is just a regression check)

Manual verification (describe what you did in the PR/issue comment):
- With the dev server running and the API up (`make api`), click a meeting in the meetings list
- Verify the Chunks section appears and is collapsible
- Verify each chunk shows speaker badge, timestamp, content
- Verify the Full Transcript toggle works
- Note how many chunks a sample meeting has in your PR comment

The PR description should include a brief description of manual testing performed.

---

## Definition of done

- [ ] `npm run build` clean
- [ ] `pytest tests/ -m "not expensive"` — all pass (regression check)
- [ ] Chunk cards visible in meeting detail with speaker badges and timestamps
- [ ] Chunks section is collapsible (not always expanded)
- [ ] Full Transcript toggle works
- [ ] No new `any` TypeScript types introduced without justification
- [ ] Manual test described in PR comment

---

## Port allocation
- No separate API port — use main workspace `http://localhost:8000`
- Frontend dev: `cd frontend && npm run dev` (main workspace port 3000)

---

## How to raise the PR

```bash
git add frontend/app/meetings/page.tsx  # (or whichever components were touched)
git commit -m "feat: chunk viewer + full transcript toggle in meeting detail panel (#47)"
gh pr create \
  --repo wayes-btye/meeting-intelligence \
  --base main \
  --head feat/47-chunk-viewer \
  --title "feat: chunk viewer + full transcript in meeting detail (#47)" \
  --body "Closes #47

## What this adds
- Collapsible Chunks section in meeting detail panel — speaker badge, timestamp, content per chunk
- Full Transcript toggle showing raw_transcript
- Pure frontend — no API changes (data already in GET /api/meetings/{id} response)

## Test plan
- npm run build — clean
- Manual: clicked [N] meetings, verified chunk cards render with speaker/timestamp/content"
```
