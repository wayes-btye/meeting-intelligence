"""Unit tests for contextual retrieval — Issue #66.

All tests mock external API calls (Anthropic Claude, OpenAI embeddings).
No live API calls are made in this file.  Tests requiring real Claude calls
are marked @pytest.mark.expensive.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from anthropic.types import TextBlock

from src.ingestion.models import Chunk

# ---------------------------------------------------------------------------
# generate_chunk_context
# ---------------------------------------------------------------------------


class TestGenerateChunkContext:
    """Tests for generate_chunk_context() in src/ingestion/embeddings.py."""

    @patch("src.ingestion.embeddings.anthropic.Anthropic")
    def test_calls_claude_haiku_and_returns_text(self, mock_anthropic_cls: MagicMock) -> None:
        """generate_chunk_context calls Claude and returns the response text."""
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value.content = [
            TextBlock(type="text", text="This chunk is from a Budget Meeting discussing Q4 allocations.")
        ]

        from src.ingestion.embeddings import generate_chunk_context

        chunk = Chunk(content="The motion to allocate funds was passed unanimously.", chunk_index=0)
        result = generate_chunk_context(chunk, "Budget Meeting")

        assert result == "This chunk is from a Budget Meeting discussing Q4 allocations."
        mock_client.messages.create.assert_called_once()

    @patch("src.ingestion.embeddings.anthropic.Anthropic")
    def test_passes_meeting_title_in_prompt(self, mock_anthropic_cls: MagicMock) -> None:
        """generate_chunk_context includes the meeting title in the Claude prompt."""
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value.content = [TextBlock(type="text", text="Context.")]

        from src.ingestion.embeddings import generate_chunk_context

        chunk = Chunk(content="Some text.", chunk_index=0)
        generate_chunk_context(chunk, "Annual Review 2025")

        call_kwargs = mock_client.messages.create.call_args
        # Extract the messages argument to verify the title is present
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][2]
        user_message_content = messages[0]["content"]
        assert "Annual Review 2025" in user_message_content

    @patch("src.ingestion.embeddings.anthropic.Anthropic")
    def test_passes_chunk_content_in_prompt(self, mock_anthropic_cls: MagicMock) -> None:
        """generate_chunk_context includes the chunk content in the Claude prompt."""
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value.content = [TextBlock(type="text", text="Context.")]

        from src.ingestion.embeddings import generate_chunk_context

        chunk = Chunk(content="The budget was approved for Q4.", chunk_index=0)
        generate_chunk_context(chunk, "Finance Meeting")

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs[1]["messages"] if call_kwargs[1] else call_kwargs[0][2]
        user_message_content = messages[0]["content"]
        assert "The budget was approved for Q4." in user_message_content

    @patch("src.ingestion.embeddings.anthropic.Anthropic")
    def test_strips_whitespace_from_response(self, mock_anthropic_cls: MagicMock) -> None:
        """generate_chunk_context strips leading/trailing whitespace from the response."""
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value.content = [
            TextBlock(type="text", text="  Context with extra whitespace.  \n")
        ]

        from src.ingestion.embeddings import generate_chunk_context

        chunk = Chunk(content="Some text.", chunk_index=0)
        result = generate_chunk_context(chunk, "Meeting")
        assert result == "Context with extra whitespace."

    @patch("src.ingestion.embeddings.anthropic.Anthropic")
    def test_uses_haiku_model(self, mock_anthropic_cls: MagicMock) -> None:
        """generate_chunk_context uses the claude-haiku-4-5 model (cheap, fast)."""
        mock_client = mock_anthropic_cls.return_value
        mock_client.messages.create.return_value.content = [TextBlock(type="text", text="Context.")]

        from src.ingestion.embeddings import generate_chunk_context

        chunk = Chunk(content="Text.", chunk_index=0)
        generate_chunk_context(chunk, "Meeting")

        call_kwargs = mock_client.messages.create.call_args
        model_used = call_kwargs[1].get("model") or call_kwargs[0][0]
        assert "haiku" in model_used.lower()


# ---------------------------------------------------------------------------
# embed_chunks_with_context
# ---------------------------------------------------------------------------


class TestEmbedChunksWithContext:
    """Tests for embed_chunks_with_context() in src/ingestion/embeddings.py."""

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_returns_chunk_embedding_pairs(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_chunks_with_context returns (Chunk, embedding) tuples."""
        mock_gen_ctx.return_value = "This is retrieval context."
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        from src.ingestion.embeddings import embed_chunks_with_context

        chunks = [Chunk(content="Meeting text here.", chunk_index=0)]
        result = embed_chunks_with_context(chunks, "Test Meeting")

        assert len(result) == 1
        chunk_out, embedding = result[0]
        assert chunk_out is chunks[0]
        assert embedding == [0.1, 0.2, 0.3]

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_enriched_text_contains_context_and_content(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_texts is called with context prepended to chunk content."""
        mock_gen_ctx.return_value = "Budget context sentence."
        mock_embed.return_value = [[0.5, 0.6]]

        from src.ingestion.embeddings import embed_chunks_with_context

        chunk = Chunk(content="The budget was approved.", chunk_index=0)
        embed_chunks_with_context([chunk], "Budget Meeting")

        call_args = mock_embed.call_args
        texts_arg = call_args[0][0]  # first positional arg is the texts list
        assert len(texts_arg) == 1
        enriched = texts_arg[0]
        assert "Budget context sentence." in enriched
        assert "The budget was approved." in enriched

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_original_chunk_content_unchanged(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_chunks_with_context does NOT modify the original chunk.content."""
        mock_gen_ctx.return_value = "Prepended context."
        mock_embed.return_value = [[0.1, 0.2]]

        from src.ingestion.embeddings import embed_chunks_with_context

        chunk = Chunk(content="Original chunk text.", chunk_index=0)
        embed_chunks_with_context([chunk], "Meeting")

        # The chunk object should be unmodified
        assert chunk.content == "Original chunk text."

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_handles_multiple_chunks(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_chunks_with_context processes each chunk independently."""
        mock_gen_ctx.side_effect = ["Context A.", "Context B."]
        mock_embed.side_effect = [[[0.1, 0.2]], [[0.3, 0.4]]]

        from src.ingestion.embeddings import embed_chunks_with_context

        chunks = [
            Chunk(content="Chunk A text.", chunk_index=0),
            Chunk(content="Chunk B text.", chunk_index=1),
        ]
        result = embed_chunks_with_context(chunks, "Meeting")

        assert len(result) == 2
        assert result[0][0] is chunks[0]
        assert result[1][0] is chunks[1]
        assert mock_gen_ctx.call_count == 2
        assert mock_embed.call_count == 2

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_empty_chunks_returns_empty_list(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_chunks_with_context returns [] when given an empty chunk list."""
        from src.ingestion.embeddings import embed_chunks_with_context

        result = embed_chunks_with_context([], "Meeting")
        assert result == []
        mock_gen_ctx.assert_not_called()
        mock_embed.assert_not_called()

    @patch("src.ingestion.embeddings.embed_texts")
    @patch("src.ingestion.embeddings.generate_chunk_context")
    def test_meeting_title_forwarded_to_generate_context(
        self, mock_gen_ctx: MagicMock, mock_embed: MagicMock
    ) -> None:
        """embed_chunks_with_context passes the meeting title to generate_chunk_context."""
        mock_gen_ctx.return_value = "Context."
        mock_embed.return_value = [[0.1]]

        from src.ingestion.embeddings import embed_chunks_with_context

        chunk = Chunk(content="Text.", chunk_index=0)
        embed_chunks_with_context([chunk], "Specific Meeting Title")

        mock_gen_ctx.assert_called_once_with(chunk, "Specific Meeting Title")


# ---------------------------------------------------------------------------
# Pipeline integration — ingest_transcript contextual_retrieval flag
# ---------------------------------------------------------------------------


class TestIngestTranscriptContextualRetrievalFlag:
    """Tests that ingest_transcript routes to the right embed function."""

    @patch("src.ingestion.pipeline.store_chunks")
    @patch("src.ingestion.pipeline.store_meeting")
    @patch("src.ingestion.pipeline.get_supabase_client")
    @patch("src.ingestion.pipeline.embed_chunks_with_context")
    @patch("src.ingestion.pipeline.embed_chunks")
    def test_contextual_retrieval_false_uses_embed_chunks(
        self,
        mock_embed_chunks: MagicMock,
        mock_embed_ctx: MagicMock,
        mock_get_client: MagicMock,
        mock_store_meeting: MagicMock,
        mock_store_chunks: MagicMock,
    ) -> None:
        """When contextual_retrieval=False, embed_chunks is called (not embed_chunks_with_context)."""
        mock_embed_chunks.return_value = []
        mock_store_meeting.return_value = "00000000-0000-0000-0000-000000000001"

        from src.ingestion.pipeline import ingest_transcript

        ingest_transcript(
            content="Speaker 1: Hello.",
            format="text",
            title="Test Meeting",
            contextual_retrieval=False,
        )

        mock_embed_chunks.assert_called_once()
        mock_embed_ctx.assert_not_called()

    @patch("src.ingestion.pipeline.store_chunks")
    @patch("src.ingestion.pipeline.store_meeting")
    @patch("src.ingestion.pipeline.get_supabase_client")
    @patch("src.ingestion.pipeline.embed_chunks_with_context")
    @patch("src.ingestion.pipeline.embed_chunks")
    def test_contextual_retrieval_true_uses_embed_chunks_with_context(
        self,
        mock_embed_chunks: MagicMock,
        mock_embed_ctx: MagicMock,
        mock_get_client: MagicMock,
        mock_store_meeting: MagicMock,
        mock_store_chunks: MagicMock,
    ) -> None:
        """When contextual_retrieval=True, embed_chunks_with_context is called."""
        mock_embed_ctx.return_value = []
        mock_store_meeting.return_value = "00000000-0000-0000-0000-000000000002"

        from src.ingestion.pipeline import ingest_transcript

        ingest_transcript(
            content="Speaker 1: Hello.",
            format="text",
            title="Test Meeting",
            contextual_retrieval=True,
        )

        mock_embed_ctx.assert_called_once()
        mock_embed_chunks.assert_not_called()

    @patch("src.ingestion.pipeline.store_chunks")
    @patch("src.ingestion.pipeline.store_meeting")
    @patch("src.ingestion.pipeline.get_supabase_client")
    @patch("src.ingestion.pipeline.embed_chunks_with_context")
    @patch("src.ingestion.pipeline.embed_chunks")
    def test_contextual_retrieval_passes_title_to_embed(
        self,
        mock_embed_chunks: MagicMock,
        mock_embed_ctx: MagicMock,
        mock_get_client: MagicMock,
        mock_store_meeting: MagicMock,
        mock_store_chunks: MagicMock,
    ) -> None:
        """When contextual_retrieval=True, the meeting title is forwarded to embed_chunks_with_context."""
        mock_embed_ctx.return_value = []
        mock_store_meeting.return_value = "00000000-0000-0000-0000-000000000003"

        from src.ingestion.pipeline import ingest_transcript

        ingest_transcript(
            content="Speaker 1: Hello.",
            format="text",
            title="Q4 Budget Review",
            contextual_retrieval=True,
        )

        call_args = mock_embed_ctx.call_args
        # Second positional arg (or keyword arg) should be the title
        _, kwargs = call_args
        # call is embed_chunks_with_context(chunks, title)
        title_passed = call_args[0][1] if len(call_args[0]) > 1 else kwargs.get("meeting_title")
        assert title_passed == "Q4 Budget Review"

    @patch("src.ingestion.pipeline.store_chunks")
    @patch("src.ingestion.pipeline.store_meeting")
    @patch("src.ingestion.pipeline.get_supabase_client")
    @patch("src.ingestion.pipeline.embed_chunks")
    def test_default_uses_standard_embedding(
        self,
        mock_embed_chunks: MagicMock,
        mock_get_client: MagicMock,
        mock_store_meeting: MagicMock,
        mock_store_chunks: MagicMock,
    ) -> None:
        """Default contextual_retrieval=False preserves existing pipeline behaviour."""
        mock_embed_chunks.return_value = []
        mock_store_meeting.return_value = "00000000-0000-0000-0000-000000000004"

        from src.ingestion.pipeline import ingest_transcript

        # Call without contextual_retrieval keyword — should default to False
        ingest_transcript(
            content="Speaker 1: Hello.",
            format="text",
            title="Test Meeting",
        )

        mock_embed_chunks.assert_called_once()


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------


class TestPipelineConfigContextualRetrieval:
    """Tests for the contextual_retrieval field on PipelineConfig."""

    def test_default_is_false(self) -> None:
        """PipelineConfig.contextual_retrieval defaults to False."""
        from src.pipeline_config import PipelineConfig

        config = PipelineConfig()
        assert config.contextual_retrieval is False

    def test_can_be_set_to_true(self) -> None:
        """PipelineConfig.contextual_retrieval can be set to True."""
        from src.pipeline_config import PipelineConfig

        config = PipelineConfig(contextual_retrieval=True)
        assert config.contextual_retrieval is True
