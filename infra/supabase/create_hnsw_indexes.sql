-- HNSW Indexes for Vector Similarity Search
-- Requires: maintenance_work_mem >= 64MB
-- Run this separately after main schema if needed

-- Increase memory temporarily for index creation
SET maintenance_work_mem = '64MB';

-- Create HNSW index on labor_law_sections
CREATE INDEX IF NOT EXISTS idx_sections_embedding_hnsw 
ON labor_law_sections 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Create HNSW index on labor_law_chunks
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON labor_law_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Reset to default
RESET maintenance_work_mem;

-- Verify indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE indexname LIKE '%_embedding_hnsw'
ORDER BY tablename, indexname;
