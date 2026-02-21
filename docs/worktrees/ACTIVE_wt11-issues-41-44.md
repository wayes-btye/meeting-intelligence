# Worktree WT11 — Issues #41 + #44
**Status:** `ACTIVE` — worktree at `C:\meeting-intelligence-wt11-issues-41-44`
**Branch:** `feat/41-44-frontend-polish`
**Created from:** main @ dd2d6ab
**Worktree path:** `C:\meeting-intelligence-wt11-issues-41-44`

---

## Context: What you need to know about this codebase

**The system is a RAG-based meeting intelligence tool.** FastAPI backend, React/Next.js 14 frontend (`/frontend/`), Supabase (pgvector), Claude for generation, OpenAI for embeddings.

**CRITICAL codebase patterns:**
- Frontend lives in `frontend/` — Next.js 14 App Router, shadcn/ui, Tailwind CSS
- Chat page: `frontend/app/chat/page.tsx`
- Meetings page: `frontend/app/meetings/page.tsx`
- 115 tests pass on main. Do not break them.
- mypy is now passing (PR #40) — run `ruff check src/ tests/` and `mypy src/` before PR.
- **This is pure frontend work — no API changes needed.**
- Start frontend only: `cd frontend && npm run dev` (port 3000)
- The main workspace API at `http://localhost:8000` is sufficient. No need to start a separate API instance from this worktree.

---

## Your mission

Two small, independent frontend fixes. Both touch `frontend/` only.

---

## Issue #41 — Markdown rendering in chat answers

### Problem
`frontend/app/chat/page.tsx` renders the answer as plain text (`whitespace-pre-wrap`). Claude's responses contain markdown — bold, headers, bullet lists — that currently displays as raw symbols.

### Install packages

```bash
cd frontend
npm install react-markdown remark-gfm @tailwindcss/typography
```

Add the typography plugin to `frontend/tailwind.config.ts` (or `tailwind.config.js`):
```js
plugins: [require('@tailwindcss/typography')]
```

### Change in `frontend/app/chat/page.tsx`

Find the answer paragraph (around line 155) and replace it:

```tsx
// Add imports at top:
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Replace:
<p className="... whitespace-pre-wrap">{result.answer}</p>

// With:
<div className="prose prose-sm max-w-none dark:prose-invert [&>*:first-child]:mt-0">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
</div>
```

The `prose` Tailwind class from `@tailwindcss/typography` handles all markdown styling cleanly. Dark mode is covered by `dark:prose-invert`.

---

## Issue #44 — Null speaker badge graceful fallback

### Problem
When naive chunking is used (or transcript has no speaker labels), `speaker` is `null`. The speaker badge in chat source cards renders as an empty chip or "undefined".

Same issue on the Meetings page: `num_speakers` can be null and may render as empty.

### Changes

**In `frontend/app/chat/page.tsx`** — source card speaker badge:
```tsx
// Before (renders empty badge when null):
<Badge>{chunk.speaker}</Badge>

// After (only render if speaker is set, otherwise omit or show fallback):
{chunk.speaker ? (
  <Badge variant="secondary">{chunk.speaker}</Badge>
) : (
  <Badge variant="outline" className="text-muted-foreground">Unknown speaker</Badge>
)}
```

**In `frontend/app/meetings/page.tsx`** — num_speakers display:
```tsx
// Wherever num_speakers is displayed, handle null:
{meeting.num_speakers ?? '—'}
```

---

## Definition of done

- [ ] `cd frontend && npm run build` passes (no TypeScript errors)
- [ ] Chat answers with markdown render correctly — bullets, bold, headers
- [ ] Source cards with `speaker: null` show "Unknown speaker" (or omit the badge gracefully)
- [ ] Meetings list shows `—` for null `num_speakers`
- [ ] `pytest tests/ -m "not expensive"` — all pass (no backend changes)
- [ ] `ruff check src/ tests/` — clean
- [ ] `mypy src/` — clean

---

## How to raise the PR

```bash
git add frontend/
git commit -m "feat: markdown rendering in chat + null speaker badge fallback (#41 #44)"
gh pr create \
  --title "feat: markdown rendering in chat answers + null speaker fallback (#41, #44)" \
  --body "Closes #41
Closes #44

## Changes
**#41 — Markdown rendering**
- Install react-markdown, remark-gfm, @tailwindcss/typography
- Replace plain-text paragraph with ReactMarkdown + prose Tailwind classes in chat/page.tsx

**#44 — Null speaker badge**
- Speaker badge in chat source cards shows 'Unknown speaker' when speaker is null
- Meetings list shows '—' for null num_speakers

## Test plan
- npm run build passes
- Claude answer with markdown renders correctly (bullets, bold, headers)
- Upload plain .txt transcript → source cards show fallback, no empty badge
- All pytest tests pass"
```
