"""Transcribe all MP3 files in tests/data/ that don't yet have a JSON transcript.

NOT a pytest test — run manually only. Consumes AssemblyAI credits.
Do not add to CI/CD.

Usage:
    python tests/transcribe_batch.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "tests" / "data"

sys.path.insert(0, str(ROOT))

import assemblyai as aai  # type: ignore[import-untyped]  # noqa: E402

from src.config import settings  # noqa: E402


def transcribe(mp3_path: Path) -> None:
    out_txt = mp3_path.with_suffix(".txt")
    out_json = mp3_path.with_suffix(".json")

    if out_json.exists():
        print(f"SKIP {mp3_path.name} — transcript already exists")
        return

    size_mb = mp3_path.stat().st_size / 1e6
    print(f"\nTranscribing {mp3_path.name} ({size_mb:.1f} MB)...")

    aai.settings.api_key = settings.assemblyai_api_key
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro"],
        speaker_labels=True,
    )
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(str(mp3_path), config=config)

    if transcript.status == aai.TranscriptStatus.error:
        print(f"  ERROR: {transcript.error}")
        return

    out_txt.write_text(transcript.text or "", encoding="utf-8")

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
    out_json.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  Done — {out['num_speakers']} speakers, {len(utterances)} utterances")
    print(f"  Saved: {out_txt.name}, {out_json.name}")


def main() -> None:
    mp3_files = sorted(DATA_DIR.glob("*.mp3"))
    if not mp3_files:
        print("No MP3 files found in tests/data/")
        sys.exit(1)

    print(f"Found {len(mp3_files)} MP3 file(s):")
    for f in mp3_files:
        print(f"  {f.name}")

    for mp3 in mp3_files:
        transcribe(mp3)

    print("\nAll done.")


if __name__ == "__main__":
    main()
