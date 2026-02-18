"""Generate evaluation test sets from meeting transcripts using Claude."""

from __future__ import annotations

import json
import uuid

from anthropic import Anthropic

from src.config import settings
from src.evaluation.models import Difficulty, QuestionCategory, TestQuestion

# How many questions to request per category per meeting
QUESTIONS_PER_CATEGORY: dict[QuestionCategory, int] = {
    QuestionCategory.FACTUAL: 8,
    QuestionCategory.INFERENCE: 5,
    QuestionCategory.ACTION_ITEMS: 4,
    QuestionCategory.DECISIONS: 4,
}

# Difficulty distribution ratios (easy, medium, hard)
DIFFICULTY_RATIOS: dict[Difficulty, float] = {
    Difficulty.EASY: 0.4,
    Difficulty.MEDIUM: 0.4,
    Difficulty.HARD: 0.2,
}

GENERATION_PROMPT = """\
You are generating evaluation questions for a meeting intelligence RAG system.

Given the meeting transcript below, generate exactly {num_questions} questions \
of category "{category}" with difficulty "{difficulty}".

Category definitions:
- factual: Questions with explicit answers stated directly in the transcript.
- inference: Questions requiring reasoning across multiple parts of the transcript.
- action_items: Questions about tasks assigned, deadlines, or follow-ups mentioned.
- decisions: Questions about decisions made or conclusions reached in the meeting.

Difficulty definitions:
- easy: Answer is in a single, obvious location in the transcript.
- medium: Answer requires combining 2-3 pieces of information.
- hard: Answer requires deep understanding, synthesis, or reasoning about implicit information.

Return a JSON array of objects with exactly these fields:
- "question": the question text
- "expected_answer": a concise, correct answer based on the transcript

TRANSCRIPT:
{transcript}

Return ONLY the JSON array, no other text.
"""

MULTI_MEETING_PROMPT = """\
You are generating evaluation questions that span multiple meetings.

Given excerpts from {num_meetings} different meetings below, generate exactly \
{num_questions} questions that require information from at least 2 meetings to answer.

These should be "hard" difficulty questions about cross-meeting themes, contradictions, \
evolving decisions, or recurring topics.

Return a JSON array of objects with exactly these fields:
- "question": the question text
- "expected_answer": a concise, correct answer referencing relevant meetings

MEETING EXCERPTS:
{transcripts}

Return ONLY the JSON array, no other text.
"""


def _call_claude(prompt: str) -> str:
    """Make a Claude API call and return the text response."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _parse_questions_json(raw: str) -> list[dict]:
    """Parse Claude's response as a JSON array, handling markdown fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (the fences)
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def generate_single_meeting_questions(
    transcript: str,
    meeting_id: str,
    max_transcript_chars: int = 30000,
) -> list[TestQuestion]:
    """Generate test questions from a single meeting transcript.

    Args:
        transcript: The full meeting transcript text.
        meeting_id: ID of the source meeting.
        max_transcript_chars: Truncate transcript to this length to stay within
            token limits.

    Returns:
        List of TestQuestion objects.
    """
    truncated = transcript[:max_transcript_chars]
    questions: list[TestQuestion] = []

    for category, count in QUESTIONS_PER_CATEGORY.items():
        for difficulty, ratio in DIFFICULTY_RATIOS.items():
            num = max(1, int(count * ratio))
            prompt = GENERATION_PROMPT.format(
                num_questions=num,
                category=category.value,
                difficulty=difficulty.value,
                transcript=truncated,
            )
            try:
                raw = _call_claude(prompt)
                parsed = _parse_questions_json(raw)
                for item in parsed:
                    questions.append(
                        TestQuestion(
                            question=item["question"],
                            expected_answer=item["expected_answer"],
                            category=category,
                            difficulty=difficulty,
                            source_meeting_id=meeting_id,
                            question_id=str(uuid.uuid4()),
                        )
                    )
            except (json.JSONDecodeError, KeyError, IndexError):
                # Skip malformed responses — best-effort generation
                continue

    return questions


def generate_multi_meeting_questions(
    transcripts: dict[str, str],
    num_questions: int = 10,
    excerpt_chars: int = 5000,
) -> list[TestQuestion]:
    """Generate questions that span multiple meetings.

    Args:
        transcripts: Mapping of meeting_id -> transcript text.
        num_questions: How many multi-meeting questions to generate.
        excerpt_chars: Characters per meeting excerpt.

    Returns:
        List of TestQuestion objects with category MULTI_MEETING.
    """
    excerpts = "\n\n---\n\n".join(
        f"[Meeting {mid}]:\n{text[:excerpt_chars]}" for mid, text in transcripts.items()
    )

    prompt = MULTI_MEETING_PROMPT.format(
        num_meetings=len(transcripts),
        num_questions=num_questions,
        transcripts=excerpts,
    )

    questions: list[TestQuestion] = []
    try:
        raw = _call_claude(prompt)
        parsed = _parse_questions_json(raw)
        for item in parsed:
            questions.append(
                TestQuestion(
                    question=item["question"],
                    expected_answer=item["expected_answer"],
                    category=QuestionCategory.MULTI_MEETING,
                    difficulty=Difficulty.HARD,
                    source_meeting_id="multi",
                    question_id=str(uuid.uuid4()),
                )
            )
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return questions


def generate_test_set(
    transcripts: dict[str, str],
    target_min: int = 150,
    target_max: int = 250,
) -> list[TestQuestion]:
    """Generate a complete test set from multiple meeting transcripts.

    Args:
        transcripts: Mapping of meeting_id -> transcript text.
        target_min: Minimum number of questions to aim for.
        target_max: Maximum number of questions.

    Returns:
        List of TestQuestion objects.
    """
    all_questions: list[TestQuestion] = []

    # Generate per-meeting questions
    for meeting_id, transcript in transcripts.items():
        qs = generate_single_meeting_questions(transcript, meeting_id)
        all_questions.extend(qs)
        if len(all_questions) >= target_max:
            break

    # Generate multi-meeting questions if we have multiple meetings
    if len(transcripts) >= 2:
        multi_qs = generate_multi_meeting_questions(transcripts)
        all_questions.extend(multi_qs)

    # Trim to target_max if needed
    return all_questions[:target_max]


def save_test_set(questions: list[TestQuestion], path: str) -> None:
    """Save test set to a JSON file."""
    data = [
        {
            "question_id": q.question_id,
            "question": q.question,
            "expected_answer": q.expected_answer,
            "category": q.category.value,
            "difficulty": q.difficulty.value,
            "source_meeting_id": q.source_meeting_id,
        }
        for q in questions
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_test_set(path: str) -> list[TestQuestion]:
    """Load a test set from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        TestQuestion(
            question_id=item.get("question_id", str(uuid.uuid4())),
            question=item["question"],
            expected_answer=item["expected_answer"],
            category=QuestionCategory(item["category"]),
            difficulty=Difficulty(item["difficulty"]),
            source_meeting_id=item["source_meeting_id"],
        )
        for item in data
    ]
