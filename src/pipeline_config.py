"""Pipeline configuration: strategy enums and PipelineConfig dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChunkingStrategy(str, Enum):
    """Available chunking strategies for transcript ingestion."""

    NAIVE = "naive"
    SPEAKER_TURN = "speaker_turn"


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies for querying."""

    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable configuration for the RAG pipeline.

    Holds the active chunking and retrieval strategies.  Defaults mirror
    the project's current behaviour (speaker-turn chunking, hybrid search).
    """

    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SPEAKER_TURN
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
