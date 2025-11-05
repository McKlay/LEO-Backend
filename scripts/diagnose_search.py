"""
Diagnose why vector search returns 0 results after RPC insertion
"""
import asyncio
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

async def diagnose():
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY")
    )
    
    print("=" * 70)
    print("DIAGNOSIS: Vector Search Issue")
    print("=" * 70)
    
    # 1. Check row count
    result = client.table('labor_law_embeddings').select('id, content', count='exact').execute()
    print(f"\n1. Row count: {result.count}")
    
    # 2. Check if embeddings are actually stored
    result = client.table('labor_law_embeddings').select('id, content, embedding').limit(1).execute()
    if result.data:
        row = result.data[0]
        print(f"\n2. Sample row:")
        print(f"   ID: {row['id']}")
        print(f"   Content: {row['content'][:100]}...")
        print(f"   Embedding type: {type(row['embedding'])}")
        if isinstance(row['embedding'], str):
            print(f"   ❌ STILL TEXT! Length: {len(row['embedding'])}")
        else:
            print(f"   ✓ Embedding is proper type: {type(row['embedding'])}")
            print(f"   Dimension: {len(row['embedding']) if hasattr(row['embedding'], '__len__') else 'N/A'}")
    
    # 3. Try direct SQL query for embedding column type
    print("\n3. Checking column type in database...")
    try:
        # Use raw SQL to check column type
        result = client.rpc('sql_query', {
            'query': """
                SELECT 
                    column_name, 
                    data_type, 
                    udt_name
                FROM information_schema.columns 
                WHERE table_name = 'labor_law_embeddings' 
                AND column_name = 'embedding'
            """
        }).execute()
        print(f"   SQL query result: {result}")
    except Exception as e:
        print(f"   Cannot query schema directly: {e}")
    
    # 4. Generate test embedding
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    print("\n4. Generating test query embedding...")
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="What is 13th month pay?",
        dimensions=1536
    )
    query_embedding = response.data[0].embedding
    print(f"   ✓ Generated embedding: dim={len(query_embedding)}")
    
    # 5. Try RPC search with explicit parameters
    print("\n5. Testing match_documents RPC...")
    try:
        result = client.rpc('match_documents', {
            'query_embedding': query_embedding,
            'match_threshold': 0.1,  # Very low threshold
            'match_count': 10
        }).execute()
        print(f"   Results: {len(result.data)}")
        if result.data:
            print(f"   ✓ FOUND RESULTS!")
            for i, doc in enumerate(result.data[:3]):
                print(f"   {i+1}. {doc.get('id')}: similarity={doc.get('similarity')}")
        else:
            print(f"   ❌ Still 0 results with threshold=0.1")
    except Exception as e:
        print(f"   ❌ RPC Error: {e}")
    
    # 6. Check if match_documents function exists
    print("\n6. Verifying match_documents function...")
    try:
        # Try to get function definition
        result = client.rpc('match_documents', {
            'query_embedding': [0.0] * 1536,  # Dummy embedding
            'match_threshold': 0.9,
            'match_count': 1
        }).execute()
        print(f"   ✓ Function exists (returned {len(result.data)} results)")
    except Exception as e:
        print(f"   ❌ Function error: {e}")
        print(f"\n   This might mean match_documents needs to be recreated!")

if __name__ == "__main__":
    asyncio.run(diagnose())
