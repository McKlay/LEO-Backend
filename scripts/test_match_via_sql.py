"""
Test match_documents function directly via SQL
"""
import os
import sys
import asyncio
import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_via_sql():
    load_dotenv()
    
    from adapters.embeddings.openai_embed import OpenAIEmbeddings
    
    # Generate embedding
    embedder = OpenAIEmbeddings()
    query = "What is 13th month pay?"
    print(f"🔍 Query: {query}")
    
    embedding_response = await embedder.embed_text(query)
    embedding = embedding_response.embedding
    print(f"✅ Generated embedding: {len(embedding)} dimensions")
    
    # Connect to DB
    db_url = os.getenv("SUPABASE_DB_URL")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Call match_documents via SQL
    print(f"\n📡 Calling match_documents via SQL...")
    
    # Convert embedding to PostgreSQL array string
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    
    cursor.execute("""
        SELECT * FROM match_documents(
            %s::vector,
            0.0::float,
            5::int,
            '{}'::jsonb
        )
    """, (embedding_str,))
    
    results = cursor.fetchall()
    print(f"✅ SQL returned {len(results)} results")
    
    for row in results:
        print(f"   - Similarity: {row[3]:.4f} - {row[1][:80]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(test_via_sql())
