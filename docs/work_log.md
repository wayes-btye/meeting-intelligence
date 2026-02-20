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
