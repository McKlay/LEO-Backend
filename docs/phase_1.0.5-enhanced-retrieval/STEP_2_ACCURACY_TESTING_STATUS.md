# Phase 1.0.5 - Step 2: Accuracy Testing Implementation

**Status**: ⚠️ IN PROGRESS - BLOCKED BY SCHEMA ISSUES  
**Date**: 2025-11-20  
**Time Investment**: ~2 hours  

---

## Summary

Created comprehensive accuracy testing infrastructure with 18 test queries across 5 categories. Testing is **blocked** by SQL schema mismatches in multiple retrieval methods that need to be fixed.

---

## What Was Built

### 1. Test Infrastructure

**Test Query Set** (`tests/data/accuracy_test_queries.json`):
- 3 Direct Article queries (Article lookup)
- 4 Specific Calculation queries (Formulas, rates)
- 5 Concept/Topic queries (Broad questions)
- 4 Vague/Clarification queries (Intentionally ambiguous)
- 2 Multi-turn conversation sequences (6 total turns)

**Total**: 18 unique test scenarios, 22 total test executions

**Test Script** (`scripts/test_accuracy.py`):
- Automated execution of all test queries
- Response evaluation against expected criteria
- Metrics tracking (latency, citations, accuracy)
- Detailed reporting with pass/fail per category
- JSON output for analysis

### 2. Database Investigation

**Created** (`scripts/check_database.py`):
- Real-time database inventory checker
- Shows actual data ingested

**Current Database State**:
```
✓ labor_law_sections: 26 rows
✓ labor_law_chunks: 4 rows
✓ labor_law_sources: 10 rows
```

**Key Finding**: Very few documents are actually chunked (only 4 chunks total). Most data is in sections table as full articles.

### 3. Integration Test Updates

**Created** (`scripts/test_dual_table_integration.py`):
- Tests dual-table retrieval with real data
- Validates deduplication logic
- Checks ranking algorithm
- Tests with ingested documents (PD-851, RA-10362, Labor Code)

---

## Critical Issues Found

### Issue 1: SQL Schema Mismatches 🔴 **BLOCKER**

Multiple query methods are using wrong column names for `labor_law_sections` table:

**Problem**: Code references `content` but table has `full_text`

**Affected Methods**:
1. `direct_article_lookup()` - Line 632 in supabase_store.py
2. `keyword_search()` - Line 556 in supabase_store.py  
3. `_query_sections_table()` - (already fixed)
4. Possibly more in semantic search paths

**Impact**: All retrieval strategies failing, making accuracy testing impossible

**Root Cause**: Schema evolved from Phase 1.0 to 1.0.5 but query code wasn't updated consistently

### Issue 2: Metadata Structure Mismatch

**Problem**: `labor_law_sections` doesn't have a `metadata` JSONB column  
**Impact**: Direct lookup and keyword search try to select non-existent column

**Actual Schema**:
```sql
CREATE TABLE labor_law_sections (
    id UUID PRIMARY KEY,
    source_id UUID,
    article_number VARCHAR(50),
    article_title TEXT,
    full_text TEXT NOT NULL,      -- NOT "content"
    summary TEXT,
    keywords TEXT[],
    -- NO "metadata" column
    book VARCHAR(100),
    title_name VARCHAR(200),
    chapter VARCHAR(100),
    -- ... other columns
)
```

---

## Required Fixes

### Fix 1: Update `direct_article_lookup()` 

**File**: `adapters/vectorstore/supabase_store.py`  
**Line**: ~632

**Current** (WRONG):
```sql
SELECT id, content, metadata
FROM labor_law_sections
WHERE article_number ILIKE %s
```

**Should be**:
```sql
SELECT id, full_text, article_number, article_title, book, title_name, chapter
FROM labor_law_sections  
WHERE article_number ILIKE %s
```

### Fix 2: Update `keyword_search()`

**File**: `adapters/vectorstore/supabase_store.py`  
**Line**: ~556

**Current** (WRONG):
```sql
SELECT 
    id,
    content,
    metadata,
    ts_rank(to_tsvector('english', content), query) as rank
FROM labor_law_sections
```

**Should be**:
```sql
SELECT 
    id,
    full_text as content,
    article_number,
    article_title,
    ts_rank(to_tsvector('english', full_text), query) as rank
FROM labor_law_sections
```

### Fix 3: Update QueryResult Construction

**Impact**: Every place that builds `QueryResult` from `labor_law_sections` needs metadata constructed from individual columns, not from a `metadata` JSONB field.

**Pattern to use**:
```python
metadata = {
    'article_number': row['article_number'],
    'article_title': row['article_title'],
    'book': row['book'],
    'title_name': row['title_name'],
    'chapter': row['chapter'],
    '_source_table': 'sections'
}
```

---

## Test Results (Blocked)

**Status**: Cannot complete accuracy testing until schema fixes applied

**Last Run**:
```
Total Tests: 22
Passed: 0
Failed: 22  
Accuracy: 0.0% (all failed due to SQL errors)
```

**Errors**: All tests failing with `column "content" does not exist`

---

## Next Steps

### Immediate (Unblock Testing)

1. **Fix SQL queries** in `supabase_store.py`:
   - [ ] `direct_article_lookup()` - use `full_text` not `content`
   - [ ] `keyword_search()` - use `full_text` not `content`
   - [ ] `_query_sections_table()` - ✅ already fixed in Step 1
   - [ ] `query()` method - verify uses correct columns
   - [ ] Any other methods querying `labor_law_sections`

2. **Fix metadata construction**:
   - [ ] Build metadata dict from individual columns
   - [ ] Update all `QueryResult` creation points
   - [ ] Ensure consistent metadata structure across all retrieval paths

3. **Restart backend** with fixes applied

4. **Run accuracy tests** again:
   ```bash
   chcp 65001
   python scripts/test_accuracy.py
   ```

### After Unblocking

5. **Analyze results**:
   - Review pass/fail by category
   - Identify systematic issues
   - Adjust expected values if needed

6. **Iterate on failures**:
   - Fix retrieval logic if citation counts low
   - Adjust ranking if wrong results prioritized
   - Tune clarification detection if false positives

7. **Document findings** in `STEP_2_ACCURACY_TESTING.md`

---

## Files Created

```
tests/data/accuracy_test_queries.json       +190 lines (NEW)
scripts/test_accuracy.py                    +360 lines (NEW)
scripts/test_dual_table_integration.py      +230 lines (NEW)
scripts/check_database.py                   +85 lines (NEW)
```

---

## Files Needing Updates

```
adapters/vectorstore/supabase_store.py
  - direct_article_lookup()   (line ~632)
  - keyword_search()          (line ~556)
  - query()                   (line ~400, verify)
  - Any other methods querying labor_law_sections
```

---

## Estimated Time to Unblock

- **SQL fixes**: 30-45 minutes
- **Testing after fixes**: 1 hour
- **Analysis & iteration**: 1-2 hours
- **Total**: 2.5-4 hours to complete Step 2

---

## Lessons Learned

1. **Schema evolution requires grep**: When DB schema changes, need to grep entire codebase for old column names
2. **Integration tests critical**: Unit tests with mocks don't catch schema mismatches
3. **Test early with real data**: Would have caught these issues sooner if tested Step 1 with live backend
4. **Document schema changes**: Need ADR or migration guide when columns renamed

---

## Recommendations

### Short-term

1. Fix SQL queries to match actual schema (highest priority)
2. Add schema validation tests (check actual DB columns match code expectations)
3. Run full test suite with live backend before declaring step complete

### Long-term

1. Consider migration script to add `metadata` JSONB column for backwards compatibility
2. Add database schema documentation to `/docs/database/`
3. Create schema change checklist for future updates
4. Add integration test to CI/CD that runs against real Supabase instance

---

**Status**: Ready for SQL fixes  
**Blocker**: Schema mismatch in retrieval queries  
**Next Action**: Update `supabase_store.py` with correct column names
