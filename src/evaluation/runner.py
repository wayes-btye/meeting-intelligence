"""Evaluation runner: orchestrates the full evaluation pipeline.

Ties together test set generation, metric evaluation, cross-check comparison,
and strategy comparison into a single workflow that produces a markdown report.
"""

from __future__ import annotations

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
