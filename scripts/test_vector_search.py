"""Test vector search to diagnose why no results are returned."""
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def test_search():
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    # 1. Check if table has data
    print("1. Checking table data...")
    result = client.table('labor_law_embeddings').select('id,content,metadata').limit(3).execute()
    print(f"   Row count: {len(result.data)}")
    for i, row in enumerate(result.data):
        print(f"   Row {i+1}: ID={row['id'][:30]}..., Content={row['content'][:80]}...")
    
    # 2. Check table schema
    print("\n2. Checking if embedding column exists...")
    result = client.table('labor_law_embeddings').select('id,embedding').limit(1).execute()
    if result.data:
        embedding = result.data[0].get('embedding')
        print(f"   Embedding type: {type(embedding)}")
        if isinstance(embedding, list):
            print(f"   Embedding dimension: {len(embedding)}")
        else:
            print(f"   Embedding value: {str(embedding)[:100]}...")
    
    # 3. Test RPC function with zero vector
    print("\n3. Testing match_documents RPC with zero vector...")
    result = client.rpc('match_documents', {
        'query_embedding': [0.0] * 1536,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    print(f"   Results: {len(result.data)}")
    if result.data:
        print(f"   First result: {result.data[0]}")
    
    # 4. Test RPC function with small random vector
    print("\n4. Testing match_documents RPC with random vector...")
    import random
    random_vec = [random.random() for _ in range(1536)]
    result = client.rpc('match_documents', {
        'query_embedding': random_vec,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    print(f"   Results: {len(result.data)}")
    if result.data:
        print(f"   First result similarity: {result.data[0].get('similarity')}")
    
    # 5. Test with actual query embedding
    print("\n5. Testing with real OpenAI embedding...")
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="What is the 13th month pay requirement in the Philippines?"
    )
    query_vector = response.data[0].embedding
    print(f"   Generated embedding dimension: {len(query_vector)}")
    
    result = client.rpc('match_documents', {
        'query_embedding': query_vector,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    print(f"   Results: {len(result.data)}")
    if result.data:
        for i, r in enumerate(result.data):
            print(f"   Result {i+1}: similarity={r.get('similarity'):.4f}, content={r.get('content', '')[:60]}...")

if __name__ == "__main__":
    asyncio.run(test_search())
