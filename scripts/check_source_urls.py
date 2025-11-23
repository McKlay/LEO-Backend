"""
Quick script to check if labor_law_sources table has URLs populated.
"""

import asyncio
import os
import sys
from pathlib import Path
import psycopg2

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings

async def main():
    print("🔍 Checking labor_law_sources table for URLs...")
    print("-" * 60)
    
    # Connect directly to database
    conn = psycopg2.connect(settings.supabase_db_url)
    cursor = conn.cursor()
    
    try:
        # Check labor_law_sources table
        cursor.execute("""
            SELECT 
                id,
                source_type,
                title,
                reference,
                url
            FROM labor_law_sources
            ORDER BY source_type, reference
            LIMIT 20
        """)
        
        sources = cursor.fetchall()
        
        if not sources:
            print("⚠️  No sources found in labor_law_sources table!")
            print("\n💡 Action Required: Run the KB ingestion script to populate sources.")
            return
        
        print(f"✅ Found {len(sources)} sources (showing first 20):\n")
        
        url_count = 0
        for source in sources:
            source_id, source_type, title, reference, url = source
            has_url = "✅" if url else "❌"
            url_count += 1 if url else 0
            
            print(f"{has_url} [{source_type}] {reference}: {title}")
            if url:
                print(f"   URL: {url}")
            print()
        
        print("-" * 60)
        print(f"📊 Summary: {url_count}/{len(sources)} sources have URLs")
        
        if url_count == 0:
            print("\n⚠️  WARNING: No sources have URLs!")
            print("💡 Action Required: Update labor_law_sources table with actual URLs")
            print("   Example SQL:")
            print("   UPDATE labor_law_sources SET url = 'https://...' WHERE reference = 'PD 442';")
        elif url_count < len(sources):
            print(f"\n⚠️  WARNING: {len(sources) - url_count} sources are missing URLs")
        else:
            print("\n✅ All sources have URLs!")
        
        # Now check if sections are properly linked
        print("\n" + "=" * 60)
        print("🔗 Checking labor_law_sections linkage to sources...")
        print("-" * 60)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sections,
                COUNT(source_id) as sections_with_source,
                COUNT(DISTINCT source_id) as unique_sources
            FROM labor_law_sections
        """)
        
        stats = cursor.fetchone()
        total, with_source, unique = stats
        
        print(f"📊 Section Statistics:")
        print(f"   Total sections: {total}")
        print(f"   Sections with source_id: {with_source} ({100*with_source/total:.1f}%)")
        print(f"   Unique sources referenced: {unique}")
        
        if with_source < total:
            print(f"\n⚠️  WARNING: {total - with_source} sections have no source_id!")
            print("💡 This means some citations won't have source URLs")
        
    finally:
        cursor.close()
        conn.close()
    
    print("\n✅ Check complete!")

if __name__ == "__main__":
    asyncio.run(main())
