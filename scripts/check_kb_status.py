"""
Verify knowledge base has content for testing
"""
import os
import asyncio
from dotenv import load_dotenv

async def check_kb():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    from supabase import create_client
    client = create_client(url, anon_key)
    
    # Sign in
    client.auth.sign_in_anonymously()
    
    # Check total embeddings
    result = client.table("labor_law_embeddings").select("id", count="exact").execute()
    print(f"📊 Total embeddings in KB: {result.count}")
    
    # Check sample content
    sample = client.table("labor_law_embeddings").select("*").limit(5).execute()
    print(f"\n📝 Sample entries:")
    for i, row in enumerate(sample.data, 1):
        content = row.get('content', '')[:100]
        metadata = row.get('metadata', {})
        print(f"  {i}. {content}...")
        print(f"     Source: {metadata.get('source', 'N/A')}, Article: {metadata.get('article', 'N/A')}")
    
    # Check if we have 13th month pay content
    print(f"\n🔍 Searching for '13th month pay' content...")
    search = client.table("labor_law_embeddings").select("*").ilike("content", "%13th month%").limit(3).execute()
    print(f"Found {len(search.data)} matches")
    for row in search.data:
        print(f"  - {row.get('content', '')[:150]}...")
    
    return result.count > 0

if __name__ == "__main__":
    has_data = asyncio.run(check_kb())
    if has_data:
        print("\n✅ Knowledge base is ready for testing")
    else:
        print("\n❌ Knowledge base is empty - need to ingest data first")
    exit(0 if has_data else 1)
