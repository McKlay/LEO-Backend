"""
Apply Supabase schema and test vector search
"""
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client
import psycopg2

async def setup_and_test():
    load_dotenv()
    
    # Read schema file
    with open("infra/supabase/schema.sql", "r") as f:
        schema_sql = f.read()
    
    # Connect to Supabase PostgreSQL directly
    db_url = os.getenv("SUPABASE_DB_URL")
    print(f"📡 Connecting to Supabase PostgreSQL...")
    
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Execute schema
        print(f"📝 Applying schema...")
        cursor.execute(schema_sql)
        conn.commit()
        print(f"✅ Schema applied successfully")
        
        # Test that match_documents function exists
        cursor.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_name = 'match_documents'
        """)
        result = cursor.fetchone()
        if result:
            print(f"✅ match_documents function exists")
        else:
            print(f"❌ match_documents function NOT found")
        
        cursor.close()
        conn.close()
        
        # Now test search with Supabase client
        print(f"\n🔍 Testing vector search...")
        url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        client = create_client(url, anon_key)
        client.auth.sign_in_anonymously()
        
        # Generate a test embedding (fake for now)
        test_embedding = [0.1] * 1536
        
        result = client.rpc(
            "match_documents",
            {
                "query_embedding": test_embedding,
                "match_threshold": 0.0,
                "match_count": 5
            }
        ).execute()
        
        print(f"✅ RPC call successful: {len(result.data)} results")
        for r in result.data:
            print(f"   - {r.get('content', '')[:80]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(setup_and_test())
