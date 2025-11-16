"""
Script to verify the migration was applied successfully
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
import psycopg2


def verify_migration():
    """Verify that the migration columns were added"""
    
    # Connect to database
    print(f"Connecting to database...")
    conn = psycopg2.connect(settings.supabase_db_url)
    
    try:
        cursor = conn.cursor()
        
        # Check labor_law_sources columns
        print("\n=== Checking labor_law_sources table ===")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'labor_law_sources'
              AND column_name IN ('reference', 'year')
            ORDER BY column_name;
        """)
        
        rows = cursor.fetchall()
        if rows:
            print("✅ New columns found in labor_law_sources:")
            for row in rows:
                print(f"   - {row[0]}: {row[1]} (nullable: {row[2]})")
        else:
            print("❌ No new columns found in labor_law_sources")
        
        # Check labor_law_sections columns
        print("\n=== Checking labor_law_sections table ===")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'labor_law_sections'
              AND column_name IN ('semantic_type', 'section_number')
            ORDER BY column_name;
        """)
        
        rows = cursor.fetchall()
        if rows:
            print("✅ New columns found in labor_law_sections:")
            for row in rows:
                print(f"   - {row[0]}: {row[1]} (nullable: {row[2]})")
        else:
            print("❌ No new columns found in labor_law_sections")
        
        # Check for new index
        print("\n=== Checking indexes ===")
        cursor.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'labor_law_sources'
              AND indexname = 'idx_sources_reference';
        """)
        
        rows = cursor.fetchall()
        if rows:
            print("✅ Index idx_sources_reference found:")
            for row in rows:
                print(f"   {row[1]}")
        else:
            print("❌ Index idx_sources_reference not found")
        
        print("\n✅ Migration verification complete!")
        
        cursor.close()
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    verify_migration()
