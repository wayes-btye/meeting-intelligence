# Worktree WT10 — Issue #52
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt10-issue-52`
**Branch:** `feat/52-supabase-auth`
**Created from:** main @ dd2d6ab
**Worktree path:** `C:\meeting-intelligence-wt10-issue-52`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js 14 frontend (`/frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- Frontend lives in `frontend/` — Next.js 14 App Router, shadcn/ui, Tailwind
- The frontend calls `NEXT_PUBLIC_API_URL` from `.env.local` for all API calls. API helpers live in `frontend/lib/api.ts`.
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` — add these to `frontend/.env.local` and `frontend/.env.example`
- 115 tests pass on main. Do not break them (`pytest tests/ -m "not expensive"`).
- mypy is now passing (PR #40 merged) — run `mypy src/` and `ruff check src/ tests/` before PR.
- **Port for this worktree:** `PORT=8100 make api` (only needed if testing API endpoints — this is mostly frontend work)
- Frontend: `cd frontend && npm run dev` (port 3000 as always)

**Supabase project:** `qjmswgbkctaazcyhinew` — already has Auth enabled. You will create the test user manually in the Supabase dashboard.

---

## Your mission

Add email/password login to the React frontend using Supabase Auth. The assessor gets a login page — you give them the credentials. No backend changes needed.

---

## Install packages

```bash
cd frontend
npm install @supabase/supabase-js @supabase/ssr
```

---

## Files to create/modify

### 1. `frontend/lib/supabase.ts` — Supabase browser client

```typescript
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

### 2. `frontend/app/login/page.tsx` — Login page

Simple email/password form. On success, `router.push('/')`.

```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const supabase = createClient()
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      router.push('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-sm space-y-4 p-8 border rounded-lg shadow-sm">
        <h1 className="text-2xl font-semibold">Meeting Intelligence</h1>
        <p className="text-sm text-muted-foreground">Sign in to continue</p>
        <form onSubmit={handleLogin} className="space-y-3">
          <Input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required />
          <Input type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)} required />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  )
}
```

### 3. `frontend/middleware.ts` — route protection

```typescript
import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  const response = NextResponse.next()

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookies) => cookies.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options)
        ),
      },
    }
  )

  const { data: { user } } = await supabase.auth.getUser()

  // Redirect to login if not authenticated
  if (!user && !request.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Redirect to home if already logged in and trying to access /login
  if (user && request.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/', request.url))
  }

  return response
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
```

### 4. `frontend/app/layout.tsx` — add logout button

In the existing nav/header, add a logout button that calls `supabase.auth.signOut()` then redirects to `/login`.

Keep it minimal — a small "Sign out" link in the top-right nav is enough.

### 5. `frontend/.env.local` — add Supabase env vars

```
NEXT_PUBLIC_SUPABASE_URL=https://qjmswgbkctaazcyhinew.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from Supabase dashboard>
```

### 6. `frontend/.env.example` — document the new vars

Add:
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

---

## What the user does manually (NOT your job)

The user will:
1. Get the anon key from the Supabase dashboard → Settings → API
2. Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` to the Vercel environment variables
3. Create the assessor user in Supabase dashboard → Authentication → Users → Add user

---

## No backend changes

The FastAPI backend is untouched. Auth is entirely client-side via Supabase. The session token is managed by `@supabase/ssr` in Next.js middleware.

---

## Definition of done

- [ ] `cd frontend && npm run build` passes
- [ ] Unauthenticated visit to `/` redirects to `/login`
- [ ] Valid email/password logs in and redirects to `/`
- [ ] Invalid credentials shows error message
- [ ] "Sign out" button works — redirects back to `/login`
- [ ] `pytest tests/ -m "not expensive"` — all pass (no backend changes)
- [ ] `ruff check src/ tests/` — clean
- [ ] `mypy src/` — clean

---

## How to raise the PR

```bash
git add frontend/
git commit -m "feat: Supabase email/password auth — protect frontend with login page (#52)"
gh pr create \
  --title "feat: email/password login via Supabase Auth (#52)" \
  --body "Closes #52

## What this adds
- /login page with email/password form
- Next.js middleware redirecting unauthenticated users to /login
- Logout button in nav
- No backend changes — session handled client-side by @supabase/ssr

## Manual steps (user)
- Add NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY to Vercel env vars
- Create assessor user in Supabase dashboard → Authentication → Users

## Test plan
- npm run build passes
- Unauthenticated → redirected to /login
- Valid credentials → home page
- Invalid credentials → error message shown
- Sign out → back to /login"
```
