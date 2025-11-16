"""
Manual Chunking Ingestion Scripts

This package contains scripts for managing manual chunking ingestion workflow.

## Quick Start

1. Validate chunks:
   ```powershell
   python scripts/ingestion/validate_chunks.py
   python scripts/ingestion/validate_chunks.py --document PD-No-851
   ```

2. Ingest chunks:
   ```powershell
   python scripts/ingestion/ingest_manual.py --folder PD-No-851
   python scripts/ingestion/ingest_manual.py --all
   ```

3. Check status:
   ```powershell
   python scripts/ingestion/check_ingestion.py
   ```

## Available Scripts

### Core Operations
- `validate_chunks.py` - Validate manual chunk files
- `ingest_manual.py` - Ingest manual chunks to database
- `check_ingestion.py` - Check ingestion status

### Document Management
- `list_documents.py` - List all chunked documents
- `create_template.py` - Create new document template
- `verify_chunk.py` - Verify single chunk file

## Documentation

See `docs/database_ingestion/` for complete guides:
- `QUICK_REFERENCE.md` - Quick command reference
- `MANUAL_CHUNKING_ARCHITECTURE.md` - Architecture details

## Requirements

All scripts require:
- Python 3.11+
- `.env` file with database credentials
- Access to Supabase database
- OpenAI API key (for embeddings)
"""

__version__ = "1.0.0"
__author__ = "LEO Team"

# Project root for easy access
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
CHUNKS_DIR = PROJECT_ROOT / "kb" / "chunks"
DOCS_DIR = PROJECT_ROOT / "docs" / "database_ingestion"
