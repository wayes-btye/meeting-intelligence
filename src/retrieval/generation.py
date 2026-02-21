"""Claude-powered answer generation with source attribution."""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic
from anthropic.types import TextBlock

from src.config import settings


def generate_answer(question: str, context_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate an answer using Claude with source attribution.

    Args:
        question: The user's question.
        context_chunks: Retrieved transcript chunks with metadata.

    Returns:
        Dictionary with answer, sources, model, and usage info.
    """
    # Format context
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks):
        speaker = chunk.get("speaker", "Unknown")
        time = chunk.get("start_time")
        time_str = f" [{time:.1f}s]" if time else ""
        context_parts.append(f"[Source {i + 1}] {speaker}{time_str}: {chunk['content']}")

    context = "\n\n".join(context_parts)

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        system=(
            "You are a meeting intelligence assistant. Answer questions based "
            "on the provided meeting transcript excerpts.\n\n"
            "Rules:\n"
            "- Only answer based on the provided context. If the answer isn't "
            "in the context, say so.\n"
            "- Cite your sources using [Source N] notation.\n"
            "- Include speaker names when relevant.\n"
            "- Be concise and direct."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Context from meeting transcripts:\n\n{context}\n\nQuestion: {question}"
                ),
            }
        ],
    )

    # Narrow the content block type — response.content[0] is a union of block types;
    # we always request plain text so the first block should be TextBlock. (#30)
    block = response.content[0]
    if not isinstance(block, TextBlock):
        raise ValueError(f"Expected TextBlock from Claude, got {type(block).__name__}")

    return {
        "answer": block.text,
        "sources": context_chunks,
        "model": response.model,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
