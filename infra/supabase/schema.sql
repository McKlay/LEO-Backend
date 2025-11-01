-- LEO Backend - Supabase Schema
-- PostgreSQL + pgvector for semantic search

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create labor_law_embeddings table for knowledge base chunks
CREATE TABLE IF NOT EXISTS labor_law_embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS labor_law_embeddings_embedding_idx 
    ON labor_law_embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS labor_law_embeddings_metadata_idx 
    ON labor_law_embeddings 
    USING GIN (metadata);

CREATE INDEX IF NOT EXISTS labor_law_embeddings_created_at_idx 
    ON labor_law_embeddings (created_at DESC);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_labor_law_embeddings_updated_at 
    BEFORE UPDATE ON labor_law_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create function for similarity search
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
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        labor_law_embeddings.id,
        labor_law_embeddings.content,
        labor_law_embeddings.metadata,
        1 - (labor_law_embeddings.embedding <=> query_embedding) as similarity
    FROM labor_law_embeddings
    WHERE 
        (1 - (labor_law_embeddings.embedding <=> query_embedding)) >= match_threshold
        AND (
            filter_metadata = '{}'::jsonb 
            OR labor_law_embeddings.metadata @> filter_metadata
        )
    ORDER BY labor_law_embeddings.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Create sessions table for anonymous session management
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

-- Create conversations table
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

CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create messages table
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

-- Create citations table (many-to-many with messages)
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

-- Create suggested_actions table
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

-- Create feedback table
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

-- Row Level Security (RLS) - Optional for future multi-tenancy
-- For now, using service role key bypasses RLS
-- ALTER TABLE labor_law_embeddings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Grant necessary permissions (adjust based on your Supabase role setup)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

-- Create view for conversation summaries
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

-- Comments for documentation
COMMENT ON TABLE labor_law_embeddings IS 'Vector store for Philippine labor law knowledge base chunks';
COMMENT ON TABLE sessions IS 'Anonymous user sessions with JWT token management';
COMMENT ON TABLE conversations IS 'Multi-turn conversation threads';
COMMENT ON TABLE messages IS 'Individual messages in conversations';
COMMENT ON TABLE citations IS 'Legal citations linked to assistant messages';
COMMENT ON TABLE suggested_actions IS 'Context-aware action suggestions for users';
COMMENT ON TABLE feedback IS 'User feedback on message quality';

COMMENT ON FUNCTION match_documents IS 'Semantic search function using cosine similarity on embeddings';
