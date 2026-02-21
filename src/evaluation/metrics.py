"""RAGAS-style evaluation metrics using Claude as judge.

Each metric returns a 0-1 score with reasoning. Metrics implemented:
- Faithfulness: Is the answer grounded in the retrieved context?
- Answer Relevancy: Does the answer address the question?
- Context Precision: Are the retrieved contexts relevant to the question?
- Context Recall: Does the context contain the information needed for the expected answer?
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock

from src.config import settings
from src.evaluation.models import MetricResult

FAITHFULNESS_PROMPT = """\
You are evaluating the faithfulness of a generated answer. Faithfulness measures \
whether every claim in the answer is supported by the provided context.

CONTEXT:
{context}

ANSWER:
{answer}

Score the faithfulness from 0.0 to 1.0:
- 1.0: Every claim in the answer is directly supported by the context.
- 0.5: Some claims are supported, others are not verifiable from context.
- 0.0: The answer contains claims that contradict or are unsupported by the context.

Return a JSON object with exactly:
- "score": a float between 0.0 and 1.0
- "reasoning": a brief explanation

Return ONLY the JSON object.
"""

ANSWER_RELEVANCY_PROMPT = """\
You are evaluating how relevant an answer is to the asked question.

QUESTION:
{question}

ANSWER:
{answer}

Score the answer relevancy from 0.0 to 1.0:
- 1.0: The answer directly and completely addresses the question.
- 0.5: The answer partially addresses the question or includes unnecessary information.
- 0.0: The answer does not address the question at all.

Return a JSON object with exactly:
- "score": a float between 0.0 and 1.0
- "reasoning": a brief explanation

Return ONLY the JSON object.
"""

CONTEXT_PRECISION_PROMPT = """\
You are evaluating context precision. This measures whether the retrieved \
context chunks are relevant to answering the question.

QUESTION:
{question}

RETRIEVED CONTEXT CHUNKS:
{context}

For each chunk, determine if it is relevant to answering the question. \
Context precision is the fraction of retrieved chunks that are relevant.

Score from 0.0 to 1.0:
- 1.0: All retrieved chunks are relevant.
- 0.5: About half are relevant.
- 0.0: None of the chunks are relevant.

Return a JSON object with exactly:
- "score": a float between 0.0 and 1.0
- "reasoning": a brief explanation

Return ONLY the JSON object.
"""

CONTEXT_RECALL_PROMPT = """\
You are evaluating context recall. This measures whether the retrieved context \
contains the information needed to produce the expected answer.

EXPECTED ANSWER:
{expected_answer}

RETRIEVED CONTEXT:
{context}

Determine what fraction of the claims in the expected answer can be found in \
or inferred from the retrieved context.

Score from 0.0 to 1.0:
- 1.0: All information needed for the expected answer is present in the context.
- 0.5: About half the needed information is present.
- 0.0: The context contains none of the needed information.

Return a JSON object with exactly:
- "score": a float between 0.0 and 1.0
- "reasoning": a brief explanation

Return ONLY the JSON object.
"""


def _call_claude_judge(prompt: str) -> dict[str, Any]:
    """Call Claude as a judge and parse the JSON response."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    # Narrow union content block to TextBlock — we send plain text prompts. (#30)
    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise ValueError(f"Expected TextBlock from Claude judge, got {type(block).__name__}")
    text = block.text.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)

    result: dict[str, Any] = json.loads(text)
    return result


def _clamp_score(score: float) -> float:
    """Clamp a score to [0.0, 1.0]."""
    return max(0.0, min(1.0, float(score)))


def _format_contexts(contexts: list[str]) -> str:
    """Format a list of context strings into numbered chunks."""
    parts = [f"[Chunk {i + 1}]: {ctx}" for i, ctx in enumerate(contexts)]
    return "\n\n".join(parts)


def score_faithfulness(answer: str, contexts: list[str]) -> MetricResult:
    """Score how faithful the answer is to the retrieved contexts.

    Args:
        answer: The generated answer text.
        contexts: List of retrieved context strings.

    Returns:
        MetricResult with score 0-1 and reasoning.
    """
    prompt = FAITHFULNESS_PROMPT.format(
        context=_format_contexts(contexts),
        answer=answer,
    )
    try:
        result = _call_claude_judge(prompt)
        return MetricResult(
            score=_clamp_score(result["score"]),
            reasoning=result.get("reasoning", ""),
            metric_name="faithfulness",
        )
    except (json.JSONDecodeError, KeyError):
        return MetricResult(score=0.0, reasoning="Failed to parse judge response", metric_name="faithfulness")


def score_answer_relevancy(question: str, answer: str) -> MetricResult:
    """Score how relevant the answer is to the question.

    Args:
        question: The original question.
        answer: The generated answer text.

    Returns:
        MetricResult with score 0-1 and reasoning.
    """
    prompt = ANSWER_RELEVANCY_PROMPT.format(
        question=question,
        answer=answer,
    )
    try:
        result = _call_claude_judge(prompt)
        return MetricResult(
            score=_clamp_score(result["score"]),
            reasoning=result.get("reasoning", ""),
            metric_name="answer_relevancy",
        )
    except (json.JSONDecodeError, KeyError):
        return MetricResult(score=0.0, reasoning="Failed to parse judge response", metric_name="answer_relevancy")


def score_context_precision(question: str, contexts: list[str]) -> MetricResult:
    """Score what fraction of retrieved contexts are relevant to the question.

    Args:
        question: The original question.
        contexts: List of retrieved context strings.

    Returns:
        MetricResult with score 0-1 and reasoning.
    """
    prompt = CONTEXT_PRECISION_PROMPT.format(
        question=question,
        context=_format_contexts(contexts),
    )
    try:
        result = _call_claude_judge(prompt)
        return MetricResult(
            score=_clamp_score(result["score"]),
            reasoning=result.get("reasoning", ""),
            metric_name="context_precision",
        )
    except (json.JSONDecodeError, KeyError):
        return MetricResult(score=0.0, reasoning="Failed to parse judge response", metric_name="context_precision")


def score_context_recall(
    expected_answer: str, contexts: list[str]
) -> MetricResult:
    """Score whether the context contains information needed for the expected answer.

    Args:
        expected_answer: The ground-truth expected answer.
        contexts: List of retrieved context strings.

    Returns:
        MetricResult with score 0-1 and reasoning.
    """
    prompt = CONTEXT_RECALL_PROMPT.format(
        expected_answer=expected_answer,
        context=_format_contexts(contexts),
    )
    try:
        result = _call_claude_judge(prompt)
        return MetricResult(
            score=_clamp_score(result["score"]),
            reasoning=result.get("reasoning", ""),
            metric_name="context_recall",
        )
    except (json.JSONDecodeError, KeyError):
        return MetricResult(score=0.0, reasoning="Failed to parse judge response", metric_name="context_recall")


def evaluate_all_metrics(
    question: str,
    expected_answer: str,
    generated_answer: str,
    contexts: list[str],
) -> dict[str, MetricResult]:
    """Run all four metrics and return results.

    Args:
        question: The original question.
        expected_answer: The ground-truth expected answer.
        generated_answer: The answer generated by the RAG pipeline.
        contexts: List of retrieved context strings.

    Returns:
        Dictionary mapping metric name to MetricResult.
    """
    return {
        "faithfulness": score_faithfulness(generated_answer, contexts),
        "answer_relevancy": score_answer_relevancy(question, generated_answer),
        "context_precision": score_context_precision(question, contexts),
        "context_recall": score_context_recall(expected_answer, contexts),
    }
