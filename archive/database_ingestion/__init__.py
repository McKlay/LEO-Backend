"""
Database Ingestion Scripts

This package contains all scripts for managing labor law document ingestion into the database.

## Quick Start

1. Verify setup:
   ```powershell
   python scripts/database_ingestion/verify_setup.py
   ```

2. Populate sources:
   ```powershell
   python scripts/database_ingestion/populate_sources.py
   ```

3. Ingest all documents (legacy regex chunking):
   ```powershell
   python scripts/database_ingestion/ingest_all.py
   ```

## Manual Chunking (Recommended)

For manual chunking workflow, use scripts in `scripts/ingestion/`:

```powershell
# Validate chunks
python scripts/ingestion/validate_chunks.py

# Ingest manual chunks
python scripts/ingestion/ingest_manual.py --folder PD-No-851

# Check status
python scripts/ingestion/check_ingestion.py
```

See `scripts/ingestion/README.md` for complete manual chunking guide.

## Available Scripts (Legacy)

### Core Operations
- `populate_sources.py` - Create source records from registry
- `ingest_all.py` - Batch ingest all documents (regex chunking)
- `ingest_single.py` - Ingest a single document (regex chunking)
- `verify_ingestion.py` - Verify ingestion results

### Source Management
- `add_source.py` - Add new source manually
- `list_sources.py` - List all sources
- `remove_source.py` - Remove source and its sections

### Status & Testing
- `verify_setup.py` - Verify database setup
- `check_status.py` - Check file ingestion status
- `check_history.py` - View ingestion history
- `test_retrieval.py` - Test search functionality

## Documentation

See `docs/database_ingestion/` for complete guides:
- `COMPLETE_GUIDE.md` - Comprehensive operational guide
- `COMMAND_REFERENCE.md` - Quick command reference
- `QUICK_REFERENCE.md` - Manual chunking quick reference

## Migration Note

This package contains **legacy regex chunking scripts**. 

**For new documents, use manual chunking** in `scripts/ingestion/` which provides:
- ✅ 100% accuracy
- ✅ Semantic completeness
- ✅ Version control
- ✅ Incremental updates

## Requirements

All scripts require:
- Python 3.11+
- `.env` file with database credentials
- Access to Supabase database
- OpenAI API key (for ingestion)

## Support

For issues or questions, refer to:
- Manual chunking: `scripts/ingestion/README.md`
- Legacy regex: Troubleshooting section in COMPLETE_GUIDE.md
- Common errors in COMMAND_REFERENCE.md
- Project documentation in docs/
"""

__version__ = "2.0.0"  # Updated for manual chunking migration
__author__ = "LEO Team"

# Utility imports for convenience
from pathlib import Path

# Project root for easy access
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "kb" / "docs"
CHUNKS_DIR = PROJECT_ROOT / "kb" / "chunks"
SCRIPTS_DIR = PROJECT_ROOT / "scripts" / "database_ingestion"
INGESTION_DIR = PROJECT_ROOT / "scripts" / "ingestion"
