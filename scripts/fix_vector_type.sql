-- Fix vector type issue in labor_law_embeddings table
-- Run each step separately to avoid errors

-- Step 1: Add temporary vector column
ALTER TABLE labor_law_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- Step 2: Convert TEXT to VECTOR
UPDATE labor_law_embeddings SET embedding_vec = embedding::vector WHERE embedding_vec IS NULL;

-- Step 3: Drop old TEXT column
ALTER TABLE labor_law_embeddings DROP COLUMN IF EXISTS embedding;

-- Step 4: Rename vector column
ALTER TABLE labor_law_embeddings RENAME COLUMN embedding_vec TO embedding;

-- Step 5: Drop old index if exists
DROP INDEX IF EXISTS labor_law_embeddings_embedding_idx;

-- Step 6: Create new vector index
CREATE INDEX labor_law_embeddings_embedding_idx ON labor_law_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Step 7: Verify the fix
SELECT id, content, pg_typeof(embedding) as embedding_type, metadata FROM labor_law_embeddings LIMIT 3;
