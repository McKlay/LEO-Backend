# Incremental Ingestion Fix - Summary

## Date
November 18, 2025

## Issues Identified

### Issue #1: Force flag deletes all chunks in folder
**Symptom**: When ingesting a single chunk file with `--force`, all other chunks from the same document folder were being deleted.

**Example**:
```powershell
python scripts/ingestion/ingest_manual.py --file kb/chunks/DOLE-Covid-Protocols/01-background-wsh-framework.md --force
```
This would delete ALL chunks from DOLE-Covid-Protocols, not just the one being re-ingested.

**Root Cause**: 
- Line 606 in `sync_to_vectorstore.py` was deleting by `source_id`
- `source_id` represents the entire document, not individual files
- Deleting by `source_id` removed all chunks for that document

### Issue #2: Folder ingestion skips all if one file is unchanged
**Symptom**: When ingesting a folder, if even one file was already ingested and unchanged, the entire ingestion would be skipped or all chunks would be filtered out.

**Example**:
```powershell
python scripts/ingestion/ingest_manual.py --folder DOLE-Covid-Protocols
```
If one file was unchanged, none of the changed files would be ingested.

**Root Cause**:
- Filtering logic was correct but applied too broadly
- Deletion happened at document level, not file level
- Missing granular tracking for `--all` mode

## Solutions Implemented

### Fix #1: Granular chunk deletion
**Changes in `sync_to_vectorstore.py`** (lines 600-630):

**Before**:
```python
if document_name and (force or reason == "File content changed"):
    # Delete by source_id before inserting new chunks
    deleted_count = await self.vectorstore.delete_by_source_id(str(source_id))
```

**After**:
```python
# Delete ONLY the chunks from files that are being re-ingested
chunk_ids_to_delete = []
files_to_delete = set()

for chunk in chunks:
    chunk_ids_to_delete.append(chunk.chunk_id)
    files_to_delete.add(chunk.file_stem)

if chunk_ids_to_delete:
    deleted_count = await self.vectorstore.delete(chunk_ids_to_delete)
```

**Impact**:
- ✅ Only deletes specific chunks being re-ingested
- ✅ Preserves all other chunks in the same document
- ✅ Uses chunk-level deletion, not source-level

### Fix #2: Enhanced ManualChunk with document tracking
**Changes in `manual_chunk_loader.py`**:

Added `document_name` field to `ManualChunk`:
```python
@dataclass
class ManualChunk:
    chunk_id: str
    title: str
    content: str
    article_number: str
    file_stem: Optional[str] = None
    document_name: Optional[str] = None  # NEW: tracks parent folder
    # ... other fields
```

Updated all loading methods to populate `document_name`:
- `load_chunk_file()` - accepts and sets `document_name`
- `load_document_chunks()` - passes `document_name` to chunks
- `load_single_chunk_file()` - extracts `document_name` from path
- `load_all_chunks()` - automatically sets via `load_document_chunks()`

**Impact**:
- ✅ Each chunk knows which document folder it came from
- ✅ Enables proper file-level tracking in `--all` mode
- ✅ No more warnings about unknown file paths

### Fix #3: Improved filtering logic
**Changes in `sync_to_vectorstore.py`** (lines 457-530):

**Enhancements**:
1. **Force flag handling**: When `force=True`, bypass all filtering
2. **Multi-mode support**: Works for single file, folder, and `--all` modes
3. **Granular tracking**: Uses `chunk.document_name` + `chunk.file_stem` to reconstruct paths
4. **Detailed logging**: Shows which files are skipped and why
5. **Fallback handling**: Gracefully handles edge cases

**Logic flow**:
```python
if not force:
    for chunk in chunks:
        # Determine file path based on mode
        if single_file:
            file_to_check = single_file
        elif chunk.document_name:
            file_to_check = Path(f"kb/chunks/{chunk.document_name}/{chunk.file_stem}.md")
        elif document_name:
            file_to_check = Path(f"kb/chunks/{document_name}/{chunk.file_stem}.md")
        
        # Check if file should be ingested
        should_ingest, reason = tracker.should_ingest(file_to_check, force=False)
        
        if should_ingest:
            filtered_chunks.append(chunk)
        else:
            skipped_count += 1
    
    chunks = filtered_chunks
```

**Impact**:
- ✅ Only processes changed/new files
- ✅ Correctly skips unchanged files
- ✅ Works across all ingestion modes
- ✅ Provides clear feedback on what was skipped

## Testing

Created comprehensive test suite: `scripts/test_incremental_fixes.py`

### Test 1: Single file force doesn't delete others
```powershell
python scripts/test_incremental_fixes.py
```

**Verifies**:
- Force flag on one file doesn't affect other files' ingestion records
- Other files' hashes remain unchanged
- No unexpected deletions

### Test 2: Folder incremental detection
**Verifies**:
- First ingestion processes all files
- Second ingestion (unchanged) skips all files
- Returns correct status: `"skipped"`

### Test 3: Partial folder update
**Verifies**:
- Can force re-ingest one file in a folder
- Re-ingesting folder skips all files (including the one just forced)
- Proper tracking after partial updates

## Usage Examples

### Ingest single file with force
```powershell
# OLD BEHAVIOR: Would delete ALL chunks from DOLE-Covid-Protocols
# NEW BEHAVIOR: Only re-ingests this one file
python scripts/ingestion/ingest_manual.py `
    --file kb/chunks/DOLE-Covid-Protocols/01-background-wsh-framework.md `
    --force
```

### Ingest folder (only changed files)
```powershell
# OLD BEHAVIOR: Might skip all or process all
# NEW BEHAVIOR: Only processes new/changed files, skips unchanged
python scripts/ingestion/ingest_manual.py --folder DOLE-Covid-Protocols
```

### Ingest all documents
```powershell
# OLD BEHAVIOR: Couldn't track individual files in --all mode
# NEW BEHAVIOR: Tracks each file individually, skips unchanged
python scripts/ingestion/ingest_manual.py --all
```

### Force re-ingest everything
```powershell
# NEW: Force flag bypasses all incremental detection
python scripts/ingestion/ingest_manual.py --folder PD-No-851 --force
```

## Benefits

1. **Precision**: Only re-ingests what's actually changed
2. **Safety**: No accidental deletions of unrelated chunks
3. **Performance**: Skips unnecessary work on unchanged files
4. **Transparency**: Clear logging of what's processed vs skipped
5. **Flexibility**: Works across all ingestion modes
6. **Robustness**: Handles edge cases gracefully

## Migration Notes

### No breaking changes
- Existing ingestion commands work the same
- Behavior is now more precise and safer
- No database schema changes required

### Recommended actions
1. Re-run tests to verify: `python scripts/test_incremental_fixes.py`
2. Check ingestion history: `python scripts/check_ingestion_status.py`
3. Verify chunk counts in database match expectations

## Files Modified

1. **kb/ingest/sync_to_vectorstore.py**
   - Lines 457-530: Enhanced filtering logic
   - Lines 600-630: Granular chunk deletion

2. **kb/ingest/loaders/manual_chunk_loader.py**
   - Added `document_name` field to `ManualChunk`
   - Updated `load_chunk_file()` signature
   - Updated `load_document_chunks()`
   - Updated `load_single_chunk_file()`

3. **scripts/test_incremental_fixes.py** (NEW)
   - Comprehensive test suite for all scenarios

## Related Documentation

- `scripts/ingestion/README.md` - Ingestion workflow
- `docs/database_ingestion/MANUAL_CHUNKING_ARCHITECTURE.md` - Architecture
- `kb/chunks/README.md` - Chunking guidelines

## Conclusion

The incremental ingestion system now works as intended:
- ✅ File-level granularity for tracking and deletion
- ✅ Proper filtering across all ingestion modes
- ✅ Safe force flag that only affects targeted files
- ✅ Clear feedback and logging
- ✅ Comprehensive test coverage

These fixes ensure reliable, efficient, and safe ingestion workflows for all use cases.
