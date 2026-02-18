"""Cross-check evaluation: RAG vs context-stuffing comparison.

For each test question, generates answers via both the RAG pipeline
(retrieve + generate) and context-stuffing (full transcript + generate),
then uses Claude as judge to compare.
"""

from __future__ import annotations

import json

from anthropic import Anthropic

from src.config import settings
from src.evaluation.models import (
    CrossCheckResult,
    CrossCheckVerdict,
    TestQuestion,
)
from src.retrieval.generation import generate_answer
from src.retrieval.search import hybrid_search, semantic_search

JUDGE_PROMPT = """\
You are comparing two answers to the same question about a meeting transcript.

QUESTION:
{question}

EXPECTED ANSWER:
{expected_answer}

ANSWER A (RAG — retrieved relevant excerpts):
{rag_answer}

ANSWER B (Context Stuffing — full transcript):
{context_stuffing_answer}

Compare both answers against the expected answer. Consider:
1. Correctness: Which answer is more factually correct?
2. Completeness: Which answer covers more of the expected information?
3. Conciseness: Which answer avoids irrelevant information?

Return a JSON object with exactly:
- "verdict": one of "RAG_BETTER", "CONTEXT_STUFFING_BETTER", or "EQUIVALENT"
- "rag_score": float 0.0-1.0 rating Answer A quality
- "context_stuffing_score": float 0.0-1.0 rating Answer B quality
- "reasoning": brief explanation of your judgment

Return ONLY the JSON object.
"""


def _generate_context_stuffing_answer(
    question: str, transcript: str, max_chars: int = 80000
) -> str:
    """Generate an answer by stuffing the full transcript into context.

    Args:
        question: The question to answer.
        transcript: Full meeting transcript text.
        max_chars: Maximum transcript characters (to stay within token limits).

    Returns:
        The generated answer text.
    """
    truncated = transcript[:max_chars]
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        system=(
            "You are a meeting intelligence assistant. Answer questions based "
            "on the provided meeting transcript.\n\n"
            "Rules:\n"
            "- Only answer based on the provided transcript.\n"
            "- Be concise and direct.\n"
            "- If the answer isn't in the transcript, say so."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Full meeting transcript:\n\n{truncated}\n\nQuestion: {question}",
            }
        ],
    )
    return response.content[0].text


def _generate_rag_answer(
    question: str,
    retrieval_strategy: str = "hybrid",
    meeting_id: str | None = None,
) -> tuple[str, list[dict]]:
    """Generate an answer using the RAG pipeline.

    Args:
        question: The question to answer.
        retrieval_strategy: "semantic" or "hybrid".
        meeting_id: Optional meeting ID filter.

    Returns:
        Tuple of (answer_text, retrieved_chunks).
    """
    if retrieval_strategy == "semantic":
        chunks = semantic_search(question, meeting_id=meeting_id)
    else:
        chunks = hybrid_search(question)

    if not chunks:
        return "No relevant meeting content found.", []

    result = generate_answer(question, chunks)
    return result["answer"], chunks


def _judge_answers(
    question: str,
    expected_answer: str,
    rag_answer: str,
    context_stuffing_answer: str,
) -> dict:
    """Use Claude to judge which answer is better."""
    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_answer=expected_answer,
        rag_answer=rag_answer,
        context_stuffing_answer=context_stuffing_answer,
    )
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def cross_check_question(
    test_question: TestQuestion,
    transcript: str,
    retrieval_strategy: str = "hybrid",
) -> CrossCheckResult:
    """Run cross-check evaluation for a single question.

    Args:
        test_question: The test question with expected answer.
        transcript: Full meeting transcript for context-stuffing.
        retrieval_strategy: "semantic" or "hybrid" for RAG pipeline.

    Returns:
        CrossCheckResult with verdict and scores.
    """
    # Generate RAG answer
    rag_answer, _ = _generate_rag_answer(
        test_question.question,
        retrieval_strategy=retrieval_strategy,
        meeting_id=test_question.source_meeting_id,
    )

    # Generate context-stuffing answer
    cs_answer = _generate_context_stuffing_answer(
        test_question.question, transcript
    )

    # Judge
    try:
        judgment = _judge_answers(
            test_question.question,
            test_question.expected_answer,
            rag_answer,
            cs_answer,
        )
        verdict = CrossCheckVerdict(judgment["verdict"])
        return CrossCheckResult(
            question=test_question,
            rag_answer=rag_answer,
            context_stuffing_answer=cs_answer,
            verdict=verdict,
            reasoning=judgment.get("reasoning", ""),
            rag_score=float(judgment.get("rag_score", 0.0)),
            context_stuffing_score=float(
                judgment.get("context_stuffing_score", 0.0)
            ),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return CrossCheckResult(
            question=test_question,
            rag_answer=rag_answer,
            context_stuffing_answer=cs_answer,
            verdict=CrossCheckVerdict.EQUIVALENT,
            reasoning="Failed to parse judge response; defaulting to EQUIVALENT.",
        )


def run_cross_check(
    questions: list[TestQuestion],
    transcripts: dict[str, str],
    retrieval_strategy: str = "hybrid",
) -> list[CrossCheckResult]:
    """Run cross-check evaluation across all questions.

    Args:
        questions: List of test questions.
        transcripts: Mapping of meeting_id -> transcript text.
        retrieval_strategy: "semantic" or "hybrid".

    Returns:
        List of CrossCheckResult objects.
    """
    results: list[CrossCheckResult] = []
    for q in questions:
        transcript = transcripts.get(q.source_meeting_id, "")
        if not transcript and q.source_meeting_id == "multi":
            # For multi-meeting questions, concatenate all transcripts
            transcript = "\n\n---\n\n".join(transcripts.values())
        if not transcript:
            continue
        result = cross_check_question(q, transcript, retrieval_strategy)
        results.append(result)
    return results


def summarize_cross_check(results: list[CrossCheckResult]) -> dict:
    """Summarize cross-check results into aggregate statistics.

    Returns:
        Dictionary with counts, percentages, and per-category breakdowns.
    """
    if not results:
        return {"total": 0}

    total = len(results)
    counts = {v: 0 for v in CrossCheckVerdict}
    for r in results:
        counts[r.verdict] += 1

    # Per-category breakdown
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.question.category.value
        if cat not in by_category:
            by_category[cat] = {v.value: 0 for v in CrossCheckVerdict}
        by_category[cat][r.verdict.value] += 1

    avg_rag = sum(r.rag_score for r in results) / total
    avg_cs = sum(r.context_stuffing_score for r in results) / total

    return {
        "total": total,
        "rag_better": counts[CrossCheckVerdict.RAG_BETTER],
        "context_stuffing_better": counts[CrossCheckVerdict.CONTEXT_STUFFING_BETTER],
        "equivalent": counts[CrossCheckVerdict.EQUIVALENT],
        "rag_better_pct": counts[CrossCheckVerdict.RAG_BETTER] / total * 100,
        "context_stuffing_better_pct": counts[CrossCheckVerdict.CONTEXT_STUFFING_BETTER] / total * 100,
        "equivalent_pct": counts[CrossCheckVerdict.EQUIVALENT] / total * 100,
        "avg_rag_score": round(avg_rag, 3),
        "avg_context_stuffing_score": round(avg_cs, 3),
        "by_category": by_category,
    }
