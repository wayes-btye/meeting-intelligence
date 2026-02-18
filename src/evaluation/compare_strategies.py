"""Strategy comparison: evaluate across chunking + retrieval combinations.

Runs the evaluation pipeline across all strategy combinations:
- Chunking: naive, speaker_turn
- Retrieval: semantic, hybrid

Generates a comparison table with per-strategy metrics.
"""

from __future__ import annotations

from src.evaluation.metrics import evaluate_all_metrics
from src.evaluation.models import EvaluationResult, StrategyResult, TestQuestion
from src.retrieval.generation import generate_answer
from src.retrieval.search import hybrid_search, semantic_search

# All strategy combinations to evaluate
STRATEGY_COMBINATIONS: list[tuple[str, str]] = [
    ("naive", "semantic"),
    ("naive", "hybrid"),
    ("speaker_turn", "semantic"),
    ("speaker_turn", "hybrid"),
]


def _retrieve_and_generate(
    question: str,
    retrieval_strategy: str,
    chunking_strategy: str | None = None,
    meeting_id: str | None = None,
) -> tuple[str, list[str]]:
    """Retrieve context and generate answer for a given strategy combination.

    Args:
        question: The question to answer.
        retrieval_strategy: "semantic" or "hybrid".
        chunking_strategy: Filter chunks by chunking strategy (if supported).
        meeting_id: Optional meeting ID filter.

    Returns:
        Tuple of (generated_answer, list_of_context_strings).
    """
    if retrieval_strategy == "semantic":
        chunks = semantic_search(
            question,
            meeting_id=meeting_id,
            strategy=chunking_strategy,
        )
    else:
        # hybrid_search doesn't support strategy filter yet
        chunks = hybrid_search(question)

    if not chunks:
        return "No relevant meeting content found.", []

    result = generate_answer(question, chunks)
    contexts = [c.get("content", "") for c in chunks]
    return result["answer"], contexts


def evaluate_strategy(
    questions: list[TestQuestion],
    chunking_strategy: str,
    retrieval_strategy: str,
) -> StrategyResult:
    """Evaluate a single strategy combination across all questions.

    Args:
        questions: List of test questions.
        chunking_strategy: "naive" or "speaker_turn".
        retrieval_strategy: "semantic" or "hybrid".

    Returns:
        StrategyResult with aggregated metrics.
    """
    individual_results: list[EvaluationResult] = []

    for q in questions:
        answer, contexts = _retrieve_and_generate(
            q.question,
            retrieval_strategy,
            chunking_strategy=chunking_strategy,
            meeting_id=q.source_meeting_id if q.source_meeting_id != "multi" else None,
        )

        metrics = evaluate_all_metrics(
            question=q.question,
            expected_answer=q.expected_answer,
            generated_answer=answer,
            contexts=contexts,
        )

        individual_results.append(
            EvaluationResult(
                question=q,
                generated_answer=answer,
                retrieved_contexts=contexts,
                metrics=metrics,
            )
        )

    # Aggregate metrics
    n = len(individual_results)
    if n == 0:
        return StrategyResult(
            chunking_strategy=chunking_strategy,
            retrieval_strategy=retrieval_strategy,
        )

    avg_faith = sum(r.metrics["faithfulness"].score for r in individual_results) / n
    avg_relev = sum(r.metrics["answer_relevancy"].score for r in individual_results) / n
    avg_prec = sum(r.metrics["context_precision"].score for r in individual_results) / n
    avg_recall = sum(r.metrics["context_recall"].score for r in individual_results) / n

    return StrategyResult(
        chunking_strategy=chunking_strategy,
        retrieval_strategy=retrieval_strategy,
        avg_faithfulness=round(avg_faith, 3),
        avg_relevancy=round(avg_relev, 3),
        avg_context_precision=round(avg_prec, 3),
        avg_context_recall=round(avg_recall, 3),
        num_questions=n,
        individual_results=individual_results,
    )


def compare_all_strategies(
    questions: list[TestQuestion],
    strategies: list[tuple[str, str]] | None = None,
) -> list[StrategyResult]:
    """Run evaluation across all strategy combinations.

    Args:
        questions: List of test questions.
        strategies: Optional list of (chunking, retrieval) tuples. Defaults
            to STRATEGY_COMBINATIONS.

    Returns:
        List of StrategyResult objects, one per strategy combination.
    """
    combos = strategies or STRATEGY_COMBINATIONS
    results: list[StrategyResult] = []
    for chunking, retrieval in combos:
        result = evaluate_strategy(questions, chunking, retrieval)
        results.append(result)
    return results


def format_comparison_table(results: list[StrategyResult]) -> str:
    """Format strategy comparison results as a markdown table.

    Args:
        results: List of StrategyResult objects.

    Returns:
        Markdown-formatted comparison table string.
    """
    header = (
        "| Chunking | Retrieval | Faithfulness | Relevancy | "
        "Context Precision | Context Recall | N |\n"
        "|----------|-----------|-------------|-----------|"
        "-------------------|----------------|---|\n"
    )
    rows: list[str] = []
    for r in results:
        rows.append(
            f"| {r.chunking_strategy} | {r.retrieval_strategy} | "
            f"{r.avg_faithfulness:.3f} | {r.avg_relevancy:.3f} | "
            f"{r.avg_context_precision:.3f} | {r.avg_context_recall:.3f} | "
            f"{r.num_questions} |"
        )
    return header + "\n".join(rows)
