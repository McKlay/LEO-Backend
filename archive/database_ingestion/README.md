# This is deprecated, check ingestion for the manual ingestion
# Database Ingestion Scripts

Complete toolkit for managing Philippine labor law document ingestion into the Supabase database.

## 📁 Directory Contents

### Core Operations
| Script | Purpose |
|--------|---------|
| `populate_sources.py` | Create source records from DOCUMENT_REGISTRY |
| `ingest_all.py` | Batch ingest all documents in registry |
| `ingest_single.py` | Ingest a single document by filename |
| `verify_ingestion.py` | Verify database setup and ingestion results |

### Source Management
| Script | Purpose |
|--------|---------|
| `add_source.py` | Manually add new source to database |
| `list_sources.py` | List all sources with filtering options |
| `remove_source.py` | Remove source and CASCADE delete sections |

### Status & Testing
| Script | Purpose |
|--------|---------|
| `verify_setup.py` | Verify database connection, tables, indexes |
| `check_status.py` | Check ingestion status of specific file |
| `check_history.py` | View ingestion history with filters |
| `test_retrieval.py` | Test search functionality (keyword/semantic/article) |

## 🚀 Quick Start

### 1. Verify Setup
```powershell
python scripts/database_ingestion/verify_setup.py
```

### 2. Populate Sources
```powershell
python scripts/database_ingestion/populate_sources.py
```

### 3. Ingest All Documents
```powershell
python scripts/database_ingestion/ingest_all.py
```

### 4. Verify Results
```powershell
python scripts/database_ingestion/verify_ingestion.py
```

## 📖 Common Use Cases

### Adding a New Labor Law Document

1. **Place file** in `kb/docs/` (e.g., `RA-11058.txt`)

2. **Add to registry** (`kb/ingest/registry.py`):
```python
{
    "filename": "RA-11058.txt",
    "source_name": "Republic Act No. 11058",
    "source_type": "republic_act",
    "reference_code": "RA-11058"
}
```

3. **Create source record**:
```powershell
python scripts/database_ingestion/populate_sources.py
```

4. **Ingest document**:
```powershell
python scripts/database_ingestion/ingest_single.py --file RA-11058.txt
```

5. **Verify**:
```powershell
python scripts/database_ingestion/check_status.py --file RA-11058.txt
```

### Updating an Existing Document

1. **Update file** in `kb/docs/`
2. **Re-ingest with force flag**:
```powershell
python scripts/database_ingestion/ingest_single.py --file PD-851.txt --force
```

### Removing a Document

1. **Remove source and all sections**:
```powershell
python scripts/database_ingestion/remove_source.py --reference PD-851
```
*Note: Includes confirmation prompt*

## 🔍 Checking Status

### Check specific file status
```powershell
python scripts/database_ingestion/check_status.py --file PD-851.txt
```

### View ingestion history
```powershell
# All history
python scripts/database_ingestion/check_history.py

# Failed ingestions only
python scripts/database_ingestion/check_history.py --status failed

# Specific file
python scripts/database_ingestion/check_history.py --filename PD-851.txt

# Last 5 entries
python scripts/database_ingestion/check_history.py --limit 5
```

### List all sources
```powershell
# Table format
python scripts/database_ingestion/list_sources.py

# JSON format
python scripts/database_ingestion/list_sources.py --format json

# Filter by type
python scripts/database_ingestion/list_sources.py --type presidential_decree
```

## 🧪 Testing Retrieval

### Test search functionality
```powershell
# Keyword search
python scripts/database_ingestion/test_retrieval.py --query "overtime pay" --method keyword

# Semantic search
python scripts/database_ingestion/test_retrieval.py --query "employee rights" --method semantic

# Article lookup
python scripts/database_ingestion/test_retrieval.py --query "article 82" --method article

# All methods
python scripts/database_ingestion/test_retrieval.py --query "minimum wage" --method all --limit 5
```

## 📚 Documentation

### Complete Guides
- **[COMPLETE_GUIDE.md](../../docs/database_ingestion/COMPLETE_GUIDE.md)** - Comprehensive operational guide with troubleshooting
- **[COMMAND_REFERENCE.md](../../docs/database_ingestion/COMMAND_REFERENCE.md)** - Quick command cheat sheet

### Project Documentation
- **[BACKEND_API_SPECIFICATIONS.md](../../docs/BACKEND_API_SPECIFICATIONS.md)** - API specifications
- **[DAY4_QUICK_REFERENCE.md](../../docs/DAY4_QUICK_REFERENCE.md)** - Day 4 implementation reference

## ⚙️ Requirements

### Environment
- Python 3.11+
- `.env` file with credentials:
  ```env
  SUPABASE_DB_URL=postgresql://...
  OPENAI_API_KEY=sk-...
  ```

### Dependencies
- All dependencies from `requirements.txt`
- OpenAI API access (for embeddings)
- Supabase database access

### Database
- PostgreSQL with pgvector extension
- Tables: `labor_law_sources`, `labor_law_sections`, `labor_law_chunks`, `ingestion_history`
- Indexes: HNSW (vector), GIN (full-text), B-tree (article, source FK)

## 🛠️ Troubleshooting

### Common Issues

**"No module named 'kb'"**
```powershell
# Run from project root
cd c:\Users\Clay\Desktop\MCS\labor-law-chatbot\LEO-Backend
python scripts/database_ingestion/verify_setup.py
```

**"Database connection failed"**
```powershell
# Verify .env file exists and has correct credentials
cat .env | Select-String SUPABASE_DB_URL
```

**"OpenAI API connection failed"**
```powershell
# Verify API key
cat .env | Select-String OPENAI_API_KEY
```

**"Table not found"**
```powershell
# Run schema migration
python scripts/run_schema_migration.py
```

### Getting Help

1. Check `docs/database_ingestion/COMPLETE_GUIDE.md` for detailed troubleshooting
2. Run `verify_setup.py` to diagnose environment issues
3. Check `check_history.py` for ingestion error messages
4. Review logs in console output

## 📊 Best Practices

1. **Always verify setup first**: Run `verify_setup.py` before ingestion
2. **Check status after ingestion**: Use `check_status.py` to confirm success
3. **Test retrieval**: Verify searchability with `test_retrieval.py`
4. **Use force flag carefully**: Re-ingestion deletes existing data
5. **Confirm deletions**: `remove_source.py` includes safety prompts

## 🔄 Workflow Example

Complete workflow for adding new Republic Act:

```powershell
# 1. Verify setup
python scripts/database_ingestion/verify_setup.py

# 2. Add source manually (optional if not in registry)
python scripts/database_ingestion/add_source.py `
    --name "Republic Act No. 11058" `
    --type "republic_act" `
    --reference "RA-11058" `
    --description "An Act Strengthening Compliance with Occupational Safety and Health Standards"

# 3. Place file in kb/docs/RA-11058.txt

# 4. Ingest document
python scripts/database_ingestion/ingest_single.py --file RA-11058.txt

# 5. Check status
python scripts/database_ingestion/check_status.py --file RA-11058.txt

# 6. Test retrieval
python scripts/database_ingestion/test_retrieval.py --query "safety standards" --limit 3

# 7. Verify all sources
python scripts/database_ingestion/list_sources.py
```

## 📝 Notes

- All scripts support `--help` flag for detailed usage
- Scripts automatically add project root to Python path
- Logging is configured for console output (not JSON)
- Database operations use connection pooling
- Embeddings use OpenAI text-embedding-3-small (1536 dimensions)

## 🔗 Related Resources

- [Project README](../../README.md)
- [Implementation Sequence](../../ImplementationSequence.md)
- [Architecture Documentation](../../docs/adr/)
- [API Documentation](../../docs/BACKEND_API_SPECIFICATIONS.md)

---

**Last Updated**: Day 4 Implementation  
**Version**: 1.0.0  
**Maintainer**: LEO Team
