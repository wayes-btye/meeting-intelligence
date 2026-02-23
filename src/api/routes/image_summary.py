"""Image summary endpoint: generate a visual infographic for a meeting via Gemini."""

from __future__ import annotations

import base64
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from src.api.models import ImageSummaryResponse
from src.config import settings
from src.ingestion.storage import get_supabase_client

router = APIRouter()

_PROMPT_TEMPLATE = """\
Create a visual summary infographic for this meeting.
Include: speaker names and their participation level, key decisions made,
main topics discussed in order, and any action items.
Use a clean, professional style with clear sections and labels.

Transcript:
{transcript}"""

# Primary model: Nano Banana Pro (Gemini 3 Pro Image)
# Fallback: gemini-2.0-flash-exp with image generation config
_PRIMARY_MODEL = "gemini-3-pro-image-preview"
_FALLBACK_MODEL = "gemini-2.0-flash-exp"


@router.post("/api/meetings/{meeting_id}/image-summary", response_model=ImageSummaryResponse)
async def generate_image_summary(meeting_id: str) -> ImageSummaryResponse:
    """Generate a visual infographic for a meeting using Gemini image generation.

    Returns base64-encoded PNG image data. Requires GOOGLE_API_KEY to be set;
    returns HTTP 501 if the key is absent (graceful degradation).
    """
    # Graceful degradation: 501 if no API key
    if not settings.google_api_key:
        raise HTTPException(
            status_code=501,
            detail="Image summary not available: GOOGLE_API_KEY is not configured.",
        )

    # Validate UUID format before hitting Supabase (malformed IDs cause a 500 from PostgREST)
    import uuid as _uuid
    try:
        _uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found") from None

    # Fetch meeting transcript from Supabase
    client = get_supabase_client()
    result = client.table("meetings").select("id, raw_transcript").eq("id", meeting_id).execute()
    rows = cast(list[dict[str, Any]], result.data)
    if not rows:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcript = rows[0].get("raw_transcript")
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Meeting has no transcript to summarise",
        )

    prompt = _PROMPT_TEMPLATE.format(transcript=str(transcript))

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.google_api_key)  # type: ignore[attr-defined]

        image_data, mime_type = _call_gemini(genai, prompt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini image generation failed: {exc}",
        ) from exc

    return ImageSummaryResponse(
        meeting_id=meeting_id,
        image_data=image_data,
        mime_type=mime_type,
    )


def _call_gemini(genai: Any, prompt: str) -> tuple[str, str]:
    """Call Gemini API and return (base64_image_data, mime_type).

    Tries the primary model (Nano Banana Pro / gemini-3-pro-image-preview) first.
    Falls back to gemini-2.0-flash-exp with explicit image generation config if the
    primary model ID is unavailable or raises an error.
    """
    # Attempt 1: primary model (Nano Banana Pro)
    try:
        model = genai.GenerativeModel(_PRIMARY_MODEL)
        response = model.generate_content([prompt])
        return _extract_image_from_response(response)
    except Exception:
        pass  # Fall through to fallback model

    # Attempt 2: fallback model with explicit image response modality
    generation_config: dict[str, Any] = {"response_modalities": ["IMAGE", "TEXT"]}
    model = genai.GenerativeModel(
        _FALLBACK_MODEL,
        generation_config=generation_config,
    )
    response = model.generate_content([prompt])
    return _extract_image_from_response(response)


def _extract_image_from_response(response: Any) -> tuple[str, str]:
    """Extract base64 image data and MIME type from a Gemini response.

    Raises ValueError if no image part is found in the response.
    """
    for part in response.parts:
        if part.inline_data is not None:
            raw: bytes = part.inline_data.data
            mime_type: str = part.inline_data.mime_type or "image/png"
            # inline_data.data may already be base64 str or raw bytes
            if isinstance(raw, (bytes, bytearray)):
                image_data = base64.b64encode(raw).decode("utf-8")
            else:
                image_data = str(raw)
            return image_data, mime_type

    raise ValueError("Gemini response contained no image data")
