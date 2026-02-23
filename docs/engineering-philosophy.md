# Engineering Philosophy — Meeting Intelligence
*This document explains the thinking behind the development approach: not just what was built, but why it was built this way. It is intended for a technical reviewer evaluating lead-level engineering judgement.*

---

## Why Streamlit First, Then React

The project started with a Streamlit frontend. This was a deliberate choice, not a shortcut.

**The initial priority was the RAG pipeline, not the UI.** Streamlit is fast to wire to a Python backend — a working upload-and-query loop was running in hours, not days. That meant evaluation and iteration on the actual RAG logic could start immediately, rather than being blocked on frontend scaffolding.

**The limitation that forced the migration:** As the parameter exposure requirements grew — showing retrieved chunk scores, toggling chunking strategy, displaying similarity thresholds, rendering markdown responses with source cards — Streamlit's component model started fighting against the design. State management across tabs, dynamic component updates, and the kind of interactive debugging panel the RAG work required pushed beyond what Streamlit handles cleanly.

**Why React was the right move (and why it wasn't as costly as it sounds):** Claude Code generates React at a pace that effectively eliminates the "Streamlit is simpler" argument. The barrier between "thin UI" and "good UI" collapses when the scaffolding cost approaches zero. A typed Next.js 14 App Router component with Supabase Auth, proper error handling, and responsive layout takes the same time to produce as a patched Streamlit workaround. Given that, there's no reason to accept the Streamlit limitations.

**What Streamlit is now:** A dev and experimentation tool. It's kept working and updated when the API changes. For rapid prototyping of new features before building them into React — it's still the right tool. But it's not the demo surface.

**The broader principle:** Start with the simplest thing that allows you to make progress on the hard problem. Replace it when it becomes the obstacle, not before.

---

## CI/CD Philosophy — Always Have a Working Demo

Every merge to main automatically produces a running system:

- **Cloud Build** triggers on every push to `main` → builds a Docker image → deploys to Cloud Run (Europe West 1). No GitHub Actions needed for the backend — Cloud Build handles it natively and is faster than Actions for container workloads.
- **Vercel** triggers on every push to `main` → builds the Next.js app → deploys globally. `NEXT_PUBLIC_API_URL` points to the Cloud Run service.

This means the live demo URL (`https://meeting-intelligence-wc.vercel.app`) is always current. After any merged PR, the deployed system reflects the change within ~3 minutes.

**Why this matters at a lead level:**

As a lead, you review PRs without pulling them locally. The auto-deploy means you can merge and immediately verify on the production URL — no "works on my machine" uncertainty. Team contributors can also see their work live immediately after merge, which shortens the feedback loop.

The CI gate (ruff + mypy + pytest) runs on every push via GitHub Actions. Nothing reaches main without passing types, lint, and tests. This is enforced by the pipeline, not by convention.

The backend is deployed as a container to Cloud Run, which means:
- Zero server management
- Scales to zero when idle (cost-efficient for a prototype)
- Scales out under load without configuration
- Consistent runtime between local Docker and production (same image)

---

## Git Worktree Workflow — Parallel Development Without Context Collision

Working on a complex project with multiple concurrent issues presents a choice: context-switch frequently (branch-switching, stashing, losing mental state), or find a way to work in parallel without interference.

**Git worktrees solve this.** Each active issue gets its own directory, its own API port, and its own Claude Code session:

```
meeting-intelligence/           ← main workspace (migrations, merges only)
meeting-intelligence-wt12/     ← Issue #42/#43 (delete meeting + source cards)
meeting-intelligence-wt13/     ← Issue #47 (chunk viewer)
meeting-intelligence-wt15/     ← Issue #49 (RAG parameter display)
```

Each worktree is a full checkout on its own feature branch. Running `PORT=8120 make api` in `wt12` gives you an isolated API at `:8120` while the main workspace runs at `:8000`. You switch between issues by switching terminal tabs, not by running `git stash && git checkout`.

The `docs/worktrees/` directory contains a context file for every worktree — `PLANNED_`, `ACTIVE_`, or `MERGED_` — making the current state visible at a glance in any file explorer.

**The safety rules this workflow imposes (and why):**

The main workspace is the only place that pushes to `main`, applies database migrations, and merges PRs. Worktrees only push their own feature branch. This is enforced by convention (documented in `CLAUDE.md`) — not because git prevents it, but because the consequences of violating it (accidentally pushing worktree work to main, applying a migration mid-feature) are hard to reverse.

**What this looks like to a team:**

A lead can have multiple active worktrees — each with a junior or mid engineer (or an AI agent) working on a separate issue. Each worktree has a context file with the spec, the branch name, and the current status. PRs are raised from worktrees against main. The lead reviews on GitHub, not by pulling branches locally.

The worktree context files serve as structured handoff documents. If you hand a worktree to an engineer or an AI agent, the context file tells them exactly what's in scope, what the acceptance criteria are, and what decisions have already been made.

---

## The `.issues/` Directory — LLM-Native Project Context

The `.issues/` directory is auto-populated nightly by a GitHub Actions workflow (`gh2md`) that exports all GitHub issues and PRs as markdown files. It's committed to the repo.

**The obvious benefit:** Anyone can read the project's full history without GitHub access or CLI setup. Clone the repo, read `.issues/`, and you have everything.

**The less obvious benefit:** It makes the repo an LLM-native context source.

Any LLM that can read a repository can answer questions about the project state without any GitHub authentication — whether that's Claude via MCP, a ChatGPT connector pointing at the repo, or a custom pipeline. Ask "what issues are still open?", "why was the RAGAS approach dropped?", "what were the acceptance criteria for issue #47?" — the answers are in plain markdown files, no API token required.

This matters in a multi-LLM workflow (e.g., Claude Code for implementation, a ChatGPT connector for project review, an analyst querying issue history). Each tool reads the same source of truth without needing API integrations between them.

The nightly update means the exported files lag by at most 24 hours — acceptable for planning contexts.

---

## RAG Thinking — Stages, Not a Single Choice

The conventional approach to building a RAG system is to pick a strategy, implement it, and ship. That's fast. It's also how you end up with a system where "RAG" is doing things SQL or a direct LLM call would do better, and where you have no idea whether the retrieval is actually helping.

This project takes a different approach: **build infrastructure to compare strategies, so choices are evidence-based rather than intuition-based.**

### The stages implemented

**Stage 1 — Naive RAG (baseline)**
Fixed-window chunking, cosine similarity retrieval, generate. This is the baseline — everything else is measured against it.

**Stage 2 — Hybrid retrieval**
Vector similarity + full-text keyword matching, combined with configurable weights (default 70% vector, 30% FTS). Full-text search handles exact keyword matches that semantic search misses — proper nouns, technical terms, short specific phrases. The combination consistently outperforms either alone on meeting corpora.

**Stage 3 — Speaker-turn chunking**
One chunk per continuous speaker segment rather than fixed-window splits. Meeting transcripts have a property that makes this important: **speaker attribution is semantically load-bearing**. "What did the CTO commit to?" requires the commitment and the speaker label to be in the same chunk. Fixed-window chunking can split them. Speaker-turn chunking preserves the natural semantic unit.

**Stage 4 — Query routing (knowing when NOT to use RAG)**
Not everything goes through the vector pipeline. A query router classifies each incoming query:
- Structured queries ("list all action items assigned to Sarah") → direct SQL — deterministic, cheaper, no retrieval noise
- Open-ended queries ("what was the team's position on the migration?") → RAG pipeline

This is architecturally more important than any retrieval optimisation. Applying probabilistic retrieval to structured lookups of known entities is simply the wrong tool.

**Stage 5 — Direct LLM for single-document extraction**
Structured extraction (action items, decisions, topics) from a single known transcript uses a full-context direct LLM call, not retrieval. The transcript fits in context. You want the model to see the complete picture. Retrieval would introduce noise.

### The roadmap stages (not yet implemented)

**Stage 6 — Contextual retrieval**
Before embedding each chunk, prepend a brief document-level context generated by Claude ("This is from a Q3 planning meeting..."). Anthropic's research shows a 67% reduction in retrieval failures when combined with reranking. Implementation path is clear.

**Stage 7 — Cross-encoder reranking**
A second-stage reranker re-scores top-K retrieved chunks using the full query-chunk pair (not just embedding similarity). Benchmarks show 15–40% precision improvement. Adds latency — needs to be measured against quality gain.

**Stage 8 — Evaluation-driven weight tuning**
The current hybrid weights (70/30) are defaults. With the evaluation framework producing data, you can grid-search weight combinations across query categories to find optimal settings per query type. This is the right way to set these numbers — not by intuition.

### Why multiple strategies rather than one optimised approach

A single optimised strategy gives you a number. Multiple strategies give you a model of when each technique helps. The evaluation framework (cross-check: RAG vs context-stuffing) was specifically designed to answer: "Does retrieval genuinely help for this query type, or is direct context-stuffing just as good?" That's a more valuable deliverable than a high score on one benchmark.

---

## Testing Philosophy — The Contract Before the Code

Tests are not a hygiene check added after the fact. They're the specification that makes confident iteration possible.

**External services are always mocked in regular tests.** AssemblyAI, OpenAI embeddings, Supabase, Claude API — all are patched with `unittest.mock.patch`. Tests pass with no API keys set. This means CI runs without secrets, tests are fast, and a new contributor can run the full suite immediately after clone.

**Live API tests are explicitly marked `@pytest.mark.expensive`.** When a test genuinely requires a real API call, it's marked and excluded from the default `make test` run. You invoke expensive tests deliberately, knowing the cost.

**The evaluation framework is itself tested.** `tests/test_evaluation.py` (512 lines) covers every metric implementation, cross-check verdict logic, test set persistence, strategy comparison tables, and report generation. The evaluation infrastructure is not special-cased — it follows the same standards as everything else.

**Pre-merge gate:** CI runs `ruff check` (linter), `mypy src/` (type checking), and `pytest -m "not expensive"` on every push. Nothing merges with a failing check.

**What this enables at a lead level:** When a team member raises a PR, the CI result answers "does this break anything?" before the code review starts. Type errors are caught before the review, not in it. The reviewer can focus on architecture and logic. For an AI-assisted development workflow — as used here — the test suite is particularly important: generated code may look correct and subtly not be. The test suite is the mechanism that catches the subtle errors.
