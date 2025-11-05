-- Create an RPC function to properly insert vector embeddings
-- Run this in Supabase SQL Editor

CREATE OR REPLACE FUNCTION insert_embedding(
    p_id TEXT,
    p_content TEXT,
    p_embedding_array FLOAT[],
    p_metadata JSONB
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO labor_law_embeddings (id, content, embedding, metadata)
    VALUES (p_id, p_content, p_embedding_array::vector(1536), p_metadata)
    ON CONFLICT (id) 
    DO UPDATE SET 
        content = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        updated_at = NOW();
END;
$$;

-- Test the function
SELECT insert_embedding(
    'test_id',
    'Test content',
    ARRAY[0.1, 0.2, 0.3]::FLOAT[], -- This will be extended to 1536 in actual use
    '{"source": "test"}'::JSONB
);

-- Verify
SELECT id, pg_typeof(embedding) as type FROM labor_law_embeddings WHERE id = 'test_id';
