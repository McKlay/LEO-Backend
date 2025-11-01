-- Test similarity search manually

-- Check if we have embeddings
SELECT COUNT(*) as total_documents FROM labor_law_embeddings;

-- Get a sample embedding
SELECT id, content, substring(content from 1 for 100) as preview
FROM labor_law_embeddings
LIMIT 1;

-- Test vector similarity (you'll need to replace the embedding array with actual values)
-- SELECT 
--     id,
--     content,
--     1 - (embedding <=> '[...]'::vector) as similarity
-- FROM labor_law_embeddings
-- ORDER BY embedding <=> '[...]'::vector
-- LIMIT 5;
