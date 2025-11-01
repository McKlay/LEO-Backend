"""Debug script to test Supabase RPC function."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.containers import get_supabase_client, get_embeddings_adapter

async def main():
    print("Testing Supabase RPC function directly...")
    
    # Get client
    client = get_supabase_client()
    
    # Check if we have data
    result = client.table("labor_law_embeddings").select("id, content").limit(1).execute()
    print(f"\nSample document from DB:")
    if result.data:
        print(f"  ID: {result.data[0]['id']}")
        print(f"  Content preview: {result.data[0]['content'][:100]}...")
    else:
        print("  No documents found!")
        return
    
    # Generate a test embedding
    embeddings = get_embeddings_adapter()
    response = await embeddings.embed_text("13th month pay")
    test_embedding = response.embedding
    
    print(f"\nTest embedding:")
    print(f"  Dimension: {len(test_embedding)}")
    print(f"  First 5 values: {test_embedding[:5]}")
    
    # Try calling RPC function
    print(f"\nCalling match_documents RPC...")
    try:
        rpc_response = client.rpc(
            "match_documents",
            {
                "query_embedding": test_embedding,
                "match_threshold": 0.0,
                "match_count": 3,
                "filter_metadata": '{}'
            }
        ).execute()
        
        print(f"RPC response received:")
        print(f"  Data type: {type(rpc_response.data)}")
        print(f"  Data length: {len(rpc_response.data) if rpc_response.data else 0}")
        print(f"  Data: {rpc_response.data}")
        
        if rpc_response.data:
            print(f"\n  First result:")
            print(f"    Keys: {rpc_response.data[0].keys()}")
            for key, value in rpc_response.data[0].items():
                if key == 'content':
                    print(f"    {key}: {str(value)[:100]}...")
                else:
                    print(f"    {key}: {value}")
        else:
            print("\n⚠️  Empty result - trying direct SQL query...")
            # Try direct embedding similarity query via PostgREST
            # Note: This won't work via Supabase client, but shows the approach
            print("  Tip: The RPC function might need to be recreated.")
            print("  Try running: python scripts/setup_supabase.py")
        
    except Exception as e:
        print(f"❌ RPC call failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n✓ Debug complete")

if __name__ == "__main__":
    asyncio.run(main())
