"""
Verify database ingestion setup and status.

Usage:
    python scripts/database_ingestion/verify_ingestion.py
    python scripts/database_ingestion/verify_ingestion.py --file PD-851.txt
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from original location
from scripts.verify_day4_completion import main

if __name__ == "__main__":
    sys.exit(main())
