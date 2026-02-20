"""Evaluation runner: orchestrates the full evaluation pipeline.

Ties together test set generation, metric evaluation, cross-check comparison,
and strategy comparison into a single workflow that produces a markdown report.

Entry point
-----------
Run as a module::

    python -m src.evaluation.runner \\
        --meetings meeting-001 meeting-002 \\
        --output reports/eval_results \\
        --strategies naive:semantic speaker_turn:hybrid

Use ``--help`` for full argument documentation.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime

from src.evaluation.compare_strategies import (
    STRATEGY_COMBINATIONS,
    compare_all_strategies,
    format_comparison_table,
)
from src.evaluation.cross_check import run_cross_check, summarize_cross_check
from src.evaluation.generate_test_set import (
    generate_test_set,
    load_test_set,
    save_test_set,
)
from src.evaluation.models import (
    StrategyResult,
    TestQuestion,
)


def _generate_or_load_test_set(
    transcripts: dict[str, str],
    test_set_path: str | None = None,
) -> list[TestQuestion]:
    """Load an existing test set or generate a new one.

    Args:
        transcripts: Meeting transcripts (needed only for generation).
        test_set_path: Path to existing test set JSON. If None or file doesn't
            exist, generates a new test set.

    Returns:
        List of test questions.
    """
    if test_set_path and os.path.exists(test_set_path):
        return load_test_set(test_set_path)

    questions = generate_test_set(transcripts)

    # Save for reuse
    out_path = test_set_path or "data/test_set.json"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    save_test_set(questions, out_path)

    return questions


def _format_test_set_summary(questions: list[TestQuestion]) -> str:
    """Format a summary of the test set composition."""
    by_category: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    for q in questions:
        by_category[q.category.value] = by_category.get(q.category.value, 0) + 1
        by_difficulty[q.difficulty.value] = by_difficulty.get(q.difficulty.value, 0) + 1

    lines = [
        f"**Total questions:** {len(questions)}\n",
        "**By category:**\n",
    ]
    for cat, count in sorted(by_category.items()):
        lines.append(f"- {cat}: {count}")
    lines.append("\n**By difficulty:**\n")
    for diff, count in sorted(by_difficulty.items()):
        lines.append(f"- {diff}: {count}")

    return "\n".join(lines)


def _format_cross_check_section(summary: dict) -> str:
    """Format the cross-check results as markdown."""
    if summary.get("total", 0) == 0:
        return "No cross-check results available.\n"

    lines = [
        f"**Total comparisons:** {summary['total']}\n",
        f"- RAG better: {summary['rag_better']} ({summary['rag_better_pct']:.1f}%)",
        f"- Context stuffing better: {summary['context_stuffing_better']} "
        f"({summary['context_stuffing_better_pct']:.1f}%)",
        f"- Equivalent: {summary['equivalent']} ({summary['equivalent_pct']:.1f}%)\n",
        f"**Average RAG score:** {summary['avg_rag_score']}",
        f"**Average context-stuffing score:** {summary['avg_context_stuffing_score']}\n",
    ]

    # Per-category breakdown
    by_cat = summary.get("by_category", {})
    if by_cat:
        lines.append("**By category:**\n")
        lines.append("| Category | RAG Better | CS Better | Equivalent |")
        lines.append("|----------|-----------|-----------|------------|")
        for cat, counts in sorted(by_cat.items()):
            lines.append(
                f"| {cat} | {counts.get('RAG_BETTER', 0)} | "
                f"{counts.get('CONTEXT_STUFFING_BETTER', 0)} | "
                f"{counts.get('EQUIVALENT', 0)} |"
            )

    return "\n".join(lines)


def generate_report(
    questions: list[TestQuestion],
    strategy_results: list[StrategyResult],
    cross_check_summary: dict | None = None,
) -> str:
    """Generate a full markdown evaluation report.

    Args:
        questions: The test set used for evaluation.
        strategy_results: Results from strategy comparison.
        cross_check_summary: Optional cross-check summary dict.

    Returns:
        Markdown-formatted report string.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        f"# Meeting Intelligence Evaluation Report\n\n_Generated: {now}_\n",
        "## 1. Test Set Summary\n",
        _format_test_set_summary(questions),
        "\n## 2. Strategy Comparison\n",
        format_comparison_table(strategy_results),
    ]

    # Find best strategy
    if strategy_results:
        best = max(
            strategy_results,
            key=lambda r: (r.avg_faithfulness + r.avg_relevancy + r.avg_context_precision + r.avg_context_recall) / 4,
        )
        composite = (
            best.avg_faithfulness + best.avg_relevancy + best.avg_context_precision + best.avg_context_recall
        ) / 4
        sections.append(
            f"\n**Best strategy:** {best.chunking_strategy} + {best.retrieval_strategy} "
            f"(composite: {composite:.3f})\n"
        )

    if cross_check_summary:
        sections.append("\n## 3. RAG vs Context Stuffing\n")
        sections.append(_format_cross_check_section(cross_check_summary))

    sections.append("\n---\n_Report generated by Meeting Intelligence Evaluation Framework_\n")

    return "\n".join(sections)


def run_evaluation(
    transcripts: dict[str, str],
    test_set_path: str | None = None,
    output_dir: str = "data/eval_results",
    strategies: list[tuple[str, str]] | None = None,
    run_cross_check_eval: bool = True,
    retrieval_strategy_for_cross_check: str = "hybrid",
) -> str:
    """Run the complete evaluation pipeline.

    Args:
        transcripts: Mapping of meeting_id -> transcript text.
        test_set_path: Path to existing test set JSON, or None to generate.
        output_dir: Directory to write results.
        strategies: Strategy combinations to evaluate. Defaults to all four.
        run_cross_check_eval: Whether to run RAG vs context-stuffing comparison.
        retrieval_strategy_for_cross_check: Retrieval strategy for cross-check.

    Returns:
        Path to the generated markdown report.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Load or generate test set
    questions = _generate_or_load_test_set(transcripts, test_set_path)

    # Step 2: Run strategy comparison
    combos = strategies or STRATEGY_COMBINATIONS
    strategy_results = compare_all_strategies(questions, combos)

    # Save raw strategy results
    strategy_data = [
        {
            "chunking_strategy": r.chunking_strategy,
            "retrieval_strategy": r.retrieval_strategy,
            "avg_faithfulness": r.avg_faithfulness,
            "avg_relevancy": r.avg_relevancy,
            "avg_context_precision": r.avg_context_precision,
            "avg_context_recall": r.avg_context_recall,
            "num_questions": r.num_questions,
        }
        for r in strategy_results
    ]
    with open(os.path.join(output_dir, "strategy_results.json"), "w") as f:
        json.dump(strategy_data, f, indent=2)

    # Step 3: Cross-check (optional)
    cross_check_summary: dict | None = None
    if run_cross_check_eval:
        cc_results = run_cross_check(
            questions, transcripts, retrieval_strategy_for_cross_check
        )
        cross_check_summary = summarize_cross_check(cc_results)
        with open(os.path.join(output_dir, "cross_check_results.json"), "w") as f:
            json.dump(cross_check_summary, f, indent=2, default=str)

    # Step 4: Generate report
    report = generate_report(questions, strategy_results, cross_check_summary)
    report_path = os.path.join(output_dir, "evaluation_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report_path


# ── CLI entry point ────────────────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the evaluation runner."""
    parser = argparse.ArgumentParser(
        prog="python -m src.evaluation.runner",
        description=(
            "Meeting Intelligence Evaluation Runner\n\n"
            "Orchestrates the full evaluation pipeline: generates or loads a test set,\n"
            "runs strategy comparison (chunking x retrieval), optionally runs RAG vs\n"
            "context-stuffing cross-check, and writes a markdown report.\n\n"
            "Implementation note: metrics are computed using Claude-as-judge -- NOT\n"
            "RAGAS or DeepEval libraries. See src/evaluation/metrics.py for details."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--meetings",
        nargs="+",
        metavar="MEETING_ID",
        required=False,
        default=None,
        help=(
            "One or more meeting IDs to evaluate (as stored in Supabase). "
            "Transcripts are fetched from the database. "
            "If omitted, a pre-existing --test-set must be supplied."
        ),
    )
    parser.add_argument(
        "--output",
        default="reports/eval_results",
        metavar="OUTPUT_DIR",
        help=(
            "Directory where results are written (default: reports/eval_results). "
            "Created if it does not exist. "
            "Produces: strategy_results.json, cross_check_results.json, "
            "evaluation_report.md."
        ),
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        metavar="CHUNKING:RETRIEVAL",
        default=None,
        help=(
            "Strategy combinations to evaluate, in CHUNKING:RETRIEVAL format. "
            "Valid chunking values: naive, speaker_turn. "
            "Valid retrieval values: semantic, hybrid. "
            "Example: --strategies naive:semantic speaker_turn:hybrid. "
            "Defaults to all four combinations."
        ),
    )
    parser.add_argument(
        "--test-set",
        metavar="PATH",
        default=None,
        help=(
            "Path to an existing test set JSON file. If provided and the file exists, "
            "test set generation is skipped. If omitted, a new test set is generated "
            "from the supplied meeting transcripts and saved to data/test_set.json."
        ),
    )
    parser.add_argument(
        "--no-cross-check",
        action="store_true",
        default=False,
        help="Skip the RAG vs context-stuffing cross-check (faster, no cross-check report).",
    )

    return parser


def _parse_strategy(s: str) -> tuple[str, str]:
    """Parse a 'chunking:retrieval' strategy string into a tuple.

    Raises ValueError if the format is invalid.
    """
    valid_chunking = {"naive", "speaker_turn"}
    valid_retrieval = {"semantic", "hybrid"}

    if ":" not in s:
        msg = f"Invalid strategy format {s!r}. Expected CHUNKING:RETRIEVAL, e.g. naive:semantic."
        raise ValueError(msg)

    chunking, retrieval = s.split(":", 1)
    if chunking not in valid_chunking:
        msg = f"Unknown chunking strategy {chunking!r}. Valid: {sorted(valid_chunking)}"
        raise ValueError(msg)
    if retrieval not in valid_retrieval:
        msg = f"Unknown retrieval strategy {retrieval!r}. Valid: {sorted(valid_retrieval)}"
        raise ValueError(msg)

    return (chunking, retrieval)


def _load_transcripts_from_supabase(meeting_ids: list[str]) -> dict[str, str]:
    """Fetch transcript text for the given meeting IDs from Supabase.

    Returns a mapping of meeting_id -> raw transcript text.
    Raises RuntimeError if a meeting ID cannot be found.

    # MANUAL TEST REQUIRED: requires live SUPABASE_URL + SUPABASE_KEY in .env
    """
    # Import here to avoid forcing DB connection at import time
    from src.config import settings
    from supabase import create_client  # type: ignore[import-untyped]

    client = create_client(settings.supabase_url, settings.supabase_key)
    transcripts: dict[str, str] = {}

    for mid in meeting_ids:
        result = (
            client.table("meetings")
            .select("meeting_id, transcript_text")
            .eq("meeting_id", mid)
            .single()
            .execute()
        )
        if not result.data:
            msg = f"Meeting '{mid}' not found in Supabase. Load it first via the ingest endpoint."
            raise RuntimeError(msg)
        transcripts[mid] = result.data["transcript_text"]

    return transcripts


if __name__ == "__main__":
    import sys

    parser = _build_arg_parser()
    args = parser.parse_args()

    # Validate: need either --meetings or --test-set
    if not args.meetings and not args.test_set:
        parser.error(
            "Provide at least one of --meetings (to generate a test set from transcripts) "
            "or --test-set (to reuse an existing test set)."
        )

    # Parse strategy combinations if provided
    strategies: list[tuple[str, str]] | None = None
    if args.strategies:
        try:
            strategies = [_parse_strategy(s) for s in args.strategies]
        except ValueError as exc:
            parser.error(str(exc))

    # Load transcripts if meeting IDs were supplied
    transcripts: dict[str, str] = {}
    if args.meetings:
        print(f"Fetching transcripts for {len(args.meetings)} meeting(s) from Supabase …")
        try:
            transcripts = _load_transcripts_from_supabase(args.meetings)
        except Exception as exc:
            print(f"ERROR: Could not load transcripts: {exc}", file=sys.stderr)
            sys.exit(1)

    print(
        f"Running evaluation — output dir: {args.output!r}, "
        f"strategies: {strategies or 'all four'}, "
        f"cross-check: {not args.no_cross_check}"
    )

    report_path = run_evaluation(
        transcripts=transcripts,
        test_set_path=args.test_set,
        output_dir=args.output,
        strategies=strategies,
        run_cross_check_eval=not args.no_cross_check,
    )

    print(f"\nEvaluation complete. Report: {report_path}")
    sys.exit(0)
