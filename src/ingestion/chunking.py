"""Chunking strategies for transcript segments."""

from __future__ import annotations

from src.ingestion.models import Chunk, TranscriptSegment


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: word count * 4/3 (≈ 1 token per 0.75 words)."""
    return max(1, len(text.split()))


def naive_chunk(
    segments: list[TranscriptSegment],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Chunk]:
    """Concatenate all text and split into fixed-size chunks by word count.

    Token count is approximated as word count (rough but dependency-free).
    Start/end times are preserved from the first/last contributing segment.

    Args:
        segments: Parsed transcript segments.
        chunk_size: Target number of words per chunk.
        overlap: Number of overlapping words between consecutive chunks.

    Returns:
        List of :class:`Chunk` instances with ``strategy="naive"``.
    """
    if not segments:
        return []

    # Build a flat list of (word, segment_index) pairs to track provenance
    word_seg_pairs: list[tuple[str, int]] = []
    for seg_idx, seg in enumerate(segments):
        for word in seg.text.split():
            word_seg_pairs.append((word, seg_idx))

    if not word_seg_pairs:
        return []

    chunks: list[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < len(word_seg_pairs):
        end = min(start + chunk_size, len(word_seg_pairs))
        window = word_seg_pairs[start:end]

        text = " ".join(w for w, _ in window)
        first_seg_idx = window[0][1]
        last_seg_idx = window[-1][1]

        chunks.append(
            Chunk(
                content=text,
                start_time=segments[first_seg_idx].start_time,
                end_time=segments[last_seg_idx].end_time,
                chunk_index=chunk_idx,
                strategy="naive",
            )
        )

        chunk_idx += 1
        start += chunk_size - overlap
        # Prevent infinite loop when overlap >= chunk_size
        if chunk_size - overlap <= 0:
            start = end

    return chunks


def speaker_turn_chunk(
    segments: list[TranscriptSegment],
    max_chunk_tokens: int = 500,
) -> list[Chunk]:
    """Group consecutive segments by the same speaker.

    If a single speaker turn exceeds *max_chunk_tokens* words it is split
    into smaller chunks.

    Args:
        segments: Parsed transcript segments.
        max_chunk_tokens: Maximum word count per chunk.

    Returns:
        List of :class:`Chunk` instances with ``strategy="speaker_turn"``.
    """
    if not segments:
        return []

    # Group consecutive segments by speaker
    groups: list[tuple[str | None, list[TranscriptSegment]]] = []
    for seg in segments:
        if groups and groups[-1][0] == seg.speaker:
            groups[-1][1].append(seg)
        else:
            groups.append((seg.speaker, [seg]))

    chunks: list[Chunk] = []
    chunk_idx = 0

    for speaker, group_segs in groups:
        combined_text = " ".join(s.text for s in group_segs)
        start_time = group_segs[0].start_time
        end_time = group_segs[-1].end_time

        words = combined_text.split()

        if _estimate_tokens(combined_text) <= max_chunk_tokens:
            chunks.append(
                Chunk(
                    content=combined_text,
                    speaker=speaker,
                    start_time=start_time,
                    end_time=end_time,
                    chunk_index=chunk_idx,
                    strategy="speaker_turn",
                )
            )
            chunk_idx += 1
        else:
            # Split long turn into sub-chunks
            pos = 0
            while pos < len(words):
                sub_words = words[pos : pos + max_chunk_tokens]
                chunks.append(
                    Chunk(
                        content=" ".join(sub_words),
                        speaker=speaker,
                        start_time=start_time,
                        end_time=end_time,
                        chunk_index=chunk_idx,
                        strategy="speaker_turn",
                    )
                )
                chunk_idx += 1
                pos += max_chunk_tokens

    return chunks
