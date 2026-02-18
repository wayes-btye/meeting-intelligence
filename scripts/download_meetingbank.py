"""Download MeetingBank dataset subset from HuggingFace."""

import json
import os
from pathlib import Path


def download_meetingbank(output_dir: str = "data/meetingbank", num_meetings: int = 30) -> Path:
    """Download MeetingBank meetings using the HuggingFace datasets library."""
    try:
        from datasets import load_dataset  # type: ignore[import-untyped]
    except ImportError:
        print("Installing datasets library...")
        os.system("pip install datasets")
        from datasets import load_dataset  # type: ignore[import-untyped]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("Loading MeetingBank dataset from HuggingFace...")
    dataset = load_dataset("huuuyeah/MeetingBank", split="train")

    # Take a diverse subset
    selected = list(dataset.select(range(min(num_meetings, len(dataset)))))

    print(f"Saving {len(selected)} meetings to {output_dir}/")

    for i, meeting in enumerate(selected):
        meeting_id = meeting.get("id", f"meeting_{i}")

        # Save the raw meeting data
        filepath = output_path / f"{meeting_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(meeting, f, indent=2, default=str)

        print(f"  [{i + 1}/{len(selected)}] Saved {meeting_id}")

    print(f"\nDone! {len(selected)} meetings saved to {output_dir}/")
    return output_path


if __name__ == "__main__":
    download_meetingbank()
