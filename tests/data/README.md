# tests/data/ — Real Audio & Transcription Files

This directory holds **real meeting recordings and their transcripts**, used for
manual end-to-end testing and demo purposes. These are NOT loaded by the
automated pytest suite (which uses `tests/fixtures/` instead).

## Files

| File | In git? | Duration | Speakers | Source |
|------|---------|----------|----------|--------|
| `gitlab-sec-growth-datascience-2022-09-14.mp3` | **Yes** (28 MB) | 29 min | 9 | [YouTube](https://www.youtube.com/watch?v=rOqgRiNMVqg) |
| `gitlab-sec-growth-datascience-2022-09-14.txt` | Yes | — | — | AssemblyAI transcript |
| `gitlab-sec-growth-datascience-2022-09-14.json` | Yes | — | 9 spk, 61 utt | AssemblyAI utterances |
| `gitlab-engineering-meeting.mp3` | No (gitignored) | 24 min | 7 | [YouTube](https://www.youtube.com/watch?v=qGFoZ8yodc4) |
| `gitlab-engineering-meeting.txt` | Yes | — | — | AssemblyAI transcript |
| `gitlab-engineering-meeting.json` | Yes | — | 7 spk, 88 utt | AssemblyAI utterances |
| `gitlab-product-marketing-weekly-2021-06-28.mp3` | No (gitignored) | 43 min | 7 | [YouTube](https://www.youtube.com/watch?v=lBVtvOpU80Q) |
| `gitlab-product-marketing-weekly-2021-06-28.txt` | Yes | — | — | AssemblyAI transcript |
| `gitlab-product-marketing-weekly-2021-06-28.json` | Yes | — | 7 spk, 180 utt | AssemblyAI utterances |
| `gitlab-product-team-meeting-2019-07-09.mp3` | No (gitignored) | 43 min | 9 | [YouTube](https://www.youtube.com/watch?v=k8K6wQLxooU) |
| `gitlab-product-team-meeting-2019-07-09.txt` | Yes | — | — | AssemblyAI transcript |
| `gitlab-product-team-meeting-2019-07-09.json` | Yes | — | 9 spk, 90 utt | AssemblyAI utterances |
| `gitlab-code-review-weekly-2022-09-30.mp3` | No (gitignored) | 34 min | 3 | [YouTube](https://www.youtube.com/watch?v=1lzK6EYO800) |
| `gitlab-code-review-weekly-2022-09-30.txt` | Yes | — | — | AssemblyAI transcript |
| `gitlab-code-review-weekly-2022-09-30.json` | Yes | — | 3 spk, 76 utt | AssemblyAI utterances |

> All MP3s are from the [GitLab Unfiltered](https://www.youtube.com/@GitLabUnfiltered) YouTube channel.

## Getting the MP3 files

**One MP3 is included in the repo** (`gitlab-sec-growth-datascience-2022-09-14.mp3`) and ready to use immediately for demo and audio ingestion testing.

**All 5 MP3s are available as a zip download:**
[Download all MP3s from Google Drive](https://drive.google.com/file/d/1WaJ8GDtoX8HgHw6V1U-zkG0aoTrCP5MM/view?usp=sharing)

After downloading, place the MP3 files in this directory (`tests/data/`). The transcripts are already committed so you only need the audio files if you want to re-run transcription or test the audio upload path.

## Testing both paths

Each meeting has both an MP3 and a committed transcript, so you can test either path:

- **Audio upload path** — drag the `.mp3` into the Upload UI; AssemblyAI transcribes it live (requires `ASSEMBLYAI_API_KEY`)
- **Transcript path** — drag the `.txt` or `.json` into the Upload UI; no API key needed, processes instantly

## How to re-transcribe

```bash
# Transcribe all MP3s that don't yet have a JSON transcript
python tests/transcribe_batch.py

# Transcribe a single file (edit the path inside first)
python tests/transcribe_sample.py
```

Both scripts call AssemblyAI with `speaker_labels=True`. **Do not run in CI** — they consume AssemblyAI credits and take several minutes per file.

## Why separate from tests/fixtures/?

| Directory | Used by | Contains |
|-----------|---------|----------|
| `tests/fixtures/` | pytest (automated) | Small synthetic/sample files safe to commit |
| `tests/data/` | Manual/demo only | Real recordings + transcripts |
| `data/meetingbank/` | pytest via fixtures | MeetingBank dataset subset (30 JSON files) |
