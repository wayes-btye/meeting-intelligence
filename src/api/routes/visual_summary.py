"""Visual summary endpoint — calls Gemini for speaker/topic/timeline breakdown."""
from __future__ import annotations

import json
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.ingestion.storage import get_supabase_client

router = APIRouter()


class VisualSummaryResponse(BaseModel):
    meeting_id: str
    speaker_breakdown: list[dict[str, Any]]
    topic_timeline: list[dict[str, Any]]
    key_moments: list[dict[str, Any]]
    word_count: int
    duration_seconds: int | None


@router.post("/api/meetings/{meeting_id}/visual-summary", response_model=VisualSummaryResponse)
async def visual_summary(meeting_id: str) -> VisualSummaryResponse:
    """Generate a visual summary of a meeting using Gemini."""
    if not settings.google_api_key:
        raise HTTPException(
            status_code=501,
            detail="Visual summary requires GOOGLE_API_KEY — not configured.",
        )

    client = get_supabase_client()
    result = client.table("meetings").select("*").eq("id", meeting_id).execute()
    rows = cast(list[dict[str, Any]], result.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = rows[0].get("raw_transcript", "")
    if not transcript:
        raise HTTPException(status_code=400, detail="Meeting has no transcript")

    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)  # type: ignore[attr-defined]
    model = genai.GenerativeModel("gemini-2.0-flash")  # type: ignore[attr-defined]

    prompt = f"""Analyse this meeting transcript and return a JSON object with exactly these fields:
- speaker_breakdown: list of {{speaker, utterance_count, percentage}} (percentage as float 0-100)
- topic_timeline: list of {{timestamp, topic}} (approximate timestamps as strings)
- key_moments: list of {{timestamp, description}} (max 5 most important moments)
- word_count: total word count as integer
- duration_seconds: estimated duration in seconds as integer, or null if unknown

Transcript:
{transcript}

Return only valid JSON, no markdown fences, no explanation."""

    response = model.generate_content(prompt)
    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned invalid JSON: {e}",
        ) from e

    return VisualSummaryResponse(
        meeting_id=meeting_id,
        speaker_breakdown=data.get("speaker_breakdown", []),
        topic_timeline=data.get("topic_timeline", []),
        key_moments=data.get("key_moments", []),
        word_count=int(data.get("word_count", 0)),
        duration_seconds=data.get("duration_seconds"),
    )
