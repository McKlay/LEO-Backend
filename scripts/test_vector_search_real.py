"""
Test vector search with actual embeddings
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from supabase import create_client

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_search():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    from adapters.embeddings.openai_embed import OpenAIEmbeddings
    
    client = create_client(url, anon_key)
    client.auth.sign_in_anonymously()
    
    embedder = OpenAIEmbeddings()
    
    # Generate real embedding
    query = "What is 13th month pay?"
    print(f"🔍 Query: {query}")
    embedding_response = await embedder.embed_text(query)
    embedding = embedding_response.embedding
    print(f"✅ Generated embedding: {len(embedding)} dimensions")
    
    # Test RPC call
    print(f"\n📡 Calling match_documents RPC...")
    try:
        result = client.rpc(
            "match_documents",
            {
                "query_embedding": embedding,
                "match_threshold": 0.0,  # No threshold for debugging
                "match_count": 5,
                "filter_metadata": {}
            }
        ).execute()
        
        print(f"✅ RPC successful: {len(result.data)} results")
        
        if result.data:
            for i, r in enumerate(result.data, 1):
                print(f"\n{i}. Similarity: {r.get('similarity', 0):.4f}")
                print(f"   Content: {r.get('content', '')[:100]}")
                print(f"   Metadata: {r.get('metadata', {})}")
        else:
            print(f"\n⚠️  No results returned")
            print(f"   This means:")
            print(f"   1. KB might be empty, OR")
            print(f"   2. Embeddings in DB might be wrong format, OR")
            print(f"   3. Similarity scores all below threshold")
            
            # Check if KB has data
            check = client.table("labor_law_embeddings").select("id, content").limit(3).execute()
            print(f"\n📊 KB has {len(check.data)} entries")
            for entry in check.data:
                print(f"   - {entry.get('content', '')[:80]}")
        
    except Exception as e:
        print(f"❌ RPC failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search())
