"""
Quick test to verify Supabase connection works
"""
import os
import asyncio
from dotenv import load_dotenv

async def test_supabase():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    print(f"Testing connection to: {url}")
    print(f"Anon key present: {bool(anon_key)}")
    
    try:
        from supabase import create_client, Client
        
        # Test client creation
        client: Client = create_client(url, anon_key)
        print("✅ Client created successfully")
        
        # Test anonymous sign-in
        response = client.auth.sign_in_anonymously()
        print(f"✅ Anonymous auth successful: {response.user.id if response.user else 'No user'}")
        
        # Test database query
        result = client.table("labor_law_embeddings").select("id").limit(1).execute()
        print(f"✅ Database query successful: {len(result.data)} rows")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_supabase())
    exit(0 if success else 1)
