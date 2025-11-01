"""Test match_documents directly with psycopg2."""
import asyncio
import psycopg2
import os
from dotenv import load_dotenv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import get_embeddings_adapter

load_dotenv()

async def main():
    # Get test embedding
    embeddings = get_embeddings_adapter()
    response = await embeddings.embed_text("13th month pay")
    test_embedding = response.embedding
    
    print(f"Generated embedding (dimension: {len(test_embedding)})")
    
    # Connect to database
    conn = psycopg2.connect(os.getenv('SUPABASE_DB_URL'))
    cur = conn.cursor()
    
    # First check the data
    cur.execute("SELECT COUNT(*) FROM labor_law_embeddings")
    count = cur.fetchone()[0]
    print(f"\nTotal documents in DB: {count}")
    
    # Try calling the function directly
    print("\nCalling match_documents function...")
    
    # Convert embedding to PostgreSQL array format
    embedding_str = '[' + ','.join(str(x) for x in test_embedding) + ']'
    
    cur.execute("""
        SELECT * FROM match_documents(
            %s::vector,
            0.0::float,
            3::int,
            '{}'::jsonb
        )
    """, (embedding_str,))
    
    results = cur.fetchall()
    print(f"Results: {len(results)} rows")
    
    if results:
        for i, row in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  ID: {row[0]}")
            print(f"  Content: {row[1][:100]}...")
            print(f"  Similarity: {row[3]}")
    else:
        print("No results returned!")
        
        # Try a direct similarity query
        print("\nTrying direct similarity query...")
        cur.execute("""
            SELECT 
                id,
                substring(content from 1 for 100) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM labor_law_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        """, (embedding_str, embedding_str))
        
        direct_results = cur.fetchall()
        print(f"Direct query results: {len(direct_results)} rows")
        
        for i, row in enumerate(direct_results, 1):
            print(f"\nResult {i}:")
            print(f"  ID: {row[0]}")
            print(f"  Content: {row[1]}...")
            print(f"  Similarity: {row[2]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
