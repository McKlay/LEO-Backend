"""
Quick script to check what's in the database.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import get_supabase_client
from core.config import settings


async def check_database():
    """Check what's in the database."""
    
    client = get_supabase_client()
    
    print("\n" + "="*80)
    print("DATABASE INVENTORY CHECK")
    print("="*80)
    
    # Check sections
    try:
        sections_response = client.table('labor_law_sections')\
            .select('id, article_number, article_title, source_id')\
            .limit(10)\
            .execute()
        
        sections_count = len(sections_response.data)
        print(f"\n✓ labor_law_sections: {sections_count} rows (showing first 10)")
        
        for idx, row in enumerate(sections_response.data, 1):
            print(f"  {idx}. {row.get('article_number', 'N/A'):30} | {row.get('article_title', 'N/A')[:50]}")
    
    except Exception as e:
        print(f"\n❌ Error querying sections: {str(e)}")
    
    # Check chunks
    try:
        chunks_response = client.table('labor_law_chunks')\
            .select('id, section_id, chunk_index, summary')\
            .limit(10)\
            .execute()
        
        chunks_count = len(chunks_response.data)
        print(f"\n✓ labor_law_chunks: {chunks_count} rows (showing first 10)")
        
        for idx, row in enumerate(chunks_response.data, 1):
            print(f"  {idx}. Chunk {row.get('chunk_index', 'N/A')} | Summary: {row.get('summary', 'N/A')[:60]}")
    
    except Exception as e:
        print(f"\n❌ Error querying chunks: {str(e)}")
    
    # Check sources
    try:
        sources_response = client.table('labor_law_sources')\
            .select('id, reference, title, source_type')\
            .execute()
        
        sources_count = len(sources_response.data)
        print(f"\n✓ labor_law_sources: {sources_count} rows")
        
        for idx, row in enumerate(sources_response.data, 1):
            print(f"  {idx}. [{row.get('source_type', 'N/A'):10}] {row.get('reference', 'N/A'):15} | {row.get('title', 'N/A')[:50]}")
    
    except Exception as e:
        print(f"\n❌ Error querying sources: {str(e)}")
    
    # Get total counts
    try:
        sections_total = client.table('labor_law_sections').select('id', count='exact').execute()
        chunks_total = client.table('labor_law_chunks').select('id', count='exact').execute()
        
        print(f"\n" + "="*80)
        print(f"TOTALS:")
        print(f"  - Sections: {sections_total.count}")
        print(f"  - Chunks: {chunks_total.count}")
        print(f"="*80 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error getting totals: {str(e)}")


if __name__ == "__main__":
    asyncio.run(check_database())
