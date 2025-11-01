-- Fix match_documents function for better debugging

-- Drop and recreate the function with better error handling
DROP FUNCTION IF EXISTS match_documents(vector, float, int, jsonb);

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

-- Grant execute permission
GRANT EXECUTE ON FUNCTION match_documents TO authenticated, anon, service_role;
