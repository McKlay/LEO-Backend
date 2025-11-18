# PD-No-442

## Document Information

- **Source**: Presidential Decree No. 442 (Labor Code of the Philippines)
- **Reference**: PD 442
- **Type**: statute
- **Year**: 1974

## Chunking Status

- **Total Chunks**: 0 (update metadata.json after chunking)
- **Last Updated**: 2025-11-14

## Next Steps

1. Read the source document
2. Plan chunk boundaries (see kb/chunks/README.md for guidelines)
3. Create chunk files (01-*.md, 02-*.md, etc.)
4. Update metadata.json with correct total_chunks
5. Validate: `python scripts/ingestion/validate_chunks.py --document PD-No-442`
6. Ingest: `python scripts/ingestion/ingest_manual.py --folder PD-No-442`

## Guidelines

- Each chunk should be semantically complete
- Target: 200-800 words per chunk
- Use descriptive filenames: `{number}-{section-type}-{description}.md`
- Include all required YAML frontmatter fields
- Add at least 3 keywords per chunk

See `kb/chunks/PD-No-851/` for a complete example.
