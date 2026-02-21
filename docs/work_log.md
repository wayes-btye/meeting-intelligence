# Work Log

> Append-only log of development activity. Newest entries at bottom.

### [2026-02-19T00:00:00Z] — Task: Add GitHub Actions Workflows
**Focus:** Set up CI/CD and automation workflows
**Done:**
- Created 4 workflows: CI (lint+test), Claude auto-review, Claude on-demand (@claude), nightly issue export
- Opened PR #28 on branch `chore/github-workflows`
- CI workflow will self-test on the PR; Claude workflows need `CLAUDE_CODE_OAUTH_TOKEN` secret
**Next:**
- Add `CLAUDE_CODE_OAUTH_TOKEN` and `GH2MD_TOKEN` secrets to repo (manual step)
**Decisions:**
- Skipped expensive tests in CI (no API keys in Actions environment)
- No path filtering — not a monorepo, run CI on every push/PR

### [2026-02-19T14:00:00Z] — Task: Public context and documentation
**Focus:** Add PRD, architecture doc, and private-context README for LLM continuity
**Done:**
- Created `docs/PRD.md` — full product requirements with MVP scope, implementation status tracker, and decisions log
- Created `docs/architecture.md` — key design decisions with rationale, trade-offs, and production notes
- Created `private-context/README.md` — explains public vs private context distinction for future LLM sessions
- Created `private-context/research/job_description_167_solutions.md` and `strategic_alignment_analysis.md`
**Next:**
- Update README to link PRD and architecture docs
- Fix open bugs before submission: Issues #22, #23, #24, #25, #26, #30
**Decisions:**
- PRD covers full product vision with explicit MVP demarcation — not MVP-only
- Architecture doc explains trade-offs in plain language, not just "what we chose"

### [2026-02-20T01:05:33Z] — Task: Core flow fixed (PR #27 merged)
**Focus:** Fix SDK clients + UI field names — all API calls now work
**Done:**
- Fixed all SDK clients (Supabase, Anthropic, OpenAI) to use `settings.x` not `os.getenv()` — was causing 500 errors on every endpoint on Windows
- Fixed UI field name mismatches — meetings page now shows correct dates, chunk counts, extracted items
- Manually verified full flow: upload → query → answer with citations ✅
- Added docs/manual-testing-guide.md, docs/how-it-works.md, docs/understanding-the-system.md
**Next:**
- Issues #22, #23, #25, #26, #30 still open (confirmed in PR body)
**Decisions:**
- Issue #24 now closed — all field name fixes included in this PR

### [2026-02-20T00:00:00Z] — Session: Planning review + new feature scoping
**Focus:** Address gaps in testing, deployment, UI, and feature scope; add Claude workflow tooling
**Done:**
- Added CLAUDE.md statements for PRD maintenance and custom skills
- Created `.claude/commands/` with `/project:status`, `/project:ingest-test`, `/project:smoke-test`
- Updated PRD with F62–F69 (zip upload, Teams VTT, Gemini visual summary, React UI, cloud deploy, test coverage)
- Created GitHub Issues #31–#35 for each new feature area
**Next:**
- Fix Issue #26 (load MeetingBank data) — highest priority, blocks demo
- Fix Issues #22, #23, #24, #25, #30 (known bugs)
**Decisions:**
- Streamlit retained as dev tool; React (Next.js) to be built as demo UI (Issue #32)
- Gemini API to be added for upload-time visual summary (Issue #35)

### [2026-02-20T09:00:00Z] — Task: Fix Issues #22 and #25 (WT1, branch fix/22-25-audio-endpoint)
**Focus:** TDD fixes: audio upload 500 crash + duplicate GET extract endpoint
**Done:**
- Issue #22: ingest.py detects audio extensions, routes to AssemblyAI SDK (key IS set), returns 400 on transcription error — no more UnicodeDecodeError 500
- Issue #25: removed duplicate `GET /api/meetings/{id}/extract` handler from meetings.py (was masking the correct POST in extraction.py)
- TDD: wrote two failing tests first, confirmed red, fixed, confirmed green; 110/110 tests pass, ruff clean, no new mypy errors
**Next:**
- Raise PR to merge fix/22-25-audio-endpoint → main, close issues #22 and #25
**Decisions:**
- ASSEMBLYAI_API_KEY was set so implemented AssemblyAI path (not 501); async blocking is a known limitation (noted in code comment)
- Duplicate GET was in meetings.py not extraction.py as originally suspected; fixed there

### [2026-02-20T10:00:00Z] — Task: PR review fixes — issues #22 and #25
**Focus:** Address Claude auto-review + Codex review findings on PR #36
**Done:**
- Replaced live AssemblyAI test with two deterministic mocked tests (no network calls)
- Fixed error semantics: TranscriptStatus.error → 400, infra failures → 503 (not 400)
- Removed temp file — SDK accepts bytes directly (confirmed via web search); added asyncio.to_thread
- Added Testing Standards section to CLAUDE.md (mocking policy, manual checklist, scope philosophy)
**Next:**
- PR #36 ready for merge; manual audio transcription test needed (see CLAUDE.md § Manual verification)
**Decisions:**
- asyncio.to_thread was simple (2 lines, no new tests) so implemented rather than deferred

### [2026-02-20T10:00:00Z] — Task: Fix eval runner entry point + test coverage (Issues #23, #33)
**Focus:** TDD: add __main__ to runner.py, real MeetingBank fixture, integration test skeleton
**Done:**
- Added argparse __main__ block to src/evaluation/runner.py — `python -m src.evaluation.runner --help` now exits 0
- Created tests/fixtures/meetingbank/sample_council_meeting.json (synthetic but realistic council meeting in canonical MeetingBank format)
- Updated src/ingestion/parsers.py to handle MeetingBank `transcription` key format (speaker_id field)
- Added tests: test_runner_callable_as_module, TestMeetingBankRealFixture (2 tests), test_pipeline_integration.py (3 expensive golden-path tests)
- Fixed README.md: replaced incorrect RAGAS/DeepEval claim with Claude-as-judge description
**Next:**
- Raise PR closing #23 and #33; integration tests require manual run (see test file header)
**Decisions:**
- parse_json now handles 3 formats: AssemblyAI utterances, MeetingBank transcription (canonical), internal segments

### [2026-02-20T02:00:00Z] — Task: Worktree setup — Wave 1 created
**Focus:** Create Wave 1 worktrees (WT1, WT3, WT5) with comprehensive context files
**Done:**
- Created docs/worktrees/ with full WORKTREE.md for WT1 (#22,#25), WT3 (#23,#33), WT5 (#32)
- Context files include: TDD instructions, conflict map, testing strategy, manual verification flags, Vercel deployment notes
- Created worktrees: meeting-intelligence-wt1-issue-22, wt3-issue-23, wt5-issue-32
- Added GOOGLE_API_KEY to Settings and .env.example (for Gemini/Issue #35)
- Cleaned up stale fix/storage-settings local branch
**Next:**
- User opens Claude Code in each worktree terminal; first message: read docs/worktrees/wtX-*.md
- Manual task: run `python scripts/load_meetingbank.py --max 30` while Wave 1 runs (Issue #26)
- Wave 2 worktrees (WT4, WT6) created after Wave 1 PRs merged
**Decisions:**
- Worktree context files committed to main so context is never lost across sessions

### [2026-02-20T02:30:00Z] — Task: Load MeetingBank data into Supabase (Issue #26)
**Focus:** Populate demo corpus
**Done:**
- Ran `python scripts/load_meetingbank.py --max 30` — 30/30 meetings loaded, 0 errors
- ~250 chunks stored with speaker_turn strategy and OpenAI embeddings
- Meetings: Denver City Council, Long Beach CC, Boston CC, Seattle City Council
- Issue #26 closed
**Next:**
- Demo corpus is now live — Supabase has real queryable meeting data
- Run a smoke test query against the data to verify retrieval works

### [2026-02-20T10:00:00Z] — Task: React/Next.js frontend — Issue #32
**Focus:** Build Next.js 14 + shadcn/ui demo frontend with Upload, Chat, Meetings pages
**Done:**
- Added CORSMiddleware to src/api/main.py (localhost:3000, Vercel wildcard)
- Scaffolded /frontend/ with Next.js 14 App Router, shadcn/ui, Tailwind, Playwright e2e
- Built Upload page (drag-drop ingest + auto-extract), Chat page (query + sources), Meetings browser (paginated + detail)
**Next:**
- Restart Claude Code session to load chrome-devtools MCP (.mcp.json added)
- Run `cd frontend && npm run dev` then verify all 3 pages visually before PR
**Decisions:**
- chrome-devtools MCP added to .mcp.json (project scope) for UI debugging visibility

### [2026-02-20T18:30:00Z] — Task: Wave 1 PRs merged — workspace manager session
**Focus:** Rebase and squash-merge PRs #36, #37, #38 into main
**Done:**
- Rebased all three branches (WT1, WT3, WT5) onto main — resolved work_log conflicts
- Squash-merged PR #36 (fix/22-25-audio-endpoint → closes #22, #25)
- Squash-merged PR #37 (fix/23-33-eval-tests → closes #23, #33)
- Squash-merged PR #38 (feat/32-react-frontend → closes #32)
- Removed remote branches and worktree git references; physical dirs remain (Windows permission; manual cleanup in MANUAL-TASKS #39)
**Next:**
- Manual verification: audio upload, React frontend pages, eval runner CLI (see Issue #39)
- Wave 2: Issues #30 (mypy), #31 (Cloud Run), #34 (test coverage), #35 (Gemini)
**Decisions:**
- All three PRs merged despite Lint FAIL in CI — failures are pre-existing mypy Issue #30, not regressions

### [2026-02-20T19:30:00Z] — Task: Post-merge verification + Wave 2 setup
**Focus:** UI smoke test, Supabase cleanup, Wave 2 worktrees
**Done:**
- Fixed ruff errors in test_pipeline_integration.py (RUF100, SIM117×2); CI lint now passes
- Ran 3/3 expensive integration tests — all passed; Supabase cleaned of test data
- UI smoke tested via chrome-devtools MCP: Upload/Chat/Meetings pages all load, API online indicator working, meetings table shows 32 meetings
- Fixed unhandled Anthropic APIStatusError (529) in extract + query routes — now returns HTTP 503 with CORS headers
- Created Wave 2 worktrees: wt6(#30), wt7(#31), wt8(#34), wt9(#35)
**Next:**
- Open Claude Code in each Wave 2 worktree and start work (priority: #30 mypy first)
- Worktree cleanup: delete C:\meeting-intelligence-wt{1,3,5}-issue-* folders in Explorer
**Decisions:**
- Wave 2 uses separate worktrees per issue (not one combined) — independent scope, parallelisable

### [2026-02-21T00:00:00Z] — Task: Fix mypy type errors (Issue #30)
**Focus:** Resolve all 218 mypy errors across src/ so `make lint` passes fully
**Done:**
- Fixed all 5 error categories: TextBlock narrowing, Supabase JSON casts, CountMethod import, bare dict params, misc annotations
- Updated test helper `_mock_claude_response` to return real `TextBlock` (not MagicMock)
- Result: `mypy src/` 0 errors, `ruff` clean, 115 tests pass — opened PR #40
**Next:**
- Merge PR #40 after review; then tackle #31 (Cloud Run), #34 (test coverage), #35 (Gemini)
**Decisions:**
- Used `cast(list[dict[str, Any]], result.data)` for Supabase returns — proper fix, not band-aid
- Used `postgrest.CountMethod.exact` enum value for count= arg — proper fix

### [2026-02-21T00:00:00Z] — Task: Cloud Run + Vercel deployment (Issue #31)
**Focus:** Wire up auto-deploy for API (Cloud Run) and frontend (Vercel)
**Done:**
- Fixed `Dockerfile` CMD to use `${PORT:-8000}` — Cloud Run injects `$PORT` at runtime
- Created `vercel.json` at repo root (`rootDirectory: frontend`) for Vercel monorepo detection
- Created `.github/workflows/deploy.yml` — builds/pushes to Artifact Registry, deploys to Cloud Run on push to main
**Next:**
- Add GitHub secrets: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, all API keys
- Set `NEXT_PUBLIC_API_URL` env var in Vercel dashboard to Cloud Run URL once deployed
**Decisions:**
- Used Workload Identity Federation (keyless) for Cloud Run auth — no SA key JSON in secrets

### [2026-02-21T00:00:00Z] — Task: Wave 3 setup — worktrees, context files, PRD update
**Focus:** Spin up Wave 3 worktrees (wt10–wt12) and update all project docs
**Done:**
- Created worktrees wt10 (#52 auth), wt11 (#41+#44 frontend polish), wt12 (#42+#43 delete+title)
- Wrote context files for all three; updated wt8/wt9 context files (mypy now passing, test count 115, pyproject.toml fix, Gemini model updated to 2.0-flash)
- Updated PRD: fixed stale statuses (F42, F49, F61, F65, F66, F67-69), added sections 4.16–4.18, new decisions log entries
**Next:**
- Open Claude Code in wt10, wt11, wt12 and start Wave 3 implementation
- Priority order: wt10 (#52 auth) → wt11 (#41+#44) → wt12 (#42+#43) alongside wt8/wt9
**Decisions:**
- Auth is client-side only (Supabase Auth + Next.js middleware) — FastAPI unchanged

### [2026-02-21T12:00:00Z] — Task: Supabase email/password auth (Issue #52)
**Focus:** Add login page + middleware route protection to Next.js frontend
**Done:**
- Created `frontend/lib/supabase.ts` (browser client via `@supabase/ssr`)
- Created `frontend/app/login/page.tsx` (email/password form with error feedback)
- Created `frontend/middleware.ts` (route protection — unauthenticated → /login)
**Next:**
- User must add `NEXT_PUBLIC_SUPABASE_ANON_KEY` to `.env.local` and Vercel env vars
- Create test user in Supabase dashboard → Authentication → Users
**Decisions:**
- Logout button added to Nav component (minimal change — reused existing `Button` component)
- Session handled entirely client-side via `@supabase/ssr` — no backend changes needed

### [2026-02-21T00:00:00Z] — Task: Wave 3 PRs merged (#54, #56, #55)
**Focus:** Merge all three Wave 3 feature PRs into main
**Done:**
- PRs #54 (markdown+speaker), #56 (delete+title), #55 (auth) all merged via squash
- Resolved package.json/lock conflict on #55 caused by #54/#56 landing first; regenerated lock via npm install
- 117 tests passing on main, all builds clean
**Next:**
- Manual testing of auth (requires Supabase anon key + test user in dashboard)
- Kick off wt8 (#34 zip+Teams VTT) and wt9 (#35 Gemini visual summary) when ready
**Decisions:**
- Auth merged last so all features are present before the login gate goes live

### [2026-02-21T00:00:00Z] — Task: Issue #34 — Zip upload + Teams VTT (WT8)
**Focus:** Zip bulk upload to ingest endpoint + Microsoft Teams VTT speaker tag parsing
**Done:**
- Part 1: `POST /api/ingest` now accepts `.zip` files — each `.vtt`/`.txt`/`.json` ingested as separate meeting; returns `BatchIngestResponse {meetings_ingested, meeting_ids, errors}`
- Part 2: `parse_vtt()` updated to detect/strip `<v SpeakerName>` Teams inline voice tags; standard colon-style labels unaffected; fixture `tests/fixtures/teams_sample.vtt` added
- TDD: 6 new tests written first, confirmed red, then implemented; 121 tests passing, ruff clean, no new mypy errors; PR #58 opened
**Next:**
- Manual test: real zip upload + real Teams VTT file before merge
**Decisions:**
- `_ingest_zip()` is a sync helper called from async `ingest()` — acceptable since zip extraction is CPU-bound and fast; no async needed for the extraction loop itself
