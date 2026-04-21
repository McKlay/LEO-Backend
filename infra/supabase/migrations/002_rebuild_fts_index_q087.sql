-- Migration: Revert FTS GIN index to full_text only
--
-- The Q087 expanded-tsvector approach (full_text + article_title + source_title)
-- was reverted in keyword_search because expanding FTS to metadata fields
-- artificially inflates lexical strategy scores — document content (full_text)
-- alone should define FTS relevance.
--
-- This migration restores the original index on full_text only, which
-- aligns with the to_tsvector('english', s.full_text) expression now used
-- in keyword_search.

-- Step 1: Drop the Q087 expanded index (includes source_title)
DROP INDEX IF EXISTS idx_sections_fts_v2;

-- Step 2: Drop the pre-Q087 index (includes article_title) so it can be recreated cleanly
DROP INDEX IF EXISTS idx_sections_fts;

-- Step 3: Restore the canonical GIN index on full_text only
CREATE INDEX idx_sections_fts
ON labor_law_sections
USING GIN(to_tsvector('english', full_text));
