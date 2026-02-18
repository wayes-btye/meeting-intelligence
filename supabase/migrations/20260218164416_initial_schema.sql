-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Meetings table
CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source_file TEXT,
    transcript_format TEXT,
    duration_seconds INTEGER,
    num_speakers INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    raw_transcript TEXT,
    summary TEXT
);

-- Chunks table (for RAG)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    speaker TEXT,
    start_time FLOAT,
    end_time FLOAT,
    chunk_index INTEGER,
    strategy TEXT DEFAULT 'naive',
    embedding halfvec(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast cosine similarity
CREATE INDEX chunks_embedding_idx ON chunks
USING hnsw (embedding halfvec_cosine_ops);

-- Full-text search index for hybrid retrieval
ALTER TABLE chunks ADD COLUMN fts tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX chunks_fts_idx ON chunks USING gin(fts);

-- Extracted items table
CREATE TABLE extracted_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL,
    content TEXT NOT NULL,
    assignee TEXT,
    due_date TEXT,
    speaker TEXT,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Match function for semantic RAG retrieval
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding halfvec(1536),
    match_count INT DEFAULT 10,
    filter_meeting_id UUID DEFAULT NULL,
    filter_strategy TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    meeting_id UUID,
    content TEXT,
    speaker TEXT,
    start_time FLOAT,
    end_time FLOAT,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.meeting_id, c.content, c.speaker,
        c.start_time, c.end_time,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM chunks c
    WHERE (filter_meeting_id IS NULL OR c.meeting_id = filter_meeting_id)
      AND (filter_strategy IS NULL OR c.strategy = filter_strategy)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Hybrid search function combining vector + full-text
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding halfvec(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    text_weight FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id UUID, meeting_id UUID, content TEXT,
    speaker TEXT, start_time FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT c.id, c.meeting_id, c.content, c.speaker, c.start_time,
               1 - (c.embedding <=> query_embedding) as vector_score
        FROM chunks c
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    text_results AS (
        SELECT c.id, c.meeting_id, c.content, c.speaker, c.start_time,
               ts_rank(c.fts, plainto_tsquery('english', query_text)) as text_score
        FROM chunks c
        WHERE c.fts @@ plainto_tsquery('english', query_text)
        LIMIT match_count * 2
    )
    SELECT COALESCE(v.id, t.id),
           COALESCE(v.meeting_id, t.meeting_id),
           COALESCE(v.content, t.content),
           COALESCE(v.speaker, t.speaker),
           COALESCE(v.start_time, t.start_time),
           (COALESCE(v.vector_score, 0) * vector_weight +
            COALESCE(t.text_score, 0) * text_weight) as combined_score
    FROM vector_results v
    FULL OUTER JOIN text_results t ON v.id = t.id
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;
