"""
Debug vector search issue
"""
import os
import asyncio
import numpy as np
from dotenv import load_dotenv

async def debug_vector_search():
    load_dotenv()
    
    from supabase import create_client
    from adapters.embeddings.openai_embed import OpenAIEmbeddings
    
    # Setup clients
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    client = create_client(url, anon_key)
    client.auth.sign_in_anonymously()
    
    embedder = OpenAIEmbeddings()
    
    # Test query
    query = "What is 13th month pay?"
    print(f"🔍 Query: {query}")
    
    # Generate embedding
    query_embedding = await embedder.embed_text(query)
    print(f"✅ Generated embedding: {len(query_embedding)} dimensions")
    print(f"   Sample values: {query_embedding[:5]}")
    
    # Check stored embeddings
    print(f"\n📊 Checking stored embeddings...")
    result = client.table("labor_law_embeddings").select("id, content, embedding").limit(1).execute()
    
    if result.data:
        stored = result.data[0]
        print(f"✅ Found stored embedding")
        print(f"   Content: {stored['content'][:100]}")
        print(f"   Type: {type(stored['embedding'])}")
        
        # Check if it's a valid vector
        if isinstance(stored['embedding'], str):
            print(f"   ⚠️  Embedding is STRING: {stored['embedding'][:100]}")
        elif isinstance(stored['embedding'], list):
            print(f"   ✅ Embedding is LIST: {len(stored['embedding'])} dimensions")
        else:
            print(f"   ❌ Unexpected type: {type(stored['embedding'])}")
    
    # Try RPC function search
    print(f"\n🔍 Testing RPC function...")
    try:
        rpc_result = client.rpc(
            "match_embeddings",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.5,
                "match_count": 5
            }
        ).execute()
        print(f"✅ RPC returned {len(rpc_result.data)} results")
        for r in rpc_result.data:
            print(f"   - Similarity: {r.get('similarity', 'N/A')}, Content: {r.get('content', '')[:80]}")
    except Exception as e:
        print(f"❌ RPC failed: {e}")
    
    # Try direct SQL similarity search
    print(f"\n🔍 Testing direct vector comparison...")
    try:
        # Convert embedding to PostgreSQL array format
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        sql_result = client.rpc(
            "match_labor_law_embeddings",
            {
                "query_embedding": query_embedding,
                "similarity_threshold": 0.1,  # Lower threshold
                "match_count": 5
            }
        ).execute()
        print(f"✅ SQL search returned {len(sql_result.data)} results")
        for r in sql_result.data:
            print(f"   - Similarity: {r.get('similarity', 'N/A')}, Content: {r.get('content', '')[:80]}")
    except Exception as e:
        print(f"❌ Direct search failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_vector_search())
