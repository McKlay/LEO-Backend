# LEO Backend - Quick Reference Guide

**Last Updated:** November 18, 2025  
**Status:** Production Ready ✅

---

## Quick Start Commands

### Check System Status
```powershell
# Check ingestion status
python scripts/check_ingestion_status.py

# Check database schema
python scripts/check_schema.py

# Check recent ingestions
python scripts/check_recent_chunks.py
```

### Validate Before Ingesting
```powershell
# Validate specific document chunks
python scripts/ingestion/validate_chunks.py --document PD-No-442

# Verify single chunk file
python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-442/01-book1-article12-objectives.md

# List all available documents
python scripts/ingestion/list_documents.py
```

### Ingest Documents
```powershell
# DRY RUN first (always recommended)
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442 --dry-run

# Ingest single file
python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/PD-No-442/01-book1-article12-objectives.md

# Ingest entire folder
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442

# Force re-ingestion
python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442 --force
```

### Test Commands
```powershell
# Test all CLI commands
python scripts/ingestion/test_all_cli.py

# Test single chunk ingestion with database verification
python scripts/ingestion/test_single_ingestion.py
```

---

## Directory Structure

```
scripts/
├── Essential Utilities
│   ├── check_ingestion_status.py    ⭐ Main status checker
│   ├── check_schema.py               📊 Database schema inspector
│   ├── check_recent_chunks.py        🔍 Recent ingestion viewer
│   ├── quick_db_check.py             ✅ Quick health check
│   └── verify_pd442_ingestion.py     📋 PD-442 verification
│
└── ingestion/                         📁 Ingestion workflow scripts
    ├── README.md                      📖 Comprehensive guide
    ├── test_all_cli.py                🧪 CLI test suite
    ├── test_single_ingestion.py       🧪 DB verification test
    ├── validate_chunks.py             ✓ Validate chunks
    ├── verify_chunk.py                ✓ Verify single chunk
    ├── ingest_manual.py               ⬆️ Manual ingestion
    ├── check_ingestion.py             📊 Check status
    ├── list_documents.py              📋 List documents
    ├── create_template.py             ➕ Create template
    └── cleanup_duplicates.py          🧹 Clean duplicates
```

---

## Common Workflows

### 1. Adding a New Document

```powershell
# Step 1: Create chunk files in kb/chunks/[DOC-NAME]/

# Step 2: Validate chunks
python scripts/ingestion/validate_chunks.py --document [DOC-NAME]

# Step 3: Dry run
python -m kb.ingest.sync_to_vectorstore --manual --folder [DOC-NAME] --dry-run

# Step 4: Ingest
python -m kb.ingest.sync_to_vectorstore --manual --folder [DOC-NAME]

# Step 5: Verify
python scripts/ingestion/check_ingestion.py --document [DOC-NAME]
```

### 2. Updating an Existing Chunk

```powershell
# Step 1: Edit the chunk file in kb/chunks/

# Step 2: Verify the chunk
python scripts/ingestion/verify_chunk.py kb/chunks/[DOC-NAME]/[CHUNK-FILE]

# Step 3: Re-ingest with force
python -m kb.ingest.sync_to_vectorstore --manual --file kb/chunks/[DOC-NAME]/[CHUNK-FILE] --force
```

### 3. Checking Ingestion Health

```powershell
# Quick status
python scripts/check_ingestion_status.py

# Detailed document status
python scripts/ingestion/list_documents.py

# Specific document check
python scripts/ingestion/check_ingestion.py --document PD-No-442

# Recent ingestions
python scripts/check_recent_chunks.py
```

### 4. Running Tests

```powershell
# Test all CLI commands
python scripts/ingestion/test_all_cli.py

# Test database column population
python scripts/ingestion/test_single_ingestion.py

# Verify PD-442 specifically
python scripts/verify_pd442_ingestion.py
```

---

## Database Schema Reference

### Key Tables

#### labor_law_sections
```sql
- id (uuid)
- source_id (uuid)
- article_number (varchar)       ⭐ For direct lookup
- article_title (text)
- full_text (text)                ⭐ For keyword search
- summary (text)
- keywords (text[])               ⭐ For keyword retrieval
- metadata (jsonb)                ⭐ Contains file_stem, chunk_id, etc.
- semantic_type (varchar)         ⭐ For filtering (decree, statute, etc.)
- section_number (integer)
- embedding (vector(1536))        ⭐ For semantic search
- created_at (timestamptz)
- updated_at (timestamptz)
```

#### ingestion_history
```sql
- id (uuid)
- file_name (varchar)
- file_path (text)
- file_hash (varchar)
- chunk_count (int)
- token_count (int)
- ingestion_method (varchar)
- status (varchar)
- error_message (text)
- created_at (timestamptz)
- updated_at (timestamptz)
```

### Important Metadata Fields (JSONB)
```json
{
  "file_stem": "01-decree-main",           // Source file identifier
  "chunk_id": "pd851_decree_main",         // Unique chunk ID
  "source_document": "PD 851",             // Short reference
  "doc_type": "statute",                   // Document type
  "url": "https://...",                    // Canonical URL
  "short_name": "PD 851",                  // Display name
  "keywords": ["13th month pay", ...],     // Searchable keywords
  "hierarchy": { ... }                     // Document structure
}
```

---

## Current System State

### Documents Available
- ✅ **PD-No-442** (Labor Code) - 65 chunks ready
- ✅ **PD-No-851** (13th Month Pay) - 5 chunks ready
- ⏳ **8 other documents** - Not yet chunked

### Currently Ingested (Test Data)
- **PD-442**: 1 chunk (preliminary title)
- **PD-851**: 1 chunk (main decree)
- **Total**: 2 test chunks

### Ready for Production
- ✅ CLI commands tested and working
- ✅ Database columns verified
- ✅ Ingestion pipeline stable
- ✅ Smart retrieval ready
- ✅ All dangerous scripts removed

---

## Troubleshooting

### Issue: Chunk not appearing in database
```powershell
# Check if chunk file is valid
python scripts/ingestion/verify_chunk.py [CHUNK-FILE]

# Check database directly
python scripts/check_recent_chunks.py

# Try force re-ingestion
python -m kb.ingest.sync_to_vectorstore --manual --file [CHUNK-FILE] --force
```

### Issue: Unicode/encoding errors
- All scripts now have UTF-8 encoding fixes for Windows
- If errors persist, check that file is saved as UTF-8

### Issue: Slow commands
- Some commands (like check_ingestion.py) are slow for large documents
- This is expected - they're checking all chunks
- Use --dry-run for faster validation

---

## Safety Reminders

⚠️ **NEVER** manually delete data from `labor_law_sections` table  
⚠️ **ALWAYS** use `--dry-run` first when ingesting  
⚠️ **ALWAYS** validate chunks before ingesting  
⚠️ **BACKUP** database before major operations  

✅ **DO** use the provided test scripts  
✅ **DO** check ingestion status regularly  
✅ **DO** keep chunk files under version control  

---

## Next Steps

1. **Ingest Full PD-442** (when ready)
   ```powershell
   python -m kb.ingest.sync_to_vectorstore --manual --folder PD-No-442 --force
   ```

2. **Test Smart Retrieval**
   - Use the verified data for testing parallel retrieval strategies
   - All columns are properly populated

3. **Continue Chunking**
   - 8 more documents need manual chunking
   - Use PD-442 and PD-851 as templates

---

## Support & Documentation

- **Full Cleanup Report**: `docs/CLI_CLEANUP_COMPLETION_REPORT.md`
- **Ingestion Guide**: `scripts/ingestion/README.md`
- **API Specs**: `docs/BACKEND_API_SPECIFICATIONS.md`
- **Architecture**: `docs/PHASE_1C_ARCHITECTURE_CURRENT_STATE.md`

---

**Questions?** Check the documentation or run scripts with `--help` flag.
