"""Transcript parsers for VTT, plain text, and JSON formats."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from src.ingestion.models import TranscriptSegment


def _parse_vtt_timestamp(ts: str) -> float:
    """Convert a VTT timestamp (HH:MM:SS.mmm) to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return 0.0
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_vtt(content: str) -> list[TranscriptSegment]:
    """Parse a WebVTT file into transcript segments.

    Handles timestamps like ``00:01:23.456 --> 00:01:30.789`` and speaker labels
    in two formats:

    - Standard colon-style: ``Speaker 1: Hello``
    - Microsoft Teams inline voice tags: ``<v SpeakerName>Hello</v>``
      (Issue #34 — Teams VTT format support)

    Teams ``<v SpeakerName>`` tags take precedence over colon-style labels when
    both are present in the same cue (unlikely in practice, but Teams format wins).
    """
    segments: list[TranscriptSegment] = []

    # Pattern: timestamp line followed by one or more text lines
    timestamp_re = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
    )
    speaker_re = re.compile(r"^(.+?):\s+(.+)$")
    # Teams <v SpeakerName> tag — matches opening tag, captures speaker name.
    # The closing </v> tag is optional per the WebVTT spec.
    teams_voice_re = re.compile(r"^<v ([^>]+)>(.*?)(?:</v>)?$", re.DOTALL)

    lines = content.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = timestamp_re.search(line)
        if match:
            start = _parse_vtt_timestamp(match.group(1).replace(",", "."))
            end = _parse_vtt_timestamp(match.group(2).replace(",", "."))

            # Collect text lines until blank line or next timestamp / end
            text_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() and not timestamp_re.search(lines[i]):
                text_lines.append(lines[i].strip())
                i += 1

            full_text = " ".join(text_lines)
            speaker: str | None = None

            # Check for Microsoft Teams inline voice tag first (<v SpeakerName>).
            # Teams format takes precedence over colon-style labels.
            teams_match = teams_voice_re.match(full_text)
            if teams_match:
                speaker = teams_match.group(1).strip()
                full_text = teams_match.group(2).strip()
            else:
                # Fall back to standard colon-style speaker label
                speaker_match = speaker_re.match(full_text)
                if speaker_match:
                    speaker = speaker_match.group(1)
                    full_text = speaker_match.group(2)

            if full_text:
                segments.append(
                    TranscriptSegment(
                        speaker=speaker,
                        text=full_text,
                        start_time=start,
                        end_time=end,
                    )
                )
        else:
            i += 1

    return segments


def parse_plain_text(content: str) -> list[TranscriptSegment]:
    """Parse a plain-text transcript.

    If lines start with ``Speaker X:`` the speaker is extracted, otherwise
    speaker is ``None``.
    """
    segments: list[TranscriptSegment] = []
    speaker_re = re.compile(r"^(.+?):\s+(.+)$")

    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        match = speaker_re.match(line)
        if match:
            segments.append(TranscriptSegment(speaker=match.group(1), text=match.group(2)))
        else:
            segments.append(TranscriptSegment(speaker=None, text=line))

    return segments


def parse_json(content: str) -> list[TranscriptSegment]:
    """Parse a JSON transcript (AssemblyAI, MeetingBank, or internal segments format).

    Supported formats:

    AssemblyAI::

        {"utterances": [{"speaker": "A", "text": "...", "start": ms, "end": ms}]}

    MeetingBank canonical (transcription key, speaker_id field, times in seconds)::

        {
          "meeting_id": "...",
          "transcription": [
            {"speaker_id": "SPEAKER_0", "text": "...", "start_time": s, "end_time": s}
          ],
          "summary": "..."
        }

    Internal segments format (used in test fixtures and pipeline output)::

        {"segments": [{"speaker": "...", "text": "...", "start_time": s, "end_time": s}]}
    """
    data = json.loads(content)
    segments: list[TranscriptSegment] = []

    if "utterances" in data:
        # AssemblyAI format — times in milliseconds
        for utt in data["utterances"]:
            segments.append(
                TranscriptSegment(
                    speaker=utt.get("speaker"),
                    text=utt["text"],
                    start_time=utt.get("start", 0) / 1000.0,
                    end_time=utt.get("end", 0) / 1000.0,
                )
            )
    elif "transcription" in data:
        # MeetingBank canonical format — speaker_id field, times in seconds
        for item in data["transcription"]:
            segments.append(
                TranscriptSegment(
                    speaker=item.get("speaker_id"),
                    text=item["text"],
                    start_time=item.get("start_time"),
                    end_time=item.get("end_time"),
                )
            )
    elif "segments" in data:
        # Internal segments format — times in seconds
        for seg in data["segments"]:
            segments.append(
                TranscriptSegment(
                    speaker=seg.get("speaker"),
                    text=seg["text"],
                    start_time=seg.get("start_time"),
                    end_time=seg.get("end_time"),
                )
            )
    else:
        msg = f"Unrecognized JSON transcript format. Keys: {list(data.keys())}"
        raise ValueError(msg)

    return segments


def parse_transcript(content: str, format: str) -> list[TranscriptSegment]:
    """Dispatch to the correct parser based on *format*.

    Args:
        content: Raw transcript text.
        format: One of ``"vtt"``, ``"text"`` / ``"plain_text"`` / ``"txt"``,
                or ``"json"``.

    Returns:
        Parsed transcript segments.

    Raises:
        ValueError: If *format* is not recognized.
    """
    # Typed dict avoids operator/no-any-return errors when calling parser(). (#30)
    dispatch: dict[str, Callable[[str], list[TranscriptSegment]]] = {
        "vtt": parse_vtt,
        "text": parse_plain_text,
        "plain_text": parse_plain_text,
        "txt": parse_plain_text,
        "json": parse_json,
    }

    parser = dispatch.get(format)
    if parser is None:
        msg = f"Unknown transcript format: {format!r}. Supported: {list(dispatch.keys())}"
        raise ValueError(msg)

    return parser(content)
