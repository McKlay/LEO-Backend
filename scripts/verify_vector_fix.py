"""Verify the vector search fix is working."""
import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

load_dotenv()

def verify_fix():
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    print("Testing vector search after SQL fix...")
    print("="*70)
    
    # Generate query embedding
    response = openai_client.embeddings.create(
        model='text-embedding-3-small',
        input='What is 13th month pay?'
    )
    query_vec = response.data[0].embedding
    
    # Search
    result = client.rpc('match_documents', {
        'query_embedding': query_vec,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    
    if len(result.data) > 0:
        print(f"✅ SUCCESS! Vector search is working!")
        print(f"\nFound {len(result.data)} results:\n")
        for i, r in enumerate(result.data):
            print(f"{i+1}. Similarity: {r.get('similarity', 0):.4f}")
            print(f"   Content: {r.get('content', '')[:80]}...")
            print()
        
        print("="*70)
        print("✅ Ready to run integration tests!")
        print("="*70)
        return True
    else:
        print("❌ Still no results. Please check the SQL execution.")
        return False

if __name__ == "__main__":
    verify_fix()
