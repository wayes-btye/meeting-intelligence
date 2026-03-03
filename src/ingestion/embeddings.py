"""Embedding helpers using OpenAI text-embedding-3-small."""

from __future__ import annotations

import anthropic
from anthropic.types import TextBlock
from openai import OpenAI

from src.config import settings
from src.ingestion.models import Chunk


def embed_texts(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed a list of texts using the OpenAI embeddings API.

    Args:
        texts: Strings to embed.
        model: OpenAI embedding model name.

    Returns:
        A list of embedding vectors (one per input text).
    """
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]


def embed_chunks(chunks: list[Chunk]) -> list[tuple[Chunk, list[float]]]:
    """Embed chunks and return ``(chunk, embedding)`` pairs.

    Args:
        chunks: Chunks whose ``content`` will be embedded.

    Returns:
        List of ``(Chunk, embedding_vector)`` tuples.
    """
    texts = [c.content for c in chunks]
    embeddings = embed_texts(texts)
    return list(zip(chunks, embeddings, strict=True))


def generate_chunk_context(chunk: Chunk, meeting_title: str) -> str:
    """Call Claude Haiku to generate retrieval context for a chunk.

    Generates a 1-2 sentence description that provides document-level context
    for the chunk. This is prepended to the chunk text before embedding so
    that the embedding captures both document context and local content
    (contextual retrieval, per Anthropic research).

    Issue #66: ~$0.001 per chunk at Haiku pricing.

    Args:
        chunk: The chunk whose content needs contextualising.
        meeting_title: Human-readable title of the meeting this chunk belongs to.

    Returns:
        A concise 1-2 sentence context string.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Meeting title: {meeting_title}\n\n"
        f"Chunk text:\n{chunk.content}\n\n"
        "Write 1-2 sentences of context to help retrieve this chunk when searching the meeting. "
        "Include the meeting topic, speaker if known, and what this excerpt is about. Be concise."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    # Narrow union content block to TextBlock — plain text prompt always returns TextBlock. (#66)
    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise ValueError(f"Expected TextBlock from Claude, got {type(block).__name__}")
    return block.text.strip()


def embed_chunks_with_context(
    chunks: list[Chunk],
    meeting_title: str,
) -> list[tuple[Chunk, list[float]]]:
    """Embed chunks with Claude-generated context prepended to each chunk text.

    For each chunk, calls ``generate_chunk_context()`` to produce a short
    retrieval-oriented summary, prepends it to the chunk content, and embeds
    the enriched text.  The original ``chunk.content`` is NOT modified — only
    the text sent to the embedding API is enriched.

    Issue #66: opt-in via ``PipelineConfig.contextual_retrieval``.

    Args:
        chunks: Chunks to embed.
        meeting_title: Human-readable meeting title, forwarded to Claude for context.

    Returns:
        List of ``(Chunk, embedding_vector)`` tuples (same structure as
        ``embed_chunks()`` for drop-in compatibility in the pipeline).
    """
    results: list[tuple[Chunk, list[float]]] = []
    for chunk in chunks:
        context = generate_chunk_context(chunk, meeting_title)
        enriched_text = f"{context}\n\n{chunk.content}"
        embedding = embed_texts([enriched_text])[0]
        results.append((chunk, embedding))
    return results
