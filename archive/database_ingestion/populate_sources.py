"""
Populate labor_law_sources table from document registry.

Usage:
    python scripts/database_ingestion/populate_sources.py
    python scripts/database_ingestion/populate_sources.py --update
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from original location
from scripts.populate_sources import main

if __name__ == "__main__":
    main()
