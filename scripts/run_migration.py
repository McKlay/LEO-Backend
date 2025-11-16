"""
Script to run SQL migrations against Supabase database
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
import psycopg2
from psycopg2 import sql


def run_migration(migration_file: Path):
    """Execute a SQL migration file"""
    
    # Read the migration file
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    # Connect to database
    print(f"Connecting to database...")
    conn = psycopg2.connect(settings.supabase_db_url)
    conn.set_session(autocommit=False)
    
    try:
        cursor = conn.cursor()
        
        print(f"Executing migration: {migration_file.name}")
        cursor.execute(migration_sql)
        
        # Commit the transaction
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # Close cursor
        cursor.close()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Get migration file from command line or use default
    if len(sys.argv) > 1:
        migration_file = Path(sys.argv[1])
    else:
        migration_file = Path(__file__).parent.parent / "infra" / "supabase" / "migrations" / "001_add_missing_columns.sql"
    
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"Running migration: {migration_file}")
    run_migration(migration_file)
