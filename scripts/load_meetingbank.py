"""Load MeetingBank meetings into the system via the ingestion pipeline."""

import argparse
import json
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.chunking import naive_chunk, speaker_turn_chunk
from src.ingestion.embeddings import embed_chunks
from src.ingestion.models import TranscriptSegment
from src.ingestion.storage import get_supabase_client, store_chunks, store_meeting


def parse_meetingbank_meeting(
    data: dict,
) -> tuple[str, str, list[TranscriptSegment]]:
    """Parse a MeetingBank meeting into our standard format.

    MeetingBank structure varies -- common keys include:
    - 'transcript' or 'source' -- the raw transcript text or segments
    - 'summary' -- reference summary
    - 'id' -- meeting identifier

    Returns: (title, raw_transcript, segments)
    """
    meeting_id = data.get("id", "Unknown Meeting")
    title = data.get("title", data.get("uid", str(meeting_id)))

    segments: list[TranscriptSegment] = []
    raw_text_parts: list[str] = []

    # Try different MeetingBank structures
    # Structure 1: transcript as list of segments
    if "transcript" in data and isinstance(data["transcript"], list):
        for seg in data["transcript"]:
            if isinstance(seg, dict):
                text = seg.get("text", seg.get("sentence", ""))
                speaker = seg.get("speaker", None)
                start = seg.get("start_time", seg.get("start", None))
                end = seg.get("end_time", seg.get("end", None))
                if isinstance(start, (int, float)) and start > 1000:
                    start = start / 1000  # ms to seconds
                if isinstance(end, (int, float)) and end > 1000:
                    end = end / 1000
                segments.append(
                    TranscriptSegment(
                        speaker=speaker,
                        text=text.strip(),
                        start_time=float(start) if start is not None else None,
                        end_time=float(end) if end is not None else None,
                    )
                )
                raw_text_parts.append(text.strip())
            elif isinstance(seg, str):
                segments.append(TranscriptSegment(speaker=None, text=seg.strip()))
                raw_text_parts.append(seg.strip())

    # Structure 2: transcript as plain string
    elif "transcript" in data and isinstance(data["transcript"], str):
        text = data["transcript"]
        # MeetingBank transcripts are often a single long string with no
        # newlines.  Split on sentence boundaries so downstream chunking
        # has reasonable segments to work with.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            segments.append(TranscriptSegment(speaker=None, text=sentence))
            raw_text_parts.append(sentence)

    # Structure 3: source field
    elif "source" in data:
        source = data["source"]
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    text = item.get("text", item.get("sentence", str(item)))
                    segments.append(
                        TranscriptSegment(speaker=item.get("speaker"), text=text.strip())
                    )
                    raw_text_parts.append(text.strip())
                else:
                    segments.append(TranscriptSegment(speaker=None, text=str(item).strip()))
                    raw_text_parts.append(str(item).strip())
        elif isinstance(source, str):
            for line in source.split("\n"):
                if line.strip():
                    segments.append(TranscriptSegment(speaker=None, text=line.strip()))
                    raw_text_parts.append(line.strip())

    raw_transcript = "\n".join(raw_text_parts)

    return title, raw_transcript, segments


def load_meetingbank(
    data_dir: str = "data/meetingbank",
    chunking_strategy: str = "speaker_turn",
    max_meetings: int | None = None,
) -> None:
    """Load all MeetingBank meetings from data directory into Supabase."""
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"Data directory {data_dir} not found. Run download_meetingbank.py first.")
        return

    files = sorted(data_path.glob("*.json"))
    if max_meetings:
        files = files[:max_meetings]

    print(f"Loading {len(files)} meetings with {chunking_strategy} chunking...")

    client = get_supabase_client()
    loaded = 0
    errors = 0

    for i, filepath in enumerate(files):
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            title, raw_transcript, segments = parse_meetingbank_meeting(data)

            if not segments:
                print(f"  [{i + 1}] SKIP {filepath.name} -- no segments found")
                continue

            # Chunk
            if chunking_strategy == "naive":
                chunks = naive_chunk(segments)
            else:
                chunks = speaker_turn_chunk(segments)

            if not chunks:
                print(f"  [{i + 1}] SKIP {filepath.name} -- no chunks produced")
                continue

            # Embed
            chunks_with_embeddings = embed_chunks(chunks)

            # Store
            num_speakers = len(set(s.speaker for s in segments if s.speaker))
            meeting_id = store_meeting(
                client,
                title=title,
                raw_transcript=raw_transcript,
                source_file=filepath.name,
                transcript_format="meetingbank",
                num_speakers=num_speakers if num_speakers > 0 else None,
            )
            store_chunks(client, meeting_id, chunks_with_embeddings)

            loaded += 1
            print(f"  [{i + 1}/{len(files)}] Loaded {title} -- {len(chunks)} chunks")

        except Exception as e:
            errors += 1
            print(f"  [{i + 1}] ERROR {filepath.name}: {e}")

    print(f"\nDone! Loaded {loaded} meetings, {errors} errors.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/meetingbank")
    parser.add_argument("--strategy", default="speaker_turn")
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()
    load_meetingbank(args.dir, args.strategy, args.max)
