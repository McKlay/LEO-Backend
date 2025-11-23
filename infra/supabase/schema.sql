-- LEO Backend - Complete Schema for Phase 1.0.5
-- PostgreSQL + pgvector for semantic search
-- Includes: Day 4 KB Enhancement with LLM-driven chunking and summarization

-- ============================================================
-- EXTENSIONS
-- ============================================================

-- Enable pgvector extension for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- CORE TABLES (Original Phase 1.0)
-- ============================================================

-- Sessions table for anonymous session management
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS sessions_session_token_idx ON sessions (session_token);
CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions (expires_at);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    title TEXT,
    language TEXT DEFAULT 'en',
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS conversations_session_id_idx ON conversations (session_id);
CREATE INDEX IF NOT EXISTS conversations_created_at_idx ON conversations (created_at DESC);
CREATE INDEX IF NOT EXISTS conversations_archived_idx ON conversations (archived);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS messages_conversation_id_idx ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS messages_created_at_idx ON messages (created_at DESC);

-- Citations table (many-to-many with messages)
CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    article TEXT,
    url TEXT,
    confidence FLOAT CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS citations_message_id_idx ON citations (message_id);

-- Suggested actions table
CREATE TABLE IF NOT EXISTS suggested_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN ('contact', 'form', 'link', 'query', 'info')),
    label TEXT NOT NULL,
    description TEXT,
    action_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

CREATE INDEX IF NOT EXISTS suggested_actions_message_id_idx ON suggested_actions (message_id);

-- Feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    flag_reason TEXT,
    flag_details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS feedback_message_id_idx ON feedback (message_id);
CREATE INDEX IF NOT EXISTS feedback_rating_idx ON feedback (rating);

-- ============================================================
-- KNOWLEDGE BASE TABLES (Phase 1.0.5 Multi-Table Schema)
-- ============================================================

-- Labor law sources (documents/statutes metadata)
CREATE TABLE IF NOT EXISTS labor_law_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,  -- 'statute', 'irr', 'order', 'primer'
    title TEXT NOT NULL,
    reference VARCHAR(100) UNIQUE NOT NULL,  -- 'PD 442', 'RA 11058', etc.
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Labor law sections (main KB table - articles/sections)
CREATE TABLE IF NOT EXISTS labor_law_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES labor_law_sources(id) ON DELETE CASCADE,
    article_number VARCHAR(255),  -- 'Article 123', 'Section 5', 'PD 442', etc. (increased from 50 to support longer chunk IDs)
    article_title TEXT,
    full_text TEXT NOT NULL,
    summary TEXT,  -- LLM-generated summary for better semantic search
    keywords TEXT[],  -- Extracted keywords for hybrid search
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Hierarchical structure
    book VARCHAR(100),
    title_name VARCHAR(200),
    chapter VARCHAR(100),
    
    -- Format flags for LLM-driven chunking (Day 4 enhancement)
    has_table BOOLEAN DEFAULT FALSE,
    has_formula BOOLEAN DEFAULT FALSE,
    has_list BOOLEAN DEFAULT FALSE,
    
    -- Vector embedding (for semantic search)
    embedding vector(1536),
    
    -- Additional columns (added after initial schema)
    semantic_type VARCHAR(50),  -- 'decree', 'article', 'section', 'rule', etc.
    section_number INTEGER,  -- Numeric section/article number if applicable
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Labor law chunks (for very long articles that need splitting)
-- Day 4: Enhanced with summary and keywords columns
CREATE TABLE IF NOT EXISTS labor_law_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id UUID REFERENCES labor_law_sections(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    summary TEXT,  -- Day 4: GPT-4o-mini generated summary
    keywords TEXT[],  -- Day 4: Extracted legal keywords
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ingestion history (Day 4: Incremental ingestion tracking)
CREATE TABLE IF NOT EXISTS ingestion_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name VARCHAR(255) NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for change detection
    chunk_count INT NOT NULL,
    token_count INT,
    ingestion_method VARCHAR(50),  -- 'llm_chunking' or 'regex_chunking'
    status VARCHAR(20) NOT NULL,  -- 'success', 'failed', 'in_progress'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- LEGACY TABLE (Backward Compatibility)
-- ============================================================

-- Keep old labor_law_embeddings table for backward compatibility
-- This will be deprecated in future versions
CREATE TABLE IF NOT EXISTS labor_law_embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ============================================================
-- INDEXES
-- ============================================================

-- === Conversations/Messages Indexes (Already defined above) ===

-- === Knowledge Base Indexes ===

-- Full-text search on labor_law_sections
CREATE INDEX IF NOT EXISTS idx_sections_fts 
ON labor_law_sections 
USING GIN(to_tsvector('english', full_text || ' ' || COALESCE(article_title, '')));

-- B-tree indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_sections_article 
ON labor_law_sections(article_number);

CREATE INDEX IF NOT EXISTS idx_sections_source 
ON labor_law_sections(source_id);

-- GIN index on keywords for efficient array search
CREATE INDEX IF NOT EXISTS idx_sections_keywords
ON labor_law_sections
USING GIN (keywords);

-- Note: HNSW indexes for vector search are created separately
-- See: infra/supabase/create_hnsw_indexes.sql
-- (Requires maintenance_work_mem >= 64MB)

-- Chunks table indexes
CREATE INDEX IF NOT EXISTS idx_chunks_section 
ON labor_law_chunks(section_id);

-- Day 4: GIN index on chunk keywords for efficient search
CREATE INDEX IF NOT EXISTS labor_law_chunks_keywords_idx
ON labor_law_chunks
USING GIN (keywords);

-- Ingestion history indexes
CREATE INDEX IF NOT EXISTS idx_ingestion_history_filename 
ON ingestion_history(file_name);

CREATE INDEX IF NOT EXISTS idx_ingestion_history_hash 
ON ingestion_history(file_hash);

-- Legacy table indexes
-- Note: Vector indexes commented out to avoid memory issues
-- Uncomment if needed or create separately
-- CREATE INDEX IF NOT EXISTS labor_law_embeddings_embedding_idx 
-- ON labor_law_embeddings 
-- USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

CREATE INDEX IF NOT EXISTS labor_law_embeddings_metadata_idx 
ON labor_law_embeddings 
USING GIN (metadata);

CREATE INDEX IF NOT EXISTS labor_law_embeddings_created_at_idx 
ON labor_law_embeddings (created_at DESC);

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to relevant tables
DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_labor_law_embeddings_updated_at ON labor_law_embeddings;
CREATE TRIGGER update_labor_law_embeddings_updated_at 
    BEFORE UPDATE ON labor_law_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_labor_law_sources_updated_at ON labor_law_sources;
CREATE TRIGGER update_labor_law_sources_updated_at
    BEFORE UPDATE ON labor_law_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_labor_law_sections_updated_at ON labor_law_sections;
CREATE TRIGGER update_labor_law_sections_updated_at
    BEFORE UPDATE ON labor_law_sections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ingestion_history_updated_at ON ingestion_history;
CREATE TRIGGER update_ingestion_history_updated_at
    BEFORE UPDATE ON ingestion_history
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Legacy match_documents function (for backward compatibility)
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 10,
    filter_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        labor_law_embeddings.id,
        labor_law_embeddings.content,
        labor_law_embeddings.metadata,
        1 - (labor_law_embeddings.embedding <=> query_embedding) as similarity
    FROM labor_law_embeddings
    WHERE 
        (1 - (labor_law_embeddings.embedding <=> query_embedding)) >= match_threshold
        AND (
            filter_metadata::text = '{}'
            OR labor_law_embeddings.metadata @> filter_metadata
        )
    ORDER BY labor_law_embeddings.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- New function for searching sections (Phase 1.0.5)
CREATE OR REPLACE FUNCTION match_sections(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 10,
    filter_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id uuid,
    article_number varchar,
    article_title text,
    full_text text,
    summary text,
    keywords text[],
    metadata jsonb,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        labor_law_sections.id,
        labor_law_sections.article_number,
        labor_law_sections.article_title,
        labor_law_sections.full_text,
        labor_law_sections.summary,
        labor_law_sections.keywords,
        labor_law_sections.metadata,
        1 - (labor_law_sections.embedding <=> query_embedding) as similarity
    FROM labor_law_sections
    WHERE 
        labor_law_sections.embedding IS NOT NULL
        AND (1 - (labor_law_sections.embedding <=> query_embedding)) >= match_threshold
        AND (
            filter_metadata::text = '{}'
            OR labor_law_sections.metadata @> filter_metadata
        )
    ORDER BY labor_law_sections.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Function for searching chunks (Day 4 enhancement)
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    section_id uuid,
    chunk_text text,
    summary text,
    keywords text[],
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        labor_law_chunks.id,
        labor_law_chunks.section_id,
        labor_law_chunks.chunk_text,
        labor_law_chunks.summary,
        labor_law_chunks.keywords,
        1 - (labor_law_chunks.embedding <=> query_embedding) as similarity
    FROM labor_law_chunks
    WHERE 
        labor_law_chunks.embedding IS NOT NULL
        AND (1 - (labor_law_chunks.embedding <=> query_embedding)) >= match_threshold
    ORDER BY labor_law_chunks.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ============================================================
-- VIEWS
-- ============================================================

-- Conversation summaries view
CREATE OR REPLACE VIEW conversation_summaries AS
SELECT 
    c.id,
    c.session_id,
    c.title,
    c.language,
    c.archived,
    c.created_at,
    c.updated_at,
    COUNT(m.id) as message_count,
    MAX(m.created_at) as last_message_at
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id, c.session_id, c.title, c.language, c.archived, c.created_at, c.updated_at;

-- ============================================================
-- COMMENTS (Documentation)
-- ============================================================

COMMENT ON TABLE labor_law_embeddings IS 'Legacy vector store (deprecated - use labor_law_sections/chunks)';
COMMENT ON TABLE labor_law_sources IS 'Philippine labor law documents metadata';
COMMENT ON TABLE labor_law_sections IS 'Labor law articles/sections with embeddings and summaries';
COMMENT ON TABLE labor_law_chunks IS 'Chunks from very long articles (Day 4: with summaries and keywords)';
COMMENT ON TABLE ingestion_history IS 'Tracks file ingestion for incremental updates (Day 4)';
COMMENT ON TABLE sessions IS 'Anonymous user sessions with JWT token management';
COMMENT ON TABLE conversations IS 'Multi-turn conversation threads';
COMMENT ON TABLE messages IS 'Individual messages in conversations';
COMMENT ON TABLE citations IS 'Legal citations linked to assistant messages';
COMMENT ON TABLE suggested_actions IS 'Context-aware action suggestions for users';
COMMENT ON TABLE feedback IS 'User feedback on message quality';

COMMENT ON FUNCTION match_documents IS 'Legacy semantic search (deprecated - use match_sections/match_chunks)';
COMMENT ON FUNCTION match_sections IS 'Semantic search on labor law sections with summaries';
COMMENT ON FUNCTION match_chunks IS 'Semantic search on labor law chunks with summaries (Day 4)';

-- ============================================================
-- GRANTS (Permissions)
-- ============================================================

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION match_documents TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION match_sections TO authenticated, anon, service_role;
GRANT EXECUTE ON FUNCTION match_chunks TO authenticated, anon, service_role;

-- Note: Table permissions should be configured based on your Supabase RLS policies
