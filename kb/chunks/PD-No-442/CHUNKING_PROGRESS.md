# PD-No-442 Chunking Progress

⚠️ **STRATEGY REVISION IN PROGRESS** ⚠️

**Document**: Presidential Decree No. 442 (Labor Code)  
**Size**: 41,163 words, 2,059 lines, ~300 articles  
**Original Strategy**: Chunk by Books and major Titles (15 chunks) - ❌ **DEPRECATED**  
**New Strategy**: Article-by-article storage with conditional chunking - ✅ **RECOMMENDED**

**📋 See**: `ANALYSIS_AND_RECOMMENDATION.md` for complete analysis and implementation plan

## Structure Overview

- **Preliminary Title** (lines 1-39): Tenant Emancipation
- **Book One** (lines 40-271): Pre-Employment
- **Book Two** (lines 272-470): Human Resources Development
- **Book Three** (lines 471-921): Conditions of Employment  
- **Book Four** (lines 922-1272): Health, Safety & Social Welfare
- **Book Five** (lines 1273-1946): Labor Relations
- **Book Six** (lines 1947-1999): Post-Employment
- **Book Seven** (lines 2000-2059): Penal/Final Provisions

## Chunking Plan

| # | Chunk ID | Lines | Articles | Status | Keywords |
|---|----------|-------|----------|--------|----------|
| 00 | preliminary-title-preamble | 1-39 | Art 7-11 | ✅ DONE | tenant, land reform, agrarian |
| 01 | book1-recruitment-placement | 40-254 | Art 12-39 | ✅ DONE | recruitment, OEDB, overseas employment |
| 02 | book1-training-development | 255-271 | Art 40-62 | ⏳ TODO | vocational training, apprenticeship |
| 03 | book2-training-skills | 272-470 | Art 63-93 | ⏳ TODO | human resources, skills development |
| 04 | book3-employment-terms | 471-650 | Art 94-150 | ⏳ TODO | wages, hours of work, employment of women |
| 05 | book3-special-groups | 651-787 | Art 151-187 | ⏳ TODO | minors, househelpers, homeworkers |
| 06 | book3-working-conditions | 788-921 | Art 188-210 | ⏳ TODO | working conditions, medical care |
| 07 | book4-health-safety | 922-1100 | Art 211-242 | ⏳ TODO | occupational health, safety standards |
| 08 | book4-employees-compensation | 1101-1272 | Art 243-271 | ⏳ TODO | workmen's compensation, ECC |
| 09 | book5-labor-relations-1 | 1273-1600 | Art 272-300 | ⏳ TODO | unions, collective bargaining |
| 10 | book5-labor-relations-2 | 1601-1800 | Art 301-330 | ⏳ TODO | strikes, lockouts, arbitration |
| 11 | book5-labor-relations-3 | 1801-1946 | Art 331-360 | ⏳ TODO | unfair labor practices, NLRC |
| 12 | book6-termination | 1947-1992 | Art 278-286 | ⏳ TODO | security of tenure, termination |
| 13 | book6-retirement | 1993-1999 | Art 287 | ⏳ TODO | retirement benefits |
| 14 | book7-penalties-final | 2000-2059 | Art 288-302 | ⏳ TODO | penalties, prescriptions, transitional |

## Current Status: PAUSED

⏸️ **Manual chunking work has been PAUSED pending schema migration.**

### Issues Identified

1. **Guideline Violation**: Chunks 00-01 violate 200-800 word guideline
   - Chunk 00: 581 words (acceptable)
   - Chunk 01: 3,662 words (458% over maximum!)
   - Planned chunks: Average 2,744 words (343% over maximum)

2. **Architectural Misalignment**: Current approach doesn't align with ADR-002 design
   - Should store individual articles (~300 articles)
   - Should use `labor_law_sections` table with hierarchical metadata
   - Should only use `labor_law_chunks` for articles > 1000 words
   - Current schema lacks required tables and indexes

3. **Missing Multi-Strategy Support**: Current database schema doesn't support:
   - Direct article lookup (Strategy 3)
   - Keyword-based full-text search (Strategy 1)
   - Hierarchical navigation (Book → Title → Article)

### Next Steps

1. ✅ **Analysis Complete**: See `ANALYSIS_AND_RECOMMENDATION.md`
2. ⏳ **Build Article Parser**: Parse ~300 articles from PD-442.txt
3. ⏳ **LLM Pipeline**: Generate summaries and extract keywords
4. ⏳ **Batch Ingestion**: Insert into `labor_law_sections` table
5. ⏳ **Conditional Chunking**: Only for articles > 1000 words

**Timeline**: 3-4 days | **Cost**: < $0.03

---

## Old Chunking Plan (DEPRECATED)

This plan is being replaced with article-by-article storage.

| # | Chunk ID | Lines | Articles | Status | Notes |
|---|----------|-------|----------|--------|-------|
| 00 | preliminary-title-preamble | 1-39 | Art 7-11 | ⚠️ DEPRECATED | 581 words - within range but using wrong approach |
| 01 | book1-recruitment-placement | 40-254 | Art 12-39 | ⚠️ DEPRECATED | 3,662 words - far exceeds 800 word maximum |
| 02-14 | (remaining chunks) | - | - | ❌ CANCELLED | See new approach below |

---

## New Approach: Article-Based Storage

### Recommended Strategy

**Store each article individually** in `labor_law_sections` table:
- ~300 articles total
- Average 137 words per article (most are 50-200 words)
- Full text + LLM-generated summary + keywords
- Hierarchical metadata (Book, Title, Chapter, Article)
- Only chunk if individual article > 1000 words (rare: ~5-10 articles)

### Implementation Plan

1. **Database Schema Migration** (1 day)
   - Create `labor_law_sources` table
   - Create `labor_law_sections` table
   - Create `labor_law_chunks` table (conditional use)
   - Add indexes: GIN (full-text), HNSW (vector), B-tree (article_number)

2. **Article Parser Development** (1-2 days)
   - Regex-based extraction of individual articles
   - Hierarchical metadata extraction
   - Validation with expected article count (~300)

3. **LLM Pipeline** (1 day)
   - Batch summary generation (GPT-4o-mini)
   - Keyword extraction (NER + TF-IDF)
   - Embedding generation (text-embedding-3-small)

4. **Batch Ingestion** (0.5 day)
   - Insert into `labor_law_sections`
   - Conditional chunking for >1000 word articles
   - Validation and testing

**Total Timeline**: 4.5-5.5 days  
**Total Cost**: < $0.03

### Benefits

- ✅ Aligns with ADR-002 multi-strategy retrieval architecture
- ✅ Enables direct article lookup (Strategy 3)
- ✅ Supports keyword-based search (Strategy 1)
- ✅ Preserves article-level granularity
- ✅ Better citation precision
- ✅ Easier maintenance

---

## References

- **Analysis & Recommendation**: `ANALYSIS_AND_RECOMMENDATION.md` (THIS DOCUMENT)
- **Database Schema**: `infra/supabase/schema_complete.sql` (already implemented ✅)
- **Architecture**: `docs/adr/002-rag-pipeline-limitations-and-future-architecture.md`

---

## Archive

Existing chunks 00-01 preserved for reference but will be replaced with article-based storage.

1. ✅ Complete chunks 00-01 (Preliminary + Book 1 Title I)
2. ⏳ Continue with Book 1 Title II (lines 255-271)
3. ⏳ Chunk Book 2 (lines 272-470)
4. ⏳ Chunk Book 3 in 3 parts (lines 471-921)
5. ⏳ Continue with remaining books

## Notes

- Large complex document requiring strategic chunking
- Each Book has multiple Titles - group by semantic similarity
- Keep chunks 500-1000 words for manageability
- Total estimated: 15 chunks (may adjust as needed)
