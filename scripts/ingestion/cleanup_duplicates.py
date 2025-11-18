#!/usr/bin/env python3
"""
Clean up duplicate records in labor_law_sections table.

Keeps the most recently ingested version and deletes duplicates.

Usage:
    # Dry run (preview what will be deleted)
    python scripts/ingestion/cleanup_duplicates.py --dry-run
    
    # Actual deletion
    python scripts/ingestion/cleanup_duplicates.py
"""
import argparse
import sys
import psycopg2
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from core.config import Settings

logger = get_logger(__name__)


def cleanup_duplicates(dry_run: bool = True):
    """
    Remove duplicate records from labor_law_sections table.
    
    Keeps the most recently created version of each article.
    
    Args:
        dry_run: If True, only show what would be deleted
    """
    settings = Settings()
    db_url = settings.supabase_db_url
    
    if not db_url:
        logger.error("Database URL not configured")
        sys.exit(1)
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Find duplicates
        cursor.execute("""
            SELECT article_number, COUNT(*) as cnt 
            FROM labor_law_sections 
            GROUP BY article_number 
            HAVING COUNT(*) > 1 
            ORDER BY cnt DESC
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            logger.info("No duplicates found!")
            return
        
        print(f"\nFound {len(duplicates)} article numbers with duplicates\n")
        print(f"{'Article':<50} {'Count':<6} {'IDs to delete'}")
        print("="*80)
        
        total_to_delete = 0
        deleted_ids = []
        
        for article_number, count in duplicates:
            # Get all records for this article, ordered by creation (keep newest)
            cursor.execute("""
                SELECT id, created_at 
                FROM labor_law_sections 
                WHERE article_number = %s 
                ORDER BY created_at DESC
            """, (article_number,))
            
            records = cursor.fetchall()
            # Keep the first (most recent), delete the rest
            ids_to_delete = [r[0] for r in records[1:]]
            
            print(f"{article_number:<50} {count:<6} {len(ids_to_delete)} record(s)")
            
            total_to_delete += len(ids_to_delete)
            deleted_ids.extend(ids_to_delete)
        
        print("="*80)
        print(f"\nTotal duplicates to delete: {total_to_delete}\n")
        
        if dry_run:
            print("DRY RUN - No changes made")
            return total_to_delete
        
        # Confirm before deletion
        response = input("Continue with deletion? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled")
            return 0
        
        # Delete duplicates
        if deleted_ids:
            # Delete in batches to avoid huge query
            batch_size = 100
            for i in range(0, len(deleted_ids), batch_size):
                batch = deleted_ids[i:i+batch_size]
                placeholders = ','.join(['%s'] * len(batch))
                cursor.execute(f"DELETE FROM labor_law_sections WHERE id IN ({placeholders})", batch)
            
            conn.commit()
            print(f"\n✅ Deleted {total_to_delete} duplicate records")
            
            # Verify deletion
            cursor.execute("SELECT COUNT(*) FROM labor_law_sections")
            new_total = cursor.fetchone()[0]
            logger.info(f"New total: {new_total} records (was {new_total + total_to_delete})")
            
            return total_to_delete
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during cleanup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Clean up duplicate records in labor_law_sections table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what will be deleted without making changes'
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("DUPLICATE CLEANUP")
    print("="*80)
    
    cleanup_duplicates(dry_run=args.dry_run)
