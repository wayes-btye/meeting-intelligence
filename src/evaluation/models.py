"""Data models for the evaluation framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class QuestionCategory(StrEnum):
    """Categories of test questions."""

    FACTUAL = "factual"
    INFERENCE = "inference"
    MULTI_MEETING = "multi_meeting"
    ACTION_ITEMS = "action_items"
    DECISIONS = "decisions"


class Difficulty(StrEnum):
    """Difficulty levels for test questions."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CrossCheckVerdict(StrEnum):
    """Outcome of a RAG vs context-stuffing comparison."""

    RAG_BETTER = "RAG_BETTER"
    CONTEXT_STUFFING_BETTER = "CONTEXT_STUFFING_BETTER"
    EQUIVALENT = "EQUIVALENT"


@dataclass
class TestQuestion:
    """A single evaluation test question."""

    question: str
    expected_answer: str
    category: QuestionCategory
    difficulty: Difficulty
    source_meeting_id: str
    question_id: str = ""


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    score: float  # 0.0 - 1.0
    reasoning: str
    metric_name: str


@dataclass
class EvaluationResult:
    """Full evaluation result for a single question."""

    question: TestQuestion
    generated_answer: str
    retrieved_contexts: list[str]
    metrics: dict[str, MetricResult] = field(default_factory=dict)


@dataclass
class CrossCheckResult:
    """Result of comparing RAG vs context-stuffing for one question."""

    question: TestQuestion
    rag_answer: str
    context_stuffing_answer: str
    verdict: CrossCheckVerdict
    reasoning: str
    rag_score: float = 0.0
    context_stuffing_score: float = 0.0


@dataclass
class StrategyResult:
    """Aggregated evaluation results for a strategy combination."""

    chunking_strategy: str
    retrieval_strategy: str
    avg_faithfulness: float = 0.0
    avg_relevancy: float = 0.0
    avg_context_precision: float = 0.0
    avg_context_recall: float = 0.0
    num_questions: int = 0
    individual_results: list[EvaluationResult] = field(default_factory=list)
