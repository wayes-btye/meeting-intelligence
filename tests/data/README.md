# tests/data/ — Real Audio & Transcription Files

This directory holds **real meeting recordings and their transcripts**, used for
manual end-to-end testing and pipeline development. These are NOT loaded by the
automated pytest suite (which uses `tests/fixtures/` instead).

## Contents

| File | Source | Duration | Notes |
|------|--------|----------|-------|
| `gitlab-engineering-meeting.mp3` | [YouTube](https://www.youtube.com/watch?v=qGFoZ8yodc4) | 24 min | GitLab Engineering Key Review, Feb 2021. First test file; used to diagnose issue #63 (speaker diarization). |
| `gitlab-engineering-meeting.txt` | AssemblyAI output | — | Plain text transcript of the above. Committed. |
| `gitlab-engineering-meeting.json` | AssemblyAI output | — | Full utterances + speaker labels (88 utterances, 7 speakers). Committed. |
| `gitlab-product-marketing-weekly-2021-06-28.mp3` | [YouTube](https://www.youtube.com/watch?v=lBVtvOpU80Q) | 43 min | GitLab Product Marketing weekly meeting, Jun 2021. |
| `gitlab-unfiltered-2021-06-28-k8K6wQLxooU.mp3` | [YouTube](https://www.youtube.com/watch?v=k8K6wQLxooU) | TBD | GitLab Unfiltered meeting. |
| `gitlab-unfiltered-2021-06-28-1lzK6EYO800.mp3` | [YouTube](https://www.youtube.com/watch?v=1lzK6EYO800) | TBD | GitLab Unfiltered meeting. |
| `gitlab-unfiltered-2021-06-28-rOqgRiNMVqg.mp3` | [YouTube](https://www.youtube.com/watch?v=rOqgRiNMVqg) | TBD | GitLab Unfiltered meeting. |

> MP3 files are gitignored (large binaries). TXT and JSON transcripts are committed where available.

## How files are obtained

Audio is extracted from YouTube using the Apify actor
`marielise.dev/youtube-video-downloader` with `format: "mp3"`. All source
videos are from the **GitLab Unfiltered** YouTube channel — publicly posted
recordings of real team meetings.

## How to transcribe

```bash
# Transcribe a single file and save TXT + JSON output
python tests/transcribe_sample.py
```

The script calls AssemblyAI with `speaker_labels=True`. **Do not run this in
CI** — it consumes AssemblyAI credits and takes several minutes per file.
Update `transcribe_sample.py` to point at whichever file you want to process.

## Why separate from tests/fixtures/?

| Directory | Used by | Contains |
|-----------|---------|----------|
| `tests/fixtures/` | pytest (automated) | Small synthetic/sample files safe to commit |
| `tests/data/` | Manual scripts only | Real recordings (large, gitignored MP3s) + their committed transcripts |
| `data/meetingbank/` | pytest via fixtures | MeetingBank dataset subset (30 JSON files) |
