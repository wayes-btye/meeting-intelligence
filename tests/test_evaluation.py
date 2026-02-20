"""Tests for the evaluation framework.

Tests cover metric calculation logic, cross-check categorization,
test set generation parsing, and report generation format.
API-calling tests are marked with @pytest.mark.expensive.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.evaluation.compare_strategies import format_comparison_table
from src.evaluation.cross_check import summarize_cross_check
from src.evaluation.generate_test_set import (
    _parse_questions_json,
    load_test_set,
    save_test_set,
)
from src.evaluation.metrics import (
    _clamp_score,
    _format_contexts,
    score_answer_relevancy,
    score_context_precision,
    score_context_recall,
    score_faithfulness,
)
from src.evaluation.models import (
    CrossCheckResult,
    CrossCheckVerdict,
    Difficulty,
    MetricResult,
    QuestionCategory,
    StrategyResult,
    TestQuestion,
)
from src.evaluation.runner import generate_report

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_question(**overrides) -> TestQuestion:
    """Create a TestQuestion with sensible defaults."""
    defaults = {
        "question": "What was decided about the budget?",
        "expected_answer": "The budget was set to $1M.",
        "category": QuestionCategory.FACTUAL,
        "difficulty": Difficulty.EASY,
        "source_meeting_id": "meeting-1",
        "question_id": "q-001",
    }
    defaults.update(overrides)
    return TestQuestion(**defaults)


def _mock_claude_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create response."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_response.model = "claude-sonnet-4-20250514"
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_response


# ── Test: Score clamping ─────────────────────────────────────────────────────


class TestClampScore:
    def test_within_range(self) -> None:
        assert _clamp_score(0.5) == 0.5

    def test_below_zero(self) -> None:
        assert _clamp_score(-0.3) == 0.0

    def test_above_one(self) -> None:
        assert _clamp_score(1.5) == 1.0

    def test_boundary_zero(self) -> None:
        assert _clamp_score(0.0) == 0.0

    def test_boundary_one(self) -> None:
        assert _clamp_score(1.0) == 1.0


# ── Test: Context formatting ────────────────────────────────────────────────


class TestFormatContexts:
    def test_formats_numbered(self) -> None:
        result = _format_contexts(["chunk one", "chunk two"])
        assert "[Chunk 1]: chunk one" in result
        assert "[Chunk 2]: chunk two" in result

    def test_empty_list(self) -> None:
        assert _format_contexts([]) == ""


# ── Test: Metrics with mocked Claude ────────────────────────────────────────


class TestMetricsMocked:
    """Test metric functions with mocked Claude API calls."""

    @patch("src.evaluation.metrics.Anthropic")
    def test_faithfulness_returns_metric_result(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            '{"score": 0.85, "reasoning": "Answer is well-grounded."}'
        )

        result = score_faithfulness("The budget is $1M.", ["Budget was set to $1M."])
        assert isinstance(result, MetricResult)
        assert result.score == 0.85
        assert result.metric_name == "faithfulness"
        assert "grounded" in result.reasoning

    @patch("src.evaluation.metrics.Anthropic")
    def test_answer_relevancy(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            '{"score": 0.9, "reasoning": "Directly answers the question."}'
        )

        result = score_answer_relevancy("What is the budget?", "The budget is $1M.")
        assert result.score == 0.9
        assert result.metric_name == "answer_relevancy"

    @patch("src.evaluation.metrics.Anthropic")
    def test_context_precision(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            '{"score": 0.7, "reasoning": "Most chunks relevant."}'
        )

        result = score_context_precision("Budget?", ["Budget info", "Irrelevant"])
        assert result.score == 0.7
        assert result.metric_name == "context_precision"

    @patch("src.evaluation.metrics.Anthropic")
    def test_context_recall(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            '{"score": 1.0, "reasoning": "All info present."}'
        )

        result = score_context_recall("Budget is $1M.", ["Budget set to $1M."])
        assert result.score == 1.0
        assert result.metric_name == "context_recall"

    @patch("src.evaluation.metrics.Anthropic")
    def test_handles_malformed_response(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            "This is not valid JSON at all"
        )

        result = score_faithfulness("answer", ["context"])
        assert result.score == 0.0
        assert "Failed" in result.reasoning

    @patch("src.evaluation.metrics.Anthropic")
    def test_handles_markdown_fences(self, mock_anthropic_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(
            '```json\n{"score": 0.75, "reasoning": "Good answer."}\n```'
        )

        result = score_faithfulness("answer", ["context"])
        assert result.score == 0.75


# ── Test: Cross-check summarization ─────────────────────────────────────────


class TestCrossCheckSummarize:
    def test_empty_results(self) -> None:
        summary = summarize_cross_check([])
        assert summary["total"] == 0

    def test_counts_verdicts(self) -> None:
        q = _make_question()
        results = [
            CrossCheckResult(
                question=q,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.RAG_BETTER,
                reasoning="RAG was more precise",
                rag_score=0.9,
                context_stuffing_score=0.6,
            ),
            CrossCheckResult(
                question=q,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.CONTEXT_STUFFING_BETTER,
                reasoning="CS had more info",
                rag_score=0.5,
                context_stuffing_score=0.8,
            ),
            CrossCheckResult(
                question=q,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.EQUIVALENT,
                reasoning="Both good",
                rag_score=0.7,
                context_stuffing_score=0.7,
            ),
        ]
        summary = summarize_cross_check(results)
        assert summary["total"] == 3
        assert summary["rag_better"] == 1
        assert summary["context_stuffing_better"] == 1
        assert summary["equivalent"] == 1
        assert abs(summary["rag_better_pct"] - 33.3) < 1.0

    def test_average_scores(self) -> None:
        q = _make_question()
        results = [
            CrossCheckResult(
                question=q,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.RAG_BETTER,
                reasoning="",
                rag_score=0.8,
                context_stuffing_score=0.4,
            ),
            CrossCheckResult(
                question=q,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.RAG_BETTER,
                reasoning="",
                rag_score=0.6,
                context_stuffing_score=0.2,
            ),
        ]
        summary = summarize_cross_check(results)
        assert summary["avg_rag_score"] == 0.7
        assert summary["avg_context_stuffing_score"] == 0.3

    def test_per_category_breakdown(self) -> None:
        q_factual = _make_question(category=QuestionCategory.FACTUAL)
        q_action = _make_question(category=QuestionCategory.ACTION_ITEMS)
        results = [
            CrossCheckResult(
                question=q_factual,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.RAG_BETTER,
                reasoning="",
            ),
            CrossCheckResult(
                question=q_action,
                rag_answer="a",
                context_stuffing_answer="b",
                verdict=CrossCheckVerdict.CONTEXT_STUFFING_BETTER,
                reasoning="",
            ),
        ]
        summary = summarize_cross_check(results)
        assert "factual" in summary["by_category"]
        assert summary["by_category"]["factual"]["RAG_BETTER"] == 1
        assert summary["by_category"]["action_items"]["CONTEXT_STUFFING_BETTER"] == 1


# ── Test: Test set JSON parsing ─────────────────────────────────────────────


class TestParseQuestionsJSON:
    def test_plain_json(self) -> None:
        raw = '[{"question": "Q?", "expected_answer": "A."}]'
        result = _parse_questions_json(raw)
        assert len(result) == 1
        assert result[0]["question"] == "Q?"

    def test_with_markdown_fences(self) -> None:
        raw = '```json\n[{"question": "Q?", "expected_answer": "A."}]\n```'
        result = _parse_questions_json(raw)
        assert len(result) == 1

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _parse_questions_json("not json at all")


# ── Test: Test set save/load round-trip ──────────────────────────────────────


class TestTestSetPersistence:
    def test_save_and_load(self) -> None:
        questions = [
            _make_question(question_id="q1"),
            _make_question(
                question_id="q2",
                category=QuestionCategory.INFERENCE,
                difficulty=Difficulty.HARD,
            ),
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        try:
            save_test_set(questions, path)
            loaded = load_test_set(path)
            assert len(loaded) == 2
            assert loaded[0].question_id == "q1"
            assert loaded[1].category == QuestionCategory.INFERENCE
            assert loaded[1].difficulty == Difficulty.HARD
        finally:
            os.unlink(path)


# ── Test: Strategy comparison table ──────────────────────────────────────────


class TestComparisonTable:
    def test_format_produces_markdown(self) -> None:
        results = [
            StrategyResult(
                chunking_strategy="naive",
                retrieval_strategy="semantic",
                avg_faithfulness=0.85,
                avg_relevancy=0.9,
                avg_context_precision=0.8,
                avg_context_recall=0.75,
                num_questions=50,
            ),
            StrategyResult(
                chunking_strategy="speaker_turn",
                retrieval_strategy="hybrid",
                avg_faithfulness=0.88,
                avg_relevancy=0.92,
                avg_context_precision=0.83,
                avg_context_recall=0.78,
                num_questions=50,
            ),
        ]
        table = format_comparison_table(results)
        assert "| Chunking |" in table
        assert "naive" in table
        assert "speaker_turn" in table
        assert "0.850" in table
        assert "0.920" in table

    def test_empty_results(self) -> None:
        table = format_comparison_table([])
        # Should still have the header
        assert "| Chunking |" in table


# ── Test: Report generation ──────────────────────────────────────────────────


class TestReportGeneration:
    def test_generates_markdown_report(self) -> None:
        questions = [
            _make_question(),
            _make_question(
                category=QuestionCategory.DECISIONS,
                difficulty=Difficulty.MEDIUM,
            ),
        ]
        strategy_results = [
            StrategyResult(
                chunking_strategy="naive",
                retrieval_strategy="hybrid",
                avg_faithfulness=0.8,
                avg_relevancy=0.85,
                avg_context_precision=0.75,
                avg_context_recall=0.7,
                num_questions=2,
            ),
        ]
        report = generate_report(questions, strategy_results)
        assert "# Meeting Intelligence Evaluation Report" in report
        assert "Test Set Summary" in report
        assert "Strategy Comparison" in report
        assert "Total questions:** 2" in report
        assert "naive" in report

    def test_report_with_cross_check(self) -> None:
        questions = [_make_question()]
        strategy_results = [
            StrategyResult(
                chunking_strategy="naive",
                retrieval_strategy="semantic",
                avg_faithfulness=0.8,
                avg_relevancy=0.85,
                avg_context_precision=0.75,
                avg_context_recall=0.7,
                num_questions=1,
            ),
        ]
        cross_check_summary = {
            "total": 10,
            "rag_better": 5,
            "context_stuffing_better": 3,
            "equivalent": 2,
            "rag_better_pct": 50.0,
            "context_stuffing_better_pct": 30.0,
            "equivalent_pct": 20.0,
            "avg_rag_score": 0.75,
            "avg_context_stuffing_score": 0.65,
            "by_category": {
                "factual": {
                    "RAG_BETTER": 3,
                    "CONTEXT_STUFFING_BETTER": 1,
                    "EQUIVALENT": 1,
                }
            },
        }
        report = generate_report(questions, strategy_results, cross_check_summary)
        assert "RAG vs Context Stuffing" in report
        assert "Total comparisons:** 10" in report
        assert "50.0%" in report

    def test_report_identifies_best_strategy(self) -> None:
        questions = [_make_question()]
        results = [
            StrategyResult(
                chunking_strategy="naive",
                retrieval_strategy="semantic",
                avg_faithfulness=0.5,
                avg_relevancy=0.5,
                avg_context_precision=0.5,
                avg_context_recall=0.5,
                num_questions=1,
            ),
            StrategyResult(
                chunking_strategy="speaker_turn",
                retrieval_strategy="hybrid",
                avg_faithfulness=0.9,
                avg_relevancy=0.9,
                avg_context_precision=0.9,
                avg_context_recall=0.9,
                num_questions=1,
            ),
        ]
        report = generate_report(questions, results)
        assert "Best strategy:** speaker_turn + hybrid" in report


# ── Test: Model enums ────────────────────────────────────────────────────────


class TestModels:
    def test_question_category_values(self) -> None:
        assert QuestionCategory.FACTUAL.value == "factual"
        assert QuestionCategory.MULTI_MEETING.value == "multi_meeting"

    def test_difficulty_values(self) -> None:
        assert Difficulty.EASY.value == "easy"
        assert Difficulty.HARD.value == "hard"

    def test_cross_check_verdict_values(self) -> None:
        assert CrossCheckVerdict.RAG_BETTER.value == "RAG_BETTER"
        assert CrossCheckVerdict.EQUIVALENT.value == "EQUIVALENT"

    def test_metric_result_fields(self) -> None:
        m = MetricResult(score=0.8, reasoning="Good", metric_name="test")
        assert m.score == 0.8
        assert m.metric_name == "test"

    def test_strategy_result_defaults(self) -> None:
        r = StrategyResult(chunking_strategy="naive", retrieval_strategy="semantic")
        assert r.avg_faithfulness == 0.0
        assert r.num_questions == 0
        assert r.individual_results == []


# ── Test: Runner module entry point ──────────────────────────────────────────


def test_runner_callable_as_module() -> None:
    """python -m src.evaluation.runner --help must exit 0.

    Verifies Issue #23 fix: the runner must be invocable as a module with
    a proper __main__ block. Before the fix this would error with
    'No module named src.evaluation.runner.__main__; ...' or similar.
    """
    result = subprocess.run(
        [sys.executable, "-m", "src.evaluation.runner", "--help"],
        capture_output=True,
        text=True,
        cwd=str(__file__.replace("\\", "/").rsplit("/tests/", 1)[0]),  # project root
    )
    assert result.returncode == 0, (
        f"Runner --help failed (exit {result.returncode}).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # --help output should describe the runner's purpose
    assert "meeting" in result.stdout.lower() or "eval" in result.stdout.lower(), (
        f"--help output doesn't describe the runner: {result.stdout}"
    )
