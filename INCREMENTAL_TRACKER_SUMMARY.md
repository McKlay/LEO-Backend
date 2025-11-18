# Incremental Tracker Fix - Summary

## Problem
Manual chunk ingestion was re-ingesting all chunks in a folder whenever any single file changed, wasting tokens unnecessarily.

## Solution
Changed tracking from **folder-level** to **file-level**:
- ✅ Each `.md` file in `kb/chunks/{folder}/` is tracked individually
- ✅ Changed files are re-ingested
- ✅ Unchanged files are skipped
- ✅ Minimal token consumption

## Implementation

### Core Logic
```python
# For each chunk, check if its source file changed
for chunk in chunks:
    file_path = folder_path / f"{chunk.file_stem}.md"
    should_ingest_file, reason = self.tracker.should_ingest(file_path, force=force)
    if should_ingest_file:
        filtered_chunks.append(chunk)

# Only ingest changed chunks
chunks = filtered_chunks
```

### Recording
- Record each file individually with its own hash
- Database tracks per-file ingestion status
- Enables change detection at file level

## Files Modified

### `kb/ingest/sync_to_vectorstore.py`
- Removed folder-level hash check
- Added per-file filtering in `ingest_manual_chunks()`
- Changed recording to track individual files
- Updated logging to show skipped/changed counts

### `kb/ingest/incremental_tracker.py`
- Removed `calculate_folder_hash()` method
- Removed `is_folder` parameter from `should_ingest()`
- Kept file-level hashing as is

## Behavior

### Example: Folder with 5 files, 1 file changed
```
Before: All 5 files re-ingested (wasteful)
After:  1 file re-ingested, 4 files skipped (efficient)
```

### Database Records
- Old: One record per folder with combined hash
- New: One record per file with individual hash
- Enables granular change detection

## Testing
```bash
python scripts/test_tracker_simple.py
# Verifies: File-level tracking works
```

## Status
✅ **FIXED** - File-level incremental tracking implemented
