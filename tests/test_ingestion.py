"""Tests for the ingestion pipeline — parsers and chunking strategies."""

from __future__ import annotations

import json

import pytest

from src.ingestion.chunking import naive_chunk, speaker_turn_chunk
from src.ingestion.models import TranscriptSegment
from src.ingestion.parsers import parse_json, parse_plain_text, parse_transcript, parse_vtt


class TestVTTParser:
    def test_basic_vtt(self) -> None:
        vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
Speaker 1: Hello everyone, welcome to the meeting.

00:00:05.500 --> 00:00:10.000
Speaker 2: Thanks for having us. Let's get started.

00:00:10.500 --> 00:00:15.000
Speaker 1: First item on the agenda is the budget review.
"""
        segments = parse_vtt(vtt)
        assert len(segments) == 3
        assert segments[0].speaker == "Speaker 1"
        assert segments[0].start_time == 1.0
        assert "welcome" in segments[0].text

    def test_vtt_no_speakers(self) -> None:
        vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
Hello everyone.

00:00:05.500 --> 00:00:10.000
Let's get started.
"""
        segments = parse_vtt(vtt)
        assert len(segments) == 2
        assert segments[0].speaker is None

    def test_vtt_end_times(self) -> None:
        vtt = """WEBVTT

00:00:01.000 --> 00:00:05.500
Speaker A: Some text here.
"""
        segments = parse_vtt(vtt)
        assert segments[0].end_time == 5.5

    def test_vtt_multiline_cue(self) -> None:
        vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
This is line one.
This is line two.
"""
        segments = parse_vtt(vtt)
        assert len(segments) == 1
        assert "line one" in segments[0].text
        assert "line two" in segments[0].text


class TestPlainTextParser:
    def test_with_speakers(self) -> None:
        text = """Speaker 1: Hello everyone.
Speaker 2: Hi there.
Speaker 1: Let's begin."""
        segments = parse_plain_text(text)
        assert len(segments) == 3
        assert segments[1].speaker == "Speaker 2"

    def test_without_speakers(self) -> None:
        text = """This is a meeting transcript.
Nothing fancy here."""
        segments = parse_plain_text(text)
        assert len(segments) == 2
        assert all(s.speaker is None for s in segments)

    def test_empty_lines_ignored(self) -> None:
        text = "Line one.\n\nLine two.\n\n"
        segments = parse_plain_text(text)
        assert len(segments) == 2


class TestJSONParser:
    def test_assemblyai_format(self) -> None:
        data = json.dumps(
            {
                "utterances": [
                    {"speaker": "A", "text": "Hello everyone.", "start": 1000, "end": 3000},
                    {"speaker": "B", "text": "Hi there.", "start": 3500, "end": 5000},
                ]
            }
        )
        segments = parse_json(data)
        assert len(segments) == 2
        assert segments[0].speaker == "A"
        assert segments[0].start_time == 1.0  # converted from ms
        assert segments[0].end_time == 3.0

    def test_meetingbank_format(self) -> None:
        data = json.dumps(
            {
                "segments": [
                    {"speaker": "X", "text": "Hello.", "start_time": 1.5, "end_time": 3.2},
                    {"speaker": "Y", "text": "World.", "start_time": 3.5, "end_time": 5.0},
                ]
            }
        )
        segments = parse_json(data)
        assert len(segments) == 2
        assert segments[0].start_time == 1.5

    def test_unknown_json_raises(self) -> None:
        data = json.dumps({"something_else": []})
        with pytest.raises(ValueError, match="Unrecognized JSON"):
            parse_json(data)


class TestNaiveChunking:
    def test_produces_chunks(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="Hello " * 100, start_time=0.0, end_time=10.0),
            TranscriptSegment(speaker="B", text="World " * 100, start_time=10.0, end_time=20.0),
        ]
        chunks = naive_chunk(segments, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        assert all(c.strategy == "naive" for c in chunks)

    def test_preserves_times(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="Short text.", start_time=5.0, end_time=10.0),
        ]
        chunks = naive_chunk(segments)
        assert chunks[0].start_time == 5.0
        assert chunks[0].end_time == 10.0

    def test_chunk_indices_sequential(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="word " * 300, start_time=0.0, end_time=60.0),
        ]
        chunks = naive_chunk(segments, chunk_size=100, overlap=10)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_empty_segments(self) -> None:
        assert naive_chunk([]) == []


class TestSpeakerTurnChunking:
    def test_groups_by_speaker(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="Hello.", start_time=0.0, end_time=1.0),
            TranscriptSegment(speaker="A", text="How are you?", start_time=1.0, end_time=2.0),
            TranscriptSegment(speaker="B", text="I'm good.", start_time=2.0, end_time=3.0),
        ]
        chunks = speaker_turn_chunk(segments)
        assert len(chunks) == 2  # A's two segments merged, B separate
        assert chunks[0].speaker == "A"
        assert chunks[1].speaker == "B"
        assert all(c.strategy == "speaker_turn" for c in chunks)

    def test_long_turn_split(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="word " * 600, start_time=0.0, end_time=60.0),
        ]
        chunks = speaker_turn_chunk(segments, max_chunk_tokens=200)
        assert len(chunks) > 1
        assert all(c.speaker == "A" for c in chunks)

    def test_preserves_times(self) -> None:
        segments = [
            TranscriptSegment(speaker="A", text="Hello.", start_time=5.0, end_time=8.0),
            TranscriptSegment(speaker="A", text="World.", start_time=8.0, end_time=10.0),
        ]
        chunks = speaker_turn_chunk(segments)
        assert chunks[0].start_time == 5.0
        assert chunks[0].end_time == 10.0

    def test_empty_segments(self) -> None:
        assert speaker_turn_chunk([]) == []


class TestParseDispatcher:
    def test_vtt_dispatch(self) -> None:
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nHello."
        segments = parse_transcript(vtt, "vtt")
        assert len(segments) >= 1

    def test_text_dispatch(self) -> None:
        segments = parse_transcript("Hello world.", "text")
        assert len(segments) == 1

    def test_json_dispatch(self) -> None:
        data = json.dumps({"utterances": [{"speaker": "A", "text": "Hi", "start": 0, "end": 1}]})
        segments = parse_transcript(data, "json")
        assert len(segments) == 1

    def test_unknown_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown transcript format"):
            parse_transcript("data", "unknown_format")
