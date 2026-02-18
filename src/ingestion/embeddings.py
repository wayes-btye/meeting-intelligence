"""Embedding helpers using OpenAI text-embedding-3-small."""

from __future__ import annotations

from openai import OpenAI

from src.ingestion.models import Chunk


def embed_texts(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed a list of texts using the OpenAI embeddings API.

    Args:
        texts: Strings to embed.
        model: OpenAI embedding model name.

    Returns:
        A list of embedding vectors (one per input text).
    """
    client = OpenAI()  # reads OPENAI_API_KEY from env
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
