-- Schema Migration: Add Missing Columns for Multi-Strategy Retrieval
-- Date: 2025-11-16
-- Purpose: Align schema with actual implementation and document structures

-- ============================================================
-- ADD MISSING COLUMNS TO labor_law_sources
-- ============================================================

-- Add reference column for fast law lookup (Strategy 3)
ALTER TABLE labor_law_sources 
ADD COLUMN IF NOT EXISTS reference VARCHAR(50);

-- Add year column to preserve enactment year
ALTER TABLE labor_law_sources 
ADD COLUMN IF NOT EXISTS year INT;

-- Create index on reference for fast "PD 851", "RA 11058" lookups
CREATE INDEX IF NOT EXISTS idx_sources_reference 
ON labor_law_sources(reference);

COMMENT ON COLUMN labor_law_sources.reference IS 'Short reference code (e.g., PD 851, RA 11058) for fast lookup';
COMMENT ON COLUMN labor_law_sources.year IS 'Year the law was enacted or published';

-- ============================================================
-- ADD MISSING COLUMNS TO labor_law_sections
-- ============================================================

-- Add semantic_type column for document categorization
ALTER TABLE labor_law_sections 
ADD COLUMN IF NOT EXISTS semantic_type VARCHAR(50);

-- Add section_number for complete hierarchy
ALTER TABLE labor_law_sections 
ADD COLUMN IF NOT EXISTS section_number INT;

COMMENT ON COLUMN labor_law_sections.semantic_type IS 'Document semantic type: decree, statute, rules, provisions, etc.';
COMMENT ON COLUMN labor_law_sections.section_number IS 'Numeric section number for ordering (optional)';

-- ============================================================
-- DATA MIGRATION (Optional)
-- ============================================================

-- Extract reference from existing source titles if not populated
-- Example: "Presidential Decree No. 851" → "PD 851"
UPDATE labor_law_sources
SET reference = CASE
  WHEN title ~ 'Presidential Decree\s+(?:No\.)?\s*(\d+)' 
    THEN 'PD ' || (regexp_match(title, 'Presidential Decree\s+(?:No\.)?\s*(\d+)'))[1]
  WHEN title ~ 'Republic Act\s+(?:No\.)?\s*(\d+)'
    THEN 'RA ' || (regexp_match(title, 'Republic Act\s+(?:No\.)?\s*(\d+)'))[1]
  WHEN title ~ 'Department Order\s+(?:No\.)?\s*([\d-]+)'
    THEN 'DO ' || (regexp_match(title, 'Department Order\s+(?:No\.)?\s*([\d-]+)'))[1]
  ELSE NULL
END
WHERE reference IS NULL;

-- ============================================================
-- VALIDATION QUERIES
-- ============================================================

-- Verify new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'labor_law_sources'
  AND column_name IN ('reference', 'year')
ORDER BY column_name;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'labor_law_sections'
  AND column_name IN ('semantic_type', 'section_number')
ORDER BY column_name;

-- Verify index was created
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'labor_law_sources'
  AND indexname = 'idx_sources_reference';

-- Sample query to test fast reference lookup (Strategy 3)
SELECT id, reference, title, url
FROM labor_law_sources
WHERE reference ILIKE 'PD 851%';
