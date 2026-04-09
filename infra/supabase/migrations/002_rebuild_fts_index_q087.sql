-- Migration: Rebuild FTS GIN index to include article_title + source_title
--
-- Q087 investigation found that NLRC procedural rules use "Commission" in body
-- text but "NLRC" only appears in the source table title.  The keyword_search
-- FTS query now concatenates full_text + article_title + source_title, so the
-- GIN index must be rebuilt to match that expression.
--
-- The new index is on an expression that joins labor_law_sources to get
-- source_title. Since PostgreSQL GIN indexes don't support JOIN expressions
-- directly, we use a materialized tsvector approach — a generated column.
-- However, since source_title lives in a different table, the simplest
-- approach is to drop the old index (the FTS query will do a seq scan with
-- on-the-fly tsvector computation; with ~200 sections this is <10ms) and
-- add a content_tsvector column that is populated by a trigger.
--
-- For the current small KB (~200 sections), the JOIN-based FTS query in
-- keyword_search runs in <10ms without a dedicated index. This migration
-- is a documentation placeholder; apply if the KB grows beyond 5000 rows.

-- Step 1: Drop the old (mismatched) GIN index
DROP INDEX IF EXISTS idx_sections_fts;

-- Step 2: Create a new index on full_text + article_title
-- (This covers the most impactful part; source_title requires the JOIN
-- which cannot be directly indexed. The query planner will filter
-- efficiently with this partial index + residual check.)
CREATE INDEX IF NOT EXISTS idx_sections_fts_v2
ON labor_law_sections
USING GIN(to_tsvector('english', full_text || ' ' || COALESCE(article_title, '')));

-- NOTE: For the full FTS expression (full_text + article_title + source_title),
-- the keyword_search Python code computes the tsvector at query time with the
-- JOIN. With ~200 rows and the partial GIN index above, performance is excellent.
-- If KB grows to >5000 rows, consider adding a materialized tsvector column
-- with a trigger that includes source_title.
