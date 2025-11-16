# Manual Chunking Architecture

## Overview

**Decision**: Shift from LLM-based automatic chunking to **manual chunking with automated ingestion**.

**Rationale**:
- Legal content requires human verification for accuracy
- Hierarchical structure is complex and context-dependent
- Incremental updates: change only specific chunks when laws are amended
- Version control: Git-trackable changes to legal content
- No LLM hallucination risk
- Full transparency and control

## New Folder Structure

```
kb/
├── docs/                           # Raw source documents (keep for reference)
│   ├── PD-No-442.txt
│   ├── PD-No-851.txt
│   └── ...
│
├── chunks/                         # NEW: Manually chunked content
│   ├── PD-No-851/                 # One folder per document
│   │   ├── metadata.json          # Document-level metadata
│   │   ├── 01-decree-preamble.md  # Hierarchical chunk files
│   │   ├── 02-decree-sec1-3.md
│   │   ├── 03-rules-preamble.md
│   │   ├── 04-rules-sec1-2.md
│   │   ├── 05-supplementary.md
│   │   └── ...
│   │
│   ├── PD-No-442/                 # Labor Code chunks
│   │   ├── metadata.json
│   │   ├── book1/
│   │   │   ├── 01-pre-employment.md
│   │   │   ├── 02-recruitment.md
│   │   │   └── ...
│   │   ├── book2/
│   │   │   └── ...
│   │   └── ...
│   │
│   └── RA-No-11058/
│       ├── metadata.json
│       ├── 01-title-definitions.md
│       └── ...
│
└── ingest/
    ├── loaders/
    │   └── manual_chunk_loader.py  # NEW: Load manually chunked files
    ├── sync_to_vectorstore.py      # MODIFIED: Support manual chunks
    └── ...
```

## Chunk File Format

### metadata.json (per document)
```json
{
  "source": "Presidential Decree No. 851",
  "reference": "PD 851",
  "short_name": "13th Month Pay Law",
  "doc_type": "statute",
  "year": "1975",
  "url": "https://lawphil.net/statutes/presdecs/pd1975/pd_851_1975.html",
  "chunking_strategy": "manual",
  "total_chunks": 5,
  "last_updated": "2024-11-13",
  "notes": "Manually chunked to preserve hierarchical structure"
}
```

### Individual Chunk File (Markdown)
```markdown
---
chunk_id: pd851_decree_preamble
title: Presidential Decree No. 851 - Main Decree and Sections 1-3
article_number: pd851_decree_sec1_3
semantic_type: decree
hierarchy:
  part: Main Decree
  sections: Preamble + Sections 1-3
keywords:
  - 13th month pay
  - employer obligation
  - payment schedule
has_table: false
has_formula: true
has_list: true
---

# Presidential Decree No. 851

REQUIRING ALL EMPLOYERS TO PAY THEIR EMPLOYEES A 13TH MONTH PAY

WHEREAS, the practice of paying employees a 13th-month pay...

## Section 1
All employers are hereby required to pay all their rank-and-file employees...

## Section 2
The 13th-month pay shall be computed as follows...

## Section 3
The 13th-month pay shall be paid not later than December 24 of every year...
```

## Ingestion Workflow

### 1. Manual Chunking Process (Human)
```
1. Read full legal document
2. Identify natural semantic boundaries
3. Create folder under kb/chunks/{document-name}/
4. Create metadata.json
5. Split into .md files with YAML frontmatter
6. Organize hierarchically (folders for books/titles if needed)
7. Commit to Git
```

### 2. Automated Ingestion (Script)
```
python -m kb.ingest.sync_to_vectorstore --manual --folder kb/chunks/PD-No-851
python -m kb.ingest.sync_to_vectorstore --manual --all  # Ingest all manual chunks
python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-851/02-decree-sec1-3.md  # Single chunk
```

### 3. Incremental Updates
```
# User edits kb/chunks/PD-No-851/02-decree-sec1-3.md
# Then re-ingest only that chunk:
python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-851/02-decree-sec1-3.md --force
```

## Technical Implementation

### Modified Files

1. **kb/ingest/loaders/manual_chunk_loader.py** (NEW)
   - Parse YAML frontmatter + Markdown content
   - Load metadata.json
   - Return structured Chunk objects

2. **kb/ingest/sync_to_vectorstore.py** (MODIFIED)
   - Add `--manual` flag
   - Add `--folder` option for chunk directories
   - Use ManualChunkLoader instead of LLMDrivenChunker
   - Support single-file ingestion from chunks folder

3. **kb/ingest/incremental_tracker.py** (MODIFIED)
   - Track chunk file hashes (not raw document hashes)
   - Support folder-based tracking
   - Detect changes in individual .md files

4. **scripts/database_ingestion/** (NEW FOLDER)
   - Migration scripts
   - Validation scripts
   - Chunk quality checkers

### Database Schema (No Changes)
```sql
-- labor_law_sections table remains the same
-- Just ingest manually chunked content instead of LLM chunks
```

## Benefits

✅ **Accuracy**: 100% accurate - human-verified chunks  
✅ **Control**: Full visibility into what goes into database  
✅ **Incremental**: Update only changed chunks  
✅ **Version Control**: Git tracks all chunk changes  
✅ **No LLM Costs**: No GPT-4o API calls for chunking  
✅ **Hierarchy**: Natural legal document structure preserved  
✅ **Debugging**: Easy to identify problematic chunks  
✅ **Compliance**: Human oversight ensures legal accuracy  

## Migration Plan

### Phase 1: Infrastructure (Day 1)
- [ ] Create kb/chunks/ directory structure
- [ ] Write ManualChunkLoader
- [ ] Modify sync_to_vectorstore.py to support --manual flag
- [ ] Update incremental_tracker.py

### Phase 2: Initial Chunking (Day 2-3)
- [ ] Manually chunk PD-No-851 (5 chunks) - PILOT
- [ ] Test ingestion pipeline
- [ ] Validate database records
- [ ] Document chunking guidelines

### Phase 3: Full Migration (Day 4-5)
- [ ] Manually chunk remaining 9 documents
- [ ] Ingest all manual chunks
- [ ] Verify accuracy vs old LLM chunks
- [ ] Update documentation

### Phase 4: Cleanup (Day 6)
- [ ] Archive LLM chunking code (keep for reference)
- [ ] Update API documentation
- [ ] Add chunk quality validation scripts
- [ ] Create chunking guidelines for future documents

## Example: PD-No-851 Manual Chunking

Based on previous analysis, here's the correct structure:

```
kb/chunks/PD-No-851/
├── metadata.json
├── 01-decree-preamble-and-sections.md      # Main decree + Sections 1-3
├── 02-implementing-rules-preamble.md       # Rules preamble + Sections 1-2
├── 03-implementing-rules-sections.md       # Rules Sections 3-8
├── 04-supplementary-rules-preamble.md      # Supplementary preamble + Sections 1-2
└── 05-supplementary-rules-sections.md      # Supplementary Sections 3-11
```

This gives us **5 semantically complete chunks** that preserve hierarchy.

## Rollback Plan

If manual chunking proves impractical:
- LLM chunking code remains in repo (archived, not deleted)
- Can revert to automatic chunking with improved prompts
- Manual chunks can be used as training data for LLM

## Success Criteria

1. ✅ 100% chunking accuracy (human-verified)
2. ✅ Complete document coverage (no omissions)
3. ✅ Correct hierarchical structure
4. ✅ Incremental update capability
5. ✅ Version control for all chunks
6. ✅ <5 minutes per document for manual chunking (after practice)
