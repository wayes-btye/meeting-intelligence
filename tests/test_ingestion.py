"""Tests for the ingestion pipeline — parsers and chunking strategies."""

from __future__ import annotations

import json
import pathlib

import pytest

from src.ingestion.chunking import naive_chunk, speaker_turn_chunk
from src.ingestion.models import TranscriptSegment
from src.ingestion.parsers import parse_json, parse_plain_text, parse_transcript, parse_vtt

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "meetingbank"


class TestVTTTeamsFormat:
    """Tests for Microsoft Teams-style <v SpeakerName> inline voice tags. Issue #34."""

    def test_vtt_parser_teams_format_extracts_speaker(self) -> None:
        """parse_vtt handles <v SpeakerName> Teams inline tags, extracting speaker and stripping tag."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:08.000
<v Mayor Johnson>Good evening everyone.

00:00:09.000 --> 00:00:18.000
<v Council Member Davis>Thank you, Mayor."""
        segments = parse_vtt(vtt_content)
        assert len(segments) == 2
        assert segments[0].speaker == "Mayor Johnson"
        assert segments[0].text == "Good evening everyone."
        assert segments[1].speaker == "Council Member Davis"
        assert segments[1].text == "Thank you, Mayor."

    def test_vtt_parser_teams_closing_tag_stripped(self) -> None:
        """parse_vtt strips optional </v> closing tags in Teams format."""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v John Smith>Hello everyone.</v>"""
        segments = parse_vtt(vtt_content)
        assert len(segments) == 1
        assert segments[0].speaker == "John Smith"
        assert segments[0].text == "Hello everyone."

    def test_vtt_parser_teams_fixture_file(self) -> None:
        """parse_vtt correctly processes the teams_sample.vtt fixture file."""
        import pathlib
        fixture = pathlib.Path(__file__).parent / "fixtures" / "teams_sample.vtt"
        content = fixture.read_text(encoding="utf-8")
        segments = parse_vtt(content)
        assert len(segments) == 3
        speakers = [s.speaker for s in segments]
        assert "Mayor Johnson" in speakers
        assert "Council Member Davis" in speakers
        # Mayor Johnson appears twice
        assert speakers.count("Mayor Johnson") == 2

    def test_vtt_parser_standard_format_unaffected(self) -> None:
        """Standard VTT with colon-style speaker labels still works correctly after Teams support."""
        vtt = """WEBVTT

00:00:01.000 --> 00:00:05.000
Speaker 1: Hello everyone.

00:00:06.000 --> 00:00:10.000
Speaker 2: Hi there.
"""
        segments = parse_vtt(vtt)
        assert len(segments) == 2
        assert segments[0].speaker == "Speaker 1"
        assert segments[1].speaker == "Speaker 2"


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

    def test_meetingbank_transcription_format(self) -> None:
        """parse_json handles canonical MeetingBank format (transcription key, speaker_id field).

        This is the format used in the real MeetingBank dataset and in
        tests/fixtures/meetingbank/sample_council_meeting.json (Issue #33).
        The transcription key was added to parsers.py in this PR; this unit test
        covers that branch directly (separate from the real-fixture test below).
        """
        data = json.dumps(
            {
                "meeting_id": "MB-TEST-001",
                "transcription": [
                    {"speaker_id": "SPEAKER_0", "text": "I call this meeting to order.", "start_time": 2.5, "end_time": 8.3},
                    {"speaker_id": "SPEAKER_1", "text": "Thank you, Mayor.", "start_time": 9.0, "end_time": 11.2},
                ],
                "summary": "Test council meeting.",
            }
        )
        segments = parse_json(data)
        assert len(segments) == 2
        assert segments[0].speaker == "SPEAKER_0"
        assert segments[0].start_time == 2.5
        assert segments[0].end_time == 8.3
        assert "order" in segments[0].text
        assert segments[1].speaker == "SPEAKER_1"

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


# ── Test: Real MeetingBank fixture ───────────────────────────────────────────


class TestMeetingBankRealFixture:
    """Tests using the real MeetingBank JSON fixture in tests/fixtures/meetingbank/.

    Issue #33: verify that the parser correctly handles the actual MeetingBank
    transcript format (transcription key, speaker_id field, times in seconds).
    """

    def test_meetingbank_json_parser_with_real_fixture(self) -> None:
        """Parser correctly handles real MeetingBank JSON format.

        The fixture uses the canonical MeetingBank schema:
          {"meeting_id": ..., "transcription": [...], "summary": ...}
        where each item has speaker_id, start_time, end_time, text.
        """
        fixture_path = FIXTURES_DIR / "sample_council_meeting.json"
        content = fixture_path.read_text(encoding="utf-8")
        segments = parse_json(content)

        # Non-trivial parse result
        assert len(segments) >= 3, f"Expected >= 3 segments, got {len(segments)}"

        # Speaker labels populated (speaker_id -> speaker)
        speakers = [s.speaker for s in segments if s.speaker is not None]
        assert len(speakers) > 0, "At least some segments should have speaker labels"

        # Timestamps present and reasonable
        times_present = [s for s in segments if s.start_time is not None and s.start_time >= 0]
        assert len(times_present) == len(segments), "All segments should have start_time"

        # Text is non-empty for all segments
        assert all(s.text.strip() for s in segments), "No segment should have empty text"

        # Timestamps are ordered (or at least non-negative)
        for seg in segments:
            assert seg.start_time >= 0, f"start_time should be >= 0, got {seg.start_time}"

    def test_meetingbank_fixture_chunking(self) -> None:
        """Real fixture produces reasonable naive chunks."""
        fixture_path = FIXTURES_DIR / "sample_council_meeting.json"
        content = fixture_path.read_text(encoding="utf-8")
        segments = parse_json(content)
        chunks = naive_chunk(segments, chunk_size=200, overlap=20)
        assert len(chunks) >= 1, "Should produce at least one chunk"
        assert all(c.strategy == "naive" for c in chunks)
