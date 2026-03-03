# Worktree WT16 — Issue #71
**Status:** `MERGED` — PR #72 merged 2026-03-03. Branch `feat/71-per-user-isolation` deleted.

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js frontend (`frontend/`), Supabase (pgvector + Supabase Auth), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- All config via Pydantic `Settings` in `src/config.py` — add `SUPABASE_JWT_SECRET` here.
- Ingest route: `src/api/routes/ingest.py` — `POST /api/ingest` accepts `UploadFile + Form fields`.
- Meetings route: `src/api/routes/meetings.py` — `GET /api/meetings`, `GET /api/meetings/{id}`, `DELETE /api/meetings/{id}`.
- Query route: `src/api/routes/query.py` — `POST /api/query`.
- Search: `src/retrieval/search.py` — `semantic_search()`, `hybrid_search()`.
- Models: `src/api/models.py`.
- Frontend nav: `frontend/components/nav.tsx`.
- Frontend API client: `frontend/lib/api.ts` — all API calls go through here.
- All tests pass on main. Do not break them.
- **Port for this worktree:** `PORT=8160 make api`
- mypy is in strict mode — run `ruff check src/ tests/` AND `mypy src/` before PR.

**Auth infrastructure already in place (issue #52):**
- `/login` page at `frontend/app/login/page.tsx`
- Next.js middleware at `frontend/middleware.ts` protects all routes
- Supabase browser client at `frontend/lib/supabase.ts`
- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` already in `frontend/.env.local`

---

## ⚠️ Migration Warning

This issue requires a schema change. **Do not apply the migration without explicit user instruction.**

Write the migration file and stop. State clearly in your PR and issue comment:
"Migration written but NOT applied — awaiting user instruction."

**Coordinate with #48** — that issue also adds a column to `meetings`. Apply this migration first, then #48, sequentially from the main workspace.

---

## Current DB State

- **2 users in auth.users:**
  - `reviewer@example.com` (id: `a28a0480-d315-4714-9ee2-a1497651656f`)
  - `wayes.chawdoury@gmail.com` (id: `06444209-06be-4c59-a1ba-4f4311fcccfa`)
- **10 meetings in DB** — all MeetingBank corpus data, uploaded 2026-02-23, currently have no `user_id` column.
- Existing meetings should be assigned to `reviewer@example.com` via the migration UPDATE.

---

## Your Mission

Add per-user data isolation. Every meeting belongs to a user (`user_id` on the `meetings` table). The FastAPI backend reads the Supabase JWT from the `Authorization` header, extracts the user's UUID, and filters all DB queries by that UUID. Users are created manually in the Supabase dashboard — no self-registration. Once a user logs in and uploads, their data is completely isolated from other users.

---

## Implementation

### Step 1 — Write the migration (do NOT apply)

```bash
supabase migration new add_user_id_to_meetings
```

Edit the generated file:
```sql
-- Add user_id column referencing Supabase auth users
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id);

-- Assign existing 10 meetings to reviewer@example.com
UPDATE meetings
SET user_id = (SELECT id FROM auth.users WHERE email = 'reviewer@example.com')
WHERE user_id IS NULL;
```

**Stop here on migrations.** Do not run `supabase db push`. Note in PR/issue that migration is written but not applied.

### Step 2 — Add SUPABASE_JWT_SECRET to config

In `src/config.py`, add:
```python
supabase_jwt_secret: str
```

In `.env.example`, add:
```
SUPABASE_JWT_SECRET=your-jwt-secret-here  # From Supabase dashboard → Settings → API → JWT Secret
```

The JWT secret for this project is found in the Supabase dashboard. Do NOT hardcode it.

### Step 3 — Create `src/api/auth.py` (new file)

FastAPI dependency that validates the Supabase JWT and returns the user's UUID:

```python
"""FastAPI dependency for JWT-based user authentication."""
from __future__ import annotations

import jwt  # PyJWT
from fastapi import Header, HTTPException

from src.config import settings


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Validate Supabase JWT and return the user's UUID (sub claim).

    Raises:
        HTTPException(401): Missing, malformed, or expired token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
```

Check `pyproject.toml` — if `PyJWT` is not already a dependency, add it.

### Step 4 — `src/ingestion/storage.py` — `store_meeting()`

Add `user_id: str` parameter and include it in the Supabase insert:
```python
"user_id": user_id,
```

### Step 5 — `src/ingestion/pipeline.py` — `ingest_transcript()`

Add `user_id: str` parameter and pass to `store_meeting()`.

### Step 6 — `src/api/routes/ingest.py` — `POST /api/ingest`

Inject the `get_current_user_id` dependency and pass `user_id` to `ingest_transcript()`. Both single-file and zip paths need it.

```python
from src.api.auth import get_current_user_id

@router.post("/api/ingest", ...)
async def ingest(
    ...,
    user_id: str = Depends(get_current_user_id),
) -> ...:
```

### Step 7 — `src/api/routes/meetings.py`

- `GET /api/meetings` — inject dependency, filter: `.eq("user_id", user_id)`
- `GET /api/meetings/{id}` — inject dependency, after fetching verify `m["user_id"] == user_id` (raise 404 if not — don't reveal existence)
- `DELETE /api/meetings/{id}` — inject dependency, add `.eq("user_id", user_id)` to delete query (Supabase will no-op if not owner → raise 404)

### Step 8 — `src/api/routes/query.py` — `POST /api/query`

Inject dependency. Pass `user_id` into `search()` so it scopes results to the user's meetings.

In `src/retrieval/search.py`, add `user_id: str | None = None` to `semantic_search()`, `hybrid_search()`, and `search()`. Filter results Python-side: fetch the user's meeting IDs, then filter returned chunks to those meeting IDs. (Same pattern as the existing `meeting_id` filter in `hybrid_search`.)

### Step 9 — `frontend/lib/api.ts`

Add an `Authorization` header to every `apiFetch` call by reading the current session token from the Supabase client:

```typescript
import { createClient } from '@/lib/supabase'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> ?? {}),
  }
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}
```

---

## Testing

### Backend (automated)
```bash
pytest tests/ -m "not expensive" -q
ruff check src/ tests/
mypy src/
```

Add to `tests/test_api.py` (or new `tests/test_auth.py`):
- `test_unauthenticated_ingest_returns_401` — POST /api/ingest without Authorization header
- `test_unauthenticated_list_meetings_returns_401` — GET /api/meetings without header
- `test_ingest_stores_user_id` — mock Supabase, verify `user_id` included in insert
- `test_list_meetings_filters_by_user_id` — mock Supabase, verify `.eq("user_id", ...)` called

All external calls must be mocked — no live Supabase/JWT calls in regular tests.

### Frontend
`npm run build` — TypeScript must compile cleanly.

**The migration is not applied** — full end-to-end only works after migration is applied. Document clearly in PR.

---

## Definition of Done

- [ ] Migration file written, NOT applied (coordinate with #48)
- [ ] `SUPABASE_JWT_SECRET` in `src/config.py` + `.env.example`
- [ ] `src/api/auth.py` — JWT dependency created
- [ ] `user_id` stored on ingest, filtered on list/get/delete/query
- [ ] Frontend passes `Authorization: Bearer <token>` on every API call
- [ ] All existing tests pass + new auth tests added
- [ ] `ruff check` + `mypy src/` — clean
- [ ] `npm run build` — clean
- [ ] PR comment: "Migration NOT applied. After applying, existing 10 meetings go to reviewer@example.com. SUPABASE_JWT_SECRET needed in Cloud Run + Vercel env vars."

---

## Port Allocation
- API: `PORT=8160 make api`
- Frontend: `NEXT_PUBLIC_API_URL=http://localhost:8160 npm run dev -- --turbo`

## Migration Coordination
Issue #48 also modifies `meetings`. Apply this migration first, then #48, sequentially from main workspace.
