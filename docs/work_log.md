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
