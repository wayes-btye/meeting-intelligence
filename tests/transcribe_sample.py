"""Quick script to transcribe a sample audio file via AssemblyAI and save output.

Usage:
    python tests/transcribe_sample.py

Outputs to tests/data/:
    gitlab-engineering-meeting.txt   — plain text transcript
    gitlab-engineering-meeting.json  — full AssemblyAI response (utterances + metadata)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import assemblyai as aai  # type: ignore[import-untyped]  # noqa: E402

from src.config import settings  # noqa: E402

AUDIO_FILE = ROOT / "tests" / "data" / "gitlab-engineering-meeting.mp3"
OUT_TXT = ROOT / "tests" / "data" / "gitlab-engineering-meeting.txt"
OUT_JSON = ROOT / "tests" / "data" / "gitlab-engineering-meeting.json"


def main() -> None:
    if not AUDIO_FILE.exists():
        print(f"Audio file not found: {AUDIO_FILE}")
        sys.exit(1)

    print(f"Transcribing {AUDIO_FILE.name} ({AUDIO_FILE.stat().st_size / 1e6:.1f} MB)...")

    aai.settings.api_key = settings.assemblyai_api_key
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro"],
        speaker_labels=True,
    )
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(str(AUDIO_FILE), config=config)

    if transcript.status == aai.TranscriptStatus.error:
        print(f"Transcription error: {transcript.error}")
        sys.exit(1)

    # Plain text
    OUT_TXT.write_text(transcript.text or "", encoding="utf-8")
    print(f"Saved plain text -> {OUT_TXT}")

    # Full JSON with utterances (speaker-labelled turns)
    utterances = []
    if transcript.utterances:
        for u in transcript.utterances:
            utterances.append({
                "speaker": u.speaker,
                "text": u.text,
                "start_ms": u.start,
                "end_ms": u.end,
            })

    out = {
        "id": transcript.id,
        "status": str(transcript.status),
        "audio_duration_s": transcript.audio_duration,
        "num_speakers": len({u["speaker"] for u in utterances}) if utterances else None,
        "utterances": utterances,
        "text": transcript.text,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved JSON with utterances -> {OUT_JSON}")
    print(f"\nSpeakers detected: {out['num_speakers']}")
    print(f"Utterances: {len(utterances)}")
    if utterances:
        print("\nFirst 3 utterances:")
        for u in utterances[:3]:
            start = u["start_ms"] / 1000
            print(f"  [{start:.1f}s] Speaker {u['speaker']}: {u['text'][:80]}...")


if __name__ == "__main__":
    main()
