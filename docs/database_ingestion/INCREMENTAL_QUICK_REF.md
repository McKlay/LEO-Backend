# Incremental Ingestion - Quick Reference

## Fixed Issues

### Before ❌
1. `--force` on single file deleted ALL chunks from that document folder
2. Folder ingestion would skip all files if one was unchanged

### After ✅
1. `--force` on single file only re-ingests that specific file
2. Folder ingestion processes only new/changed files, skips unchanged

## Commands

### Ingest Single File (Force)
```powershell
# Only re-ingests this one file
python scripts/ingestion/ingest_manual.py `
    --file kb/chunks/PD-No-851/01-decree-main.md `
    --force
```

### Ingest Folder (Incremental)
```powershell
# Only processes new/changed files
python scripts/ingestion/ingest_manual.py --folder PD-No-851
```

### Ingest All Documents (Incremental)
```powershell
# Tracks each file individually
python scripts/ingestion/ingest_manual.py --all
```

### Force Re-ingest Entire Folder
```powershell
# Re-processes all files in folder
python scripts/ingestion/ingest_manual.py --folder PD-No-851 --force
```

## Verification

```powershell
# Quick verification test
python scripts/verify_incremental.py

# Check what's ingested
python scripts/check_ingestion_status.py

# Check specific document
python scripts/check_ingestion_status.py --document PD-No-851
```

## How It Works

### File-Level Tracking
- Each chunk file (`*.md`) is tracked individually
- SHA-256 hash detects file changes
- Ingestion history stored in `ingestion_history` table

### Smart Deletion
- Only deletes chunks from files being re-ingested
- Uses `article_number` for precise targeting
- Preserves all other chunks in the document

### Incremental Detection
- Compares file hash with last ingestion
- Skips if unchanged
- Processes if new or modified

## Troubleshooting

### All files skipped unexpectedly
```powershell
# Check ingestion history
python scripts/check_ingestion_status.py

# Force re-ingest if needed
python scripts/ingestion/ingest_manual.py --folder <name> --force
```

### Want to see what would be ingested
```powershell
# Dry run mode
python scripts/ingestion/ingest_manual.py --folder <name> --dry-run
```

### Reset ingestion history
```sql
-- Clear history for specific file
DELETE FROM ingestion_history WHERE file_name = '01-decree-main.md';

-- Clear all history (use with caution!)
TRUNCATE TABLE ingestion_history;
```

## Key Changes

### 1. ManualChunk Enhancement
Added `document_name` field to track source folder:
```python
chunk.document_name  # e.g., "PD-No-851"
chunk.file_stem      # e.g., "01-decree-main"
```

### 2. Granular Deletion
Changed from deleting entire document to specific chunks:
```python
# Before: delete all chunks for source_id
await vectorstore.delete_by_source_id(source_id)

# After: delete only specific chunks
await vectorstore.delete_by_article_numbers(article_numbers)
```

### 3. Improved Filtering
Now handles all modes with file-level granularity:
- ✅ Single file mode
- ✅ Specific folder mode
- ✅ All documents mode

## Benefits

- **Precision**: Only affects files you're actually changing
- **Safety**: No accidental deletions of unrelated content
- **Efficiency**: Skips processing unchanged files
- **Transparency**: Clear logs show what's processed vs skipped
- **Flexibility**: Works across all ingestion modes

## Related Documentation

- `docs/database_ingestion/INCREMENTAL_FIX_FINAL_REPORT.md` - Detailed report
- `docs/database_ingestion/INCREMENTAL_INGESTION_FIX.md` - Technical details
- `scripts/ingestion/README.md` - Full ingestion guide
