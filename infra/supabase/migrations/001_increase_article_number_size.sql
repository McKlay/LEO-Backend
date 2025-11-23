-- Migration: Increase article_number column size
-- Date: 2025-11-23
-- Reason: DOLE Handbook chunks have article_number values exceeding VARCHAR(50)
-- Example: "dole_handbook_2023_leave_benefits_vawc_special_women" (53 chars)

-- Increase article_number from VARCHAR(50) to VARCHAR(255)
-- This accommodates longer identifiers while maintaining index efficiency
ALTER TABLE labor_law_sections 
ALTER COLUMN article_number TYPE VARCHAR(255);

-- No need to recreate indexes - they will automatically adjust
-- Verify the change
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'labor_law_sections' 
  AND column_name = 'article_number';
