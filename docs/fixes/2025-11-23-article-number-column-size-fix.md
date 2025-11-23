# Fix: Article Number Column Size Issue

**Date:** November 23, 2025  
**Issue:** Ingestion failed with database constraint error  
**Status:** ✅ Resolved

## Problem

During DOLE Handbook ingestion, the process failed with the following error:

```
APIError: {'message': 'value too long for type character varying(50)', 'code': '22001'}
```

### Root Cause

The `article_number` column in the `labor_law_sections` table was defined as `VARCHAR(50)`, but some chunk identifiers exceeded this limit:

- `dole_handbook_2023_leave_benefits_vawc_special_women` (53 characters) ❌
- `dole_handbook_2023_government_benefits_philhealth` (50 characters) ⚠️ (exactly at limit)
- Other chunks were approaching the limit

The issue was that long descriptive identifiers for DOLE Handbook sections naturally exceeded the 50-character constraint.

## Solution

### 1. Database Schema Migration

Created migration: `infra/supabase/migrations/001_increase_article_number_size.sql`

```sql
-- Increase article_number from VARCHAR(50) to VARCHAR(255)
ALTER TABLE labor_law_sections 
ALTER COLUMN article_number TYPE VARCHAR(255);
```

### 2. Updated Schema Definition

Modified `infra/supabase/schema.sql`:

```sql
article_number VARCHAR(255),  -- 'Article 123', 'Section 5', 'PD 442', etc. 
                              -- (increased from 50 to support longer chunk IDs)
```

### 3. Applied Migration

Executed the migration directly against Supabase database:

```bash
python -c "import psycopg2; ..."
```

Verification confirmed:
- Column type: `character varying`
- Character maximum length: `255`

## Results

✅ **Successful ingestion of DOLE Handbook:**
- 15 chunks ingested successfully
- 33 sub-chunks auto-generated for oversized articles (>1000 words)
- Total tokens: 32,757
- All files tracked in ingestion history

### Ingestion Summary

```
✓ Successfully ingested 15 manual chunks: 32757 tokens
✓ Auto-chunked 33 sub-chunks into labor_law_chunks table
✓ Recorded ingestion history for 15 files in DOLE-Handbook
```

## Files Modified

1. `infra/supabase/migrations/001_increase_article_number_size.sql` (created)
2. `infra/supabase/schema.sql` (updated)

## Testing

- ✅ Migration applied without errors
- ✅ Full DOLE Handbook ingestion successful
- ✅ All chunks with long identifiers ingested correctly
- ✅ Auto-chunking working for oversized articles
- ✅ Incremental tracking recording all files

## Recommendations

1. **For Future Schemas:** Consider using `VARCHAR(255)` or `TEXT` for identifier columns that may contain descriptive names
2. **Validation:** Add pre-ingestion validation to check field lengths before database insertion
3. **Documentation:** Update KB chunking guidelines to note the 255-character limit for article_number identifiers

## Related Files

- Ingestion script: `scripts/ingestion/ingest_manual.py`
- Vector store adapter: `adapters/vectorstore/supabase_store.py`
- Sync module: `kb/ingest/sync_to_vectorstore.py`
- Schema: `infra/supabase/schema.sql`
