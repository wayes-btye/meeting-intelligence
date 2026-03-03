# Worktree WT16 — Issue #45
**Status:** `PLANNED` — worktree not yet created

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py`.
- Ingest route: `src/api/routes/ingest.py` — `POST /api/ingest` accepts `UploadFile + Form fields`.
- Meetings route: `src/api/routes/meetings.py` — `GET /api/meetings`, `GET /api/meetings/{id}`.
- Query route: `src/api/routes/query.py` — `POST /api/query`.
- Search: `src/retrieval/search.py` — `semantic_search()`, `hybrid_search()`.
- Models: `src/api/models.py`.
- Frontend nav: `frontend/components/nav.tsx` — the nav bar (already modified for auth logout button).
- All 117+ tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8160 make api`
- mypy is passing — run `ruff check src/ tests/` AND `mypy src/` before PR.

---

## ⚠️ Migration Warning

This issue requires a schema change. **Do not apply the migration without explicit user instruction.**

Write the migration file and stop. State clearly in your PR and issue comment: "Migration written but NOT applied — awaiting user instruction."

**Coordinate with #48** — that issue also adds a column to `meetings`. Both use different columns (`project_id` vs `chunking_strategy`) so they don't conflict at the SQL level. Apply in whichever order the user decides — they must not be applied concurrently.

---

## Your mission

Add project namespacing to the system. A project is just a string label — no auth, no sessions. Every meeting belongs to a project. All API calls and UI interactions are scoped to the selected project.

This solves a real problem: dev/test uploads pollute the demo corpus. With projects, the assessor selects `assessment` and sees only clean council meeting data.

---

## Implementation

### Step 1 — Write the migration (do NOT apply)

```bash
supabase migration new add_project_id_to_meetings
```

Edit the generated file:
```sql
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS project_id text NOT NULL DEFAULT 'default';
CREATE INDEX IF NOT EXISTS idx_meetings_project_id ON meetings(project_id);
```

**Stop here on migrations.** Do not run `supabase db push`. Note in PR/issue that migration is written but not applied.

### Step 2 — Backend: `POST /api/ingest`

Read `src/api/routes/ingest.py` first. Add `project_id` as an optional Form field:
```python
project_id: str = Form(default="default"),
```
Pass it to `store_meeting()`.

### Step 3 — Backend: `src/ingestion/storage.py`

Read the file first. Add `project_id: str = "default"` param to `store_meeting()` and include it in the Supabase insert:
```python
"project_id": project_id,
```

### Step 4 — Backend: `GET /api/meetings`

Read `src/api/routes/meetings.py` first. Add optional `project_id` query param (default `"default"`):
```python
@router.get("/api/meetings")
async def list_meetings(project_id: str = "default") -> list[MeetingResponse]:
```
Filter the Supabase query:
```python
client.table("meetings").select("*").eq("project_id", project_id).execute()
```

### Step 5 — Backend: `GET /api/projects` (new endpoint)

Add to `meetings.py` (or a new `projects.py` route):
```python
@router.get("/api/projects")
async def list_projects() -> list[str]:
    """Return distinct project_id values from the meetings table."""
    client = get_supabase_client()
    result = client.table("meetings").select("project_id").execute()
    data = cast(list[dict[str, Any]], result.data)
    projects = sorted({row["project_id"] for row in data if row.get("project_id")})
    return projects or ["default"]
```

### Step 6 — Backend: `POST /api/query`

Read `src/api/routes/query.py` and `src/api/models.py` first.

Add `project_id: str = "default"` to `QueryRequest`:
```python
class QueryRequest(BaseModel):
    question: str
    strategy: str = "hybrid"
    meeting_id: str | None = None
    project_id: str = "default"
```

Pass `project_id` into the search functions. Read `src/retrieval/search.py` — add `project_id` filter to both `semantic_search()` and `hybrid_search()` Supabase queries:
```python
query = query.eq("meetings.project_id", project_id)  # adjust based on actual query structure
```

**Important:** The search functions query the `chunks` table joined with meetings. Read the actual SQL/Supabase calls carefully before adding the filter — the join path matters.

### Step 7 — Frontend: API helpers

Read `frontend/lib/api.ts` first. Update:
- `api.getMeetings()` — add `projectId: string = 'default'` param, pass as `?project_id=...` query param
- `api.query()` — add `project_id` to the request body
- Add `api.getProjects()` helper:
```typescript
getProjects: async (): Promise<string[]> => {
  const res = await fetch(`${API_URL}/api/projects`)
  if (!res.ok) return ['default']
  return res.json()
},
```

### Step 8 — Frontend: Project selector in nav

Read `frontend/components/nav.tsx` first — it already has a logout button and other structure. Add a project selector:

```tsx
// State (in the Nav component or a wrapper):
const [projects, setProjects] = useState<string[]>(['default'])
const [selectedProject, setSelectedProject] = useState<string>(
  typeof window !== 'undefined' ? (localStorage.getItem('selectedProject') ?? 'default') : 'default'
)

// Fetch projects on mount
useEffect(() => {
  api.getProjects().then(setProjects)
}, [])

// Persist to localStorage on change
const handleProjectChange = (project: string) => {
  setSelectedProject(project)
  localStorage.setItem('selectedProject', project)
}
```

Render as a simple `<select>` or shadcn `Select` in the nav bar (check what's already imported). Keep it minimal.

### Step 9 — Frontend: Thread project_id through all pages

Each page that calls API methods needs to read the selected project from localStorage and pass it:
```typescript
const projectId = localStorage.getItem('selectedProject') ?? 'default'
```

Pages to update:
- `frontend/app/page.tsx` (upload) — pass `project_id` to ingest call
- `frontend/app/chat/page.tsx` — pass `project_id` to query call
- `frontend/app/meetings/page.tsx` — pass `project_id` to getMeetings call

---

## Testing

### Backend (automated)
```bash
python -m pytest tests/ -m "not expensive" -q
ruff check src/ tests/
mypy src/
```

Add tests:
```python
def test_ingest_with_project_id(client):
    """Ingest scopes meeting to specified project."""
    from tests.conftest import SAMPLE_VTT
    response = client.post(
        "/ingest",
        files={"file": ("test.vtt", SAMPLE_VTT, "text/vtt")},
        data={"title": "Project Test", "project_id": "test-project"},
    )
    assert response.status_code == 200

def test_list_meetings_filters_by_project(client):
    """GET /meetings returns only meetings for the specified project."""
    response = client.get("/meetings?project_id=nonexistent-project")
    assert response.status_code == 200
    assert response.json() == []
```

### Frontend (visual)
`npm run build` — TypeScript must compile cleanly.

**The migration is not applied** — the project selector will render but all existing meetings return as `project_id = NULL` from the DB. The feature works end-to-end only after the migration is applied. Document this clearly in the PR.

---

## Definition of done

- [ ] Migration file written, NOT applied
- [ ] `project_id` threaded through: ingest, meetings list, query, search functions
- [ ] `GET /api/projects` endpoint returns distinct project IDs
- [ ] Project selector in nav with localStorage persistence
- [ ] All pages pass `project_id` from localStorage to API calls
- [ ] `pytest tests/ -m "not expensive"` — all pass
- [ ] `ruff check` + `mypy src/` — clean
- [ ] `npm run build` — clean
- [ ] PR comment states: "Migration NOT applied — apply with `supabase db push --linked` from main workspace then create `assessment` project by ingesting with `project_id=assessment`"

---

## Port allocation
- API: `PORT=8160 make api`
- Frontend: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8160 npm run dev`

---

## Migration note re: #48
Issue #48 also adds a column to `meetings` (`chunking_strategy`). Apply #45 migration first, then #48, from the main workspace. They don't conflict at SQL level but must be sequential.
