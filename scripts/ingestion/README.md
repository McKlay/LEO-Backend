# Manual Chunking Ingestion Scripts

This directory contains scripts for managing the manual chunking workflow for labor law documents.

## Philosophy

**Manual chunking** gives us 100% control over how documents are split, ensuring:
- ✅ **Semantic completeness** - Each chunk is self-contained and meaningful
- ✅ **Accurate citations** - Preserves exact legal structure and references
- ✅ **Incremental updates** - Edit only changed chunks without re-processing entire documents
- ✅ **Version control** - Git tracks all changes to chunks
- ✅ **Quality assurance** - Human verification of every chunk

## Available Scripts

### 1. Validation

#### `validate_chunks.py`
Validate chunk files for correctness.

```powershell
# Validate all documents
python scripts/ingestion/validate_chunks.py

# Validate specific document
python scripts/ingestion/validate_chunks.py --document PD-No-851

# Strict mode (warnings as errors)
python scripts/ingestion/validate_chunks.py --strict

# Verbose output
python scripts/ingestion/validate_chunks.py --verbose
```

#### `verify_chunk.py`
Quick verification of a single chunk file.

```powershell
# Verify single chunk
python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-851/01-decree-main.md

# With detailed output
python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-851/01-decree-main.md --verbose
```

### 2. Ingestion

#### `ingest_manual.py`
Ingest manually chunked documents into the database.

```powershell
# Ingest specific document
python scripts/ingestion/ingest_manual.py --folder PD-No-851

# Ingest all documents
python scripts/ingestion/ingest_manual.py --all

# Dry run (preview without ingesting)
python scripts/ingestion/ingest_manual.py --folder PD-No-851 --dry-run

# Force re-ingestion
python scripts/ingestion/ingest_manual.py --folder PD-No-851 --force

# Ingest single chunk file
python scripts/ingestion/ingest_manual.py --file kb/chunks/PD-No-851/01-decree-main.md
```

### 3. Status & Management

#### `check_ingestion.py`
Check which chunks have been ingested.

```powershell
# Check all documents
python scripts/ingestion/check_ingestion.py

# Check specific document
python scripts/ingestion/check_ingestion.py --document PD-No-851

# Detailed output
python scripts/ingestion/check_ingestion.py --verbose
```

#### `list_documents.py`
List all manually chunked documents.

```powershell
# List all documents
python scripts/ingestion/list_documents.py

# Detailed information
python scripts/ingestion/list_documents.py --verbose

# Show only incomplete documents
python scripts/ingestion/list_documents.py --incomplete
```

### 4. Document Creation

#### `create_template.py`
Create a new document template for chunking.

```powershell
# Create with full metadata
python scripts/ingestion/create_template.py `
    --name "RA-No-10361" `
    --source "Republic Act No. 10361" `
    --reference "RA 10361" `
    --short-name "Domestic Workers Act" `
    --type statute `
    --year 2013 `
    --url "https://lawphil.net/statutes/repacts/ra2013/ra_10361_2013.html"

# Create minimal template
python scripts/ingestion/create_template.py --name "RA-No-10361"
```

## Typical Workflow

### 1. Create New Document

```powershell
# Create template
python scripts/ingestion/create_template.py --name "RA-No-10361"

# Edit metadata.json and create chunk files in kb/chunks/RA-No-10361/
# See kb/chunks/README.md for guidelines
```

### 2. Validate Chunks

```powershell
# Validate your chunks
python scripts/ingestion/validate_chunks.py --document RA-No-10361

# Fix any errors, then validate again
python scripts/ingestion/verify_chunk.py kb/chunks/RA-No-10361/01-main.md
```

### 3. Ingest to Database

```powershell
# Dry run first
python scripts/ingestion/ingest_manual.py --folder RA-No-10361 --dry-run

# Actual ingestion
python scripts/ingestion/ingest_manual.py --folder RA-No-10361
```

### 4. Verify Ingestion

```powershell
# Check status
python scripts/ingestion/check_ingestion.py --document RA-No-10361
```

### 5. Update Existing Chunk

```powershell
# Edit chunk file in kb/chunks/

# Validate
python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-851/02-rules.md

# Re-ingest with force
python scripts/ingestion/ingest_manual.py `
    --file kb/chunks/PD-No-851/02-rules.md `
    --force
```

## Chunk File Format

Each chunk is a Markdown file with YAML frontmatter:

```markdown
---
chunk_id: unique_identifier_no_spaces
title: Descriptive Title
article_number: database_article_number
semantic_type: decree|rules|provisions|definitions
hierarchy:
  part: Main Decree
  sections: Sections 1-3
keywords:
  - keyword1
  - keyword2
  - keyword3
has_table: false
has_formula: false
has_list: true
---

# Content Header

Actual content goes here...
```

## Document Status

Current manual chunking progress:

| Document | Status | Chunks | Priority |
|----------|--------|--------|----------|
| PD-No-851 | ✅ DONE | 5/5 | Complete |
| RA-No-10361 | ⏳ TODO | 0 | 🔴 HIGH |
| DOLE-DO-147-15 | ⏳ TODO | 0 | 🟡 MEDIUM |
| SEnA | ⏳ TODO | 0 | 🟡 MEDIUM |
| RA-No-11058 | ⏳ TODO | 0 | 🟡 MEDIUM |
| RA-No-11199 | ⏳ TODO | 0 | 🟡 MEDIUM |
| NLRC-Rules | ⏳ TODO | 0 | 🟢 LOW |
| DOLE-Handbook | ⏳ TODO | 0 | 🟢 LOW |
| Covid-Protocols | ⏳ TODO | 0 | 🟢 LOW |
| PD-No-442 | ⏳ TODO | 0 | 🔵 LAST (Labor Code - LARGE) |

## Troubleshooting

### Validation Errors

**Missing frontmatter:**
```markdown
❌ Wrong:
# Content starts here

✅ Correct:
---
chunk_id: example
title: Example
---

# Content starts here
```

**Invalid keywords:**
```yaml
❌ Wrong:
keywords: []

✅ Correct:
keywords:
  - keyword1
  - keyword2
  - keyword3
```

### Ingestion Issues

**Chunk already exists:**
- Use `--force` flag to re-ingest
- Or delete from database first

**Connection errors:**
- Check `.env` file has correct credentials
- Verify Supabase database is accessible

## Best Practices

1. **Always validate before ingesting**
   ```powershell
   python scripts/ingestion/validate_chunks.py --document <name>
   ```

2. **Use dry-run first**
   ```powershell
   python scripts/ingestion/ingest_manual.py --folder <name> --dry-run
   ```

3. **Commit chunks to Git**
   ```powershell
   git add kb/chunks/<name>/
   git commit -m "Add manual chunks for <name>"
   ```

4. **Keep metadata updated**
   - Update `last_updated` when editing chunks
   - Update `total_chunks` when adding/removing chunks

## Related Documentation

- `kb/chunks/README.md` - Chunking guidelines
- `docs/database_ingestion/QUICK_REFERENCE.md` - Quick reference
- `docs/database_ingestion/MANUAL_CHUNKING_ARCHITECTURE.md` - Architecture details
- `kb/chunks/PD-No-851/` - Complete working example

## Support

For questions or issues:
1. Check example chunks in `kb/chunks/PD-No-851/`
2. Run validation scripts
3. Review error messages carefully
4. Consult architecture documentation
