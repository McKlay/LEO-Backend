"""
Apply Supabase schema in smaller steps to avoid memory limits
"""
import os
import asyncio
from dotenv import load_dotenv
import psycopg2

async def setup():
    load_dotenv()
    
    db_url = os.getenv("SUPABASE_DB_URL")
    print(f"📡 Connecting to Supabase PostgreSQL...")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    steps = [
        ("Enable vector extension", "CREATE EXTENSION IF NOT EXISTS vector;"),
        
        ("Create table", """
CREATE TABLE IF NOT EXISTS labor_law_embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);
        """),
        
        ("Create match_documents function", """
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 10,
    filter_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        labor_law_embeddings.id,
        labor_law_embeddings.content,
        labor_law_embeddings.metadata,
        1 - (labor_law_embeddings.embedding <=> query_embedding) as similarity
    FROM labor_law_embeddings
    WHERE 
        (1 - (labor_law_embeddings.embedding <=> query_embedding)) >= match_threshold
        AND (
            filter_metadata = '{}'::jsonb 
            OR labor_law_embeddings.metadata @> filter_metadata
        )
    ORDER BY labor_law_embeddings.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
        """),
    ]
    
    for step_name, sql in steps:
        try:
            print(f"📝 {step_name}...")
            cursor.execute(sql)
            conn.commit()
            print(f"   ✅ Done")
        except Exception as e:
            print(f"   ⚠️  {e}")
    
    # Test match_documents
    print(f"\n🔍 Testing match_documents function...")
    try:
        test_embedding = [0.1] * 1536
        cursor.execute("""
            SELECT * FROM match_documents(%s::vector, 0.0, 5, '{}'::jsonb)
        """, ([test_embedding],))
        results = cursor.fetchall()
        print(f"✅ Function works: returned {len(results)} results")
    except Exception as e:
        print(f"❌ Function test failed: {e}")
    
    cursor.close()
    conn.close()
    print(f"\n✅ Setup complete!")

if __name__ == "__main__":
    asyncio.run(setup())
