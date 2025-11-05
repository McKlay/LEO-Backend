"""
Debug exactly what the adapter is doing
"""
import os
import sys
import asyncio
import json
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_adapter_style():
    load_dotenv()
    
    from adapters.embeddings.openai_embed import OpenAIEmbeddings
    
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_KEY")  # Try service_role key instead
    
    client = create_client(url, service_key)
    # Don't sign in - use anon key directly
    # response = client.auth.sign_in_anonymously()
    # print(f"✅ Signed in: {response.user.id if response.user else 'No user'}")
    
    # Generate embedding exactly like the adapter
    embedder = OpenAIEmbeddings()
    query = "What is 13th month pay?"
    print(f"\n🔍 Query: {query}")
    
    embedding_response = await embedder.embed_text(query)
    query_embedding = embedding_response.embedding
    print(f"✅ Embedding: {len(query_embedding)} dimensions")
    
    # Call RPC exactly like the adapter (with string conversion)
    threshold = 0.3
    limit = 5
    filters = None
    
    # Convert to string format for PostgreSQL vector type
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    rpc_params = {
        "query_embedding": embedding_str,
        "match_threshold": threshold or 0.0,
        "match_count": limit,
        "filter_metadata": json.dumps(filters) if filters else '{}'
    }
    
    print(f"\n📡 Calling RPC with:")
    print(f"   - threshold: {rpc_params['match_threshold']}")
    print(f"   - count: {rpc_params['match_count']}")
    print(f"   - filter: {rpc_params['filter_metadata']}")
    print(f"   - embedding format: string (length {len(embedding_str)} chars)")
    
    try:
        response = client.rpc(
            "match_documents",
            rpc_params
        ).execute()
        
        print(f"\n✅ RPC successful: {len(response.data)} results")
        
        for i, row in enumerate(response.data, 1):
            similarity = row.get("similarity", 0.0)
            content = row.get("content", "")[:80]
            print(f"{i}. Similarity: {similarity:.4f} - {content}")
            
        if not response.data:
            print(f"\n⚠️  No results! Let's check why...")
            
            # Check raw query without threshold
            print(f"\n🔍 Trying without threshold...")
            response2 = client.rpc(
                "match_documents",
                {
                    "query_embedding": embedding_str,  # Use string format
                    "match_threshold": 0.0,
                    "match_count": 5,
                    "filter_metadata": '{}'
                }
            ).execute()
            
            print(f"Without threshold: {len(response2.data)} results")
            for row in response2.data[:3]:
                print(f"  - Similarity: {row.get('similarity', 0):.4f}")
        
    except Exception as e:
        print(f"❌ RPC failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_adapter_style())
