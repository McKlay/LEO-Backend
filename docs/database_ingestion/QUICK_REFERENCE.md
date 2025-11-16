# Manual Chunking Quick Reference

## 🎯 Quick Commands

### Validate Chunks
```bash
# Validate all documents
python scripts/ingestion/validate_chunks.py

# Validate specific document
python scripts/ingestion/validate_chunks.py --document PD-No-851

# Strict mode (fail on warnings)
python scripts/ingestion/validate_chunks.py --strict
```

### Ingest Chunks (Coming Soon)
```bash
# Ingest single document
python scripts/ingestion/ingest_manual.py --folder PD-No-851

# Ingest all manual chunks
python scripts/ingestion/ingest_manual.py --all

# Re-ingest single edited chunk
python scripts/ingestion/ingest_manual.py --file kb/chunks/PD-No-851/02-*.md --force

# Dry run (test without writing)
python scripts/ingestion/ingest_manual.py --folder PD-No-851 --dry-run
```

---

## 📂 File Structure

```
kb/chunks/
├── PD-No-851/                      ✅ DONE
│   ├── metadata.json
│   ├── 01-decree-main.md
│   ├── 02-rules-preamble-definitions.md
│   ├── 03-rules-coverage-eligibility.md
│   ├── 04-rules-benefits-compliance.md
│   └── 05-supplementary-rules.md
│
├── PD-No-442/                      ⏳ TODO (Labor Code - LARGE)
│   ├── metadata.json
│   ├── book1/
│   │   ├── 01-pre-employment.md
│   │   └── ...
│   └── ...
│
└── [Other documents...]            ⏳ TODO
```

---

## 📝 Chunk Template

```markdown
---
chunk_id: unique_identifier_no_spaces
title: Descriptive Title of This Chunk
article_number: database_article_number
semantic_type: decree|rules|provisions|definitions|supplementary
hierarchy:
  part: Main Decree
  sections: Sections 1-3
keywords:
  - keyword1
  - keyword2
  - keyword3
has_table: false
has_formula: true
has_list: true
---

# Content Header

Actual content goes here...

## Section 1
...

## Section 2
...
```

---

## ✅ Metadata Template

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
  "notes": "Optional notes about chunking decisions"
}
```

---

## 🔍 Chunking Guidelines

### 1. Semantic Completeness
- ✅ Each chunk is **self-contained**
- ✅ Include all context to understand the chunk
- ❌ Don't split mid-sentence or mid-paragraph

### 2. Size Guidelines
- **Target**: 200-800 words
- **Flexible**: Semantic completeness > strict word count
- **Exception**: Keep tables, formulas, lists intact

### 3. Hierarchical Grouping
✅ **DO**: Group related content together
- Preamble + its sections
- Rules header + its subsections  
- Book title + short chapters

❌ **DON'T**: Split artificially
- Don't separate section header from content
- Don't split numbered lists
- Don't break tables across chunks

### 4. File Naming
```
{number}-{section-type}-{brief-description}.md

Examples:
01-decree-main.md
02-rules-preamble-definitions.md
03-rules-coverage-eligibility.md
```

### 5. Keywords
- Minimum: 3 keywords per chunk
- Include: legal terms, document numbers, key concepts
- Examples: `13th month pay`, `employer obligation`, `P1000 limit`

---

## 🎯 Workflow

### Creating New Document

1. **Create folder**
   ```bash
   mkdir kb/chunks/RA-No-10361
   ```

2. **Create metadata.json**
   - Copy template
   - Fill in document details
   - Set `total_chunks` to 0 initially

3. **Read source document**
   - Identify natural boundaries
   - Plan chunk structure

4. **Create chunks**
   - One .md file per chunk
   - Use template above
   - Fill YAML frontmatter
   - Add content

5. **Update metadata.json**
   - Set correct `total_chunks`
   - Update `last_updated`

6. **Validate**
   ```bash
   python scripts/ingestion/validate_chunks.py --document RA-No-10361
   ```

7. **Commit to Git**
   ```bash
   git add kb/chunks/RA-No-10361/
   git commit -m "Add manual chunks for RA-No-10361 (Domestic Workers Act)"
   ```

8. **Ingest**
   ```bash
   python scripts/ingestion/ingest_manual.py --folder RA-No-10361
   ```

### Editing Existing Chunk

1. **Edit .md file** in VS Code

2. **Update `last_updated`** in metadata.json

2. **Validate**
   ```bash
   python scripts/ingestion/validate_chunks.py --document PD-No-851
   ```

4. **Commit**
   ```bash
   git add kb/chunks/PD-No-851/02-*.md
   git commit -m "Update PD-851 chunk 02: clarify basic salary definition"
   ```

5. **Re-ingest**
   ```bash
   python scripts/ingestion/ingest_manual.py --file kb/chunks/PD-No-851/02-rules-preamble-definitions.md --force
   ```

---

## 📊 Document Status

| Document | Status | Chunks | Priority |
|----------|--------|--------|----------|
| PD-No-851 | ✅ DONE | 5/5 | ✓ Complete |
| RA-No-10361 | ⏳ TODO | 0 | 🔴 HIGH (small, good practice) |
| DOLE-Dep-Order-147-15 | ⏳ TODO | 0 | 🟡 MEDIUM |
| SEnA | ⏳ TODO | 0 | 🟡 MEDIUM |
| RA-No-11058 | ⏳ TODO | 0 | 🟡 MEDIUM |
| RA-No-11199 | ⏳ TODO | 0 | 🟡 MEDIUM |
| NLRC-Rules | ⏳ TODO | 0 | 🟢 LOW |
| DOLE-Handbook | ⏳ TODO | 0 | 🟢 LOW |
| DOLE-Covid-Protocols | ⏳ TODO | 0 | 🟢 LOW |
| PD-No-442 | ⏳ TODO | 0 | 🔵 LAST (Labor Code - LARGE) |

---

## 🚨 Common Issues

### Issue: "Missing YAML frontmatter"
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

### Issue: "Keywords list is empty"
```yaml
❌ Wrong:
keywords: []

✅ Correct:
keywords:
  - 13th month pay
  - employer requirement
  - basic salary
```

### Issue: "Content is very short"
```markdown
❌ Wrong: Only 50 chars of content

✅ Correct: At least 100+ chars, preferably 200-800 words
```

---

## 🎓 Learning from PD-No-851

### Good Examples

**Chunk 1** (Decree Main):
- ✅ Preamble + Sections 1-3 grouped
- ✅ Self-contained (complete decree text)
- ✅ Clear keywords: `13th month pay`, `P1000 limit`, `December 24 deadline`

**Chunk 5** (Supplementary):
- ✅ All 6 clarifications in one chunk
- ✅ Semantically related (all supplementary rules)
- ✅ Keywords include special cases: `contractors exemption`, `private school teachers`

### Structure Lessons
- Decree → Rules → Supplementary = Natural boundaries
- Group preamble with its sections (don't separate)
- Related sections stay together (e.g., Sections 3-5 all about coverage)

---

## 📞 Need Help?

1. **Check examples**: `kb/chunks/PD-No-851/`
2. **Run validation**: `python scripts/validate_manual_chunks.py`
3. **Read guidelines**: `kb/chunks/README.md`
4. **Check architecture**: `docs/database_ingestion/MANUAL_CHUNKING_ARCHITECTURE.md`

---

## ⏭️ Next Steps

1. ✅ **Infrastructure ready** - Validation working
2. ✅ **Ingestion scripts ready** - All manual chunking scripts created
3. ⏳ **Update ingestion pipeline** - Connect to database
4. ⏳ **Test PD-No-851 ingestion** - Validate pipeline
5. ⏳ **Chunk next document** - RA-No-10361 (practice)
6. ⏳ **Chunk remaining docs** - Complete all 10 documents
