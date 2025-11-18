# Manual Chunk Repository

This directory contains **manually chunked legal documents** ready for ingestion into the LEO knowledge base.

## Purpose

Instead of relying on LLM-based automatic chunking (which can be inaccurate), we manually split documents into semantically coherent chunks that:
- Preserve hierarchical structure (preambles + sections, books + titles)
- Are 100% accurate (human-verified)
- Support incremental updates (edit only changed chunks)
- Are version-controlled (Git tracks all changes)

## Structure

```
chunks/
├── PD-No-851/              # One folder per document
│   ├── metadata.json       # Document metadata
│   ├── 01-chunk.md        # Individual chunks
│   ├── 02-chunk.md
│   └── ...
├── PD-No-442/
│   ├── metadata.json       # Document metadata
│   ├── 01-chunk.md        # Individual chunks
│   ├── 02-chunk.md
└── ...
```

## Chunk File Format

Each chunk is a **Markdown file with YAML frontmatter**:

```markdown
---
chunk_id: unique_identifier
title: Descriptive title
article_number: {source_prefix}_{descriptive_section_id}
semantic_type: decree|statute|rules|provisions|definitions|guidelines|handbook
hierarchy:
  part: "Preliminary Title"  # or "Main Decree", "Chapter I", "Rule I"
  sections: "Articles 7-11"  # or "Sections 1-3", "Rule I-A"
keywords:
  - keyword1
  - keyword2
has_table: false
has_formula: false
has_list: true
---

# Actual Content

The full text of the chunk goes here...
```

**CRITICAL: Article Number Format**

The `article_number` field **MUST** be a string identifier in the format:
```
{source_prefix}_{descriptive_section_id}
```

**Examples:**
- `pd851_decree_sec1_3` - Presidential Decree 851, decree sections 1-3
- `pd851_rules_preamble_sec1_2` - PD 851, rules preamble and sections 1-2
- `ra11199_sec3_establishment` - Republic Act 11199, section 3 (establishment)
- `ra11199_sec12_13b_pension_benefits` - RA 11199, sections 12-13B (pension benefits)
- `pd442_book1_title1_art1_11` - PD 442 (Labor Code), Book 1, Title 1, Articles 1-11

**Naming Guidelines:**
1. **Source prefix**: Use lowercase abbreviation (e.g., `pd851`, `ra11199`, `pd442`)
2. **Section identifier**: Use descriptive text (lowercase, underscore-separated)
3. **Never use numeric-only values** (e.g., `1`, `2`, `3`) - database expects strings
4. **Be descriptive**: Include section numbers and/or topic keywords
5. **Keep consistent**: Within a document, use the same prefix format

**Note**: This string identifier is used for database lookups and auto-chunking operations.

**CRITICAL: Hierarchy Structure Flexibility**

The `hierarchy` field uses **flexible key names** adapted to each document's structure:

- **For Labor Code (PD-442)**: Use `part` + `sections`
  ```yaml
  hierarchy:
    part: "Book One"  # or "Preliminary Title"
    sections: "Articles 12-15"
  ```

- **For simple decrees (PD-851)**: Use `part` + `sections`
  ```yaml
  hierarchy:
    part: "Main Presidential Decree"
    sections: "Preamble and Sections 1-3"
  ```

- **For Republic Acts with Chapters (RA-11058)**: Use `chapter` + `sections`
  ```yaml
  hierarchy:
    chapter: "Chapter I"
    sections: "Section 1"
  ```

- **For Republic Acts with Articles (RA-10361)**: Use `article` + `sections`
  ```yaml
  hierarchy:
    article: "Article II"
    sections: "Sections 5-10"
  ```

- **For Rules/Orders (DOLE-DO-147-15, SEnA, NLRC)**: Use `rule` + `sections`
  ```yaml
  hierarchy:
    rule: "Rule I-A"
    sections: "Sections 1-5"
  ```

- **For Handbooks (DOLE Handbook)**: Use `topic` + `sections`
  ```yaml
  hierarchy:
    topic: "Minimum Wage"
    sections: "Section 1"
  ```

**Note**: The database schema maps these to `metadata JSONB` field, preserving the original structure.

## Metadata Format

Each document folder has a `metadata.json`:

```json
{
  "source": "Presidential Decree No. 851",
  "reference": "PD 851",
  "short_name": "13th Month Pay Law",
  "doc_type": "statute",
  "year": "1975",
  "url": "https://lawphil.net/statutes/presdecs/pd1975/pd_851_1975.html",
  "total_chunks": 5,
  "chunking_strategy": "manual",
  "last_updated": "2024-11-13",
  "structure_note": "Optional note about document structure and chunking approach"
}
```

**Field Descriptions**:

| Field | Type | Required | Description | Database Mapping |
|-------|------|----------|-------------|------------------|
| `source` | string | Yes | Full official name of the document | `labor_law_sources.title` |
| `reference` | string | Yes | Short reference code (e.g., "PD 851", "RA 11058") | `labor_law_sources.reference` |
| `short_name` | string | Yes | Common name for the law | Used in UI, not in DB |
| `doc_type` | string | Yes | Document category | `labor_law_sources.source_type` |
| `year` | string | Yes | Year enacted/published | `labor_law_sources.year` |
| `url` | string | No | Official or authoritative URL | `labor_law_sources.official_url` |
| `total_chunks` | number | Yes | Expected number of chunk files | Validation only |
| `chunking_strategy` | string | Yes | Always "manual" for this directory | Validation only |
| `last_updated` | string | Yes | ISO date of last update | Validation only |
| `structure_note` | string | No | Notes about document structure | Validation only |

**Valid `doc_type` values**:
- `statute` - Laws passed by Congress (RA, PD, BP)
- `department_order` - DOLE Department Orders (DO)
- `procedural_rules` - NLRC, SEnA, court procedures
- `guidelines` - Advisory/interim guidelines
- `handbook` - Reference handbooks
- `irr` - Implementing Rules and Regulations

## Chunking Guidelines

### 1. Semantic Completeness
- Each chunk should be **self-contained** and **meaningful** on its own
- Include all context needed to understand the content
- Don't split mid-sentence or mid-paragraph

### 2. Hierarchical Structure
- Group related content together:
  - Preamble + its sections
  - Rules header + its subsections
  - Book title + its chapters (if short)
- Preserve legal document hierarchy

### 3. Size Guidelines
- **Target**: 200-800 words per chunk
- **Flexible**: Semantic completeness > strict word count
- **Exception**: Tables, formulas, lists must remain intact

### 4. Special Formats
- **Tables**: Keep entire table in one chunk
- **Formulas**: Include complete calculation with context
- **Lists**: Include all items (don't split numbered lists)

### 5. Naming Convention
```
{number}-{section-type}-{brief-description}.md

Examples:
01-decree-preamble.md
02-decree-sec1-3.md
03-rules-preamble.md
04-rules-sec1-2.md
```

## Dry Run (test without writing to DB)
```bash
python -m kb.ingest.sync_to_vectorstore --manual --folder kb/chunks/PD-No-851 --dry-run
```

## Workflow

### Initial Chunking
1. Read full legal document from `kb/docs/`
2. Identify natural boundaries (Books, Titles, Articles, Sections, Rules)
3. Create folder: `kb/chunks/{document-name}/`
4. Create `metadata.json`
5. Split into `.md` files with YAML frontmatter
6. Commit to Git

### Editing Existing Chunk
1. Edit `.md` file in VS Code
2. Review changes (Git diff)
3. Commit to Git
4. Re-ingest: `python -m kb.ingest.sync_to_vectorstore --manual --file <path> --force`

### Adding New Chunks
1. Create new `.md` file in appropriate folder
2. Update `total_chunks` in `metadata.json`
3. Commit to Git
4. Ingest: `python -m kb.ingest.sync_to_vectorstore --manual --folder <folder>`

## Quality Checks

Before committing chunks:
- [ ] YAML frontmatter is valid
- [ ] All required fields present
- [ ] Content is semantically complete
- [ ] No truncated text
- [ ] Keywords are relevant
- [ ] Hierarchy structure is correct

## Example: PD-No-851

See `kb/chunks/PD-No-851/` for a complete example of properly chunked legal document.

## Benefits

✅ 100% accuracy (human-verified)  
✅ Full control and transparency  
✅ Incremental updates (change only affected chunks)  
✅ Version control (Git tracks changes)  
✅ No LLM hallucination risk  
✅ Natural hierarchical structure  
