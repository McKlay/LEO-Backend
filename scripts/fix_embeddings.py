"""Fix embedding column type in existing data."""
import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def fix_embeddings():
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    print("Fetching all rows...")
    result = client.table('labor_law_embeddings').select('id,content,embedding,metadata').execute()
    print(f"Found {len(result.data)} rows")
    
    for i, row in enumerate(result.data):
        row_id = row['id']
        embedding_value = row['embedding']
        
        print(f"\nRow {i+1}: {row_id[:40]}...")
        print(f"  Embedding type: {type(embedding_value)}")
        
        # If embedding is a string, parse it to list
        if isinstance(embedding_value, str):
            print(f"  Converting string to list...")
            try:
                # Parse the string representation
                embedding_list = json.loads(embedding_value)
                print(f"  Parsed dimension: {len(embedding_list)}")
                
                # Update the row with the proper embedding
                # Note: We need to use the PostgREST cast syntax
                update_result = client.table('labor_law_embeddings')\
                    .update({'embedding': embedding_list})\
                    .eq('id', row_id)\
                    .execute()
                
                print(f"  ✓ Updated successfully")
                
            except json.JSONDecodeError as e:
                print(f"  ✗ Failed to parse: {e}")
        else:
            print(f"  Already correct type")
    
    print("\n" + "="*60)
    print("Verification: Testing search with updated data...")
    
    # Test search
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="What is the 13th month pay requirement?"
    )
    query_vector = response.data[0].embedding
    
    result = client.rpc('match_documents', {
        'query_embedding': query_vector,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    
    print(f"Search results: {len(result.data)}")
    if result.data:
        for j, r in enumerate(result.data):
            print(f"  Result {j+1}: similarity={r.get('similarity'):.4f}, content={r.get('content', '')[:60]}...")
    else:
        print("  Still no results. Checking data types again...")
        check = client.table('labor_law_embeddings').select('id,embedding').limit(1).execute()
        if check.data:
            print(f"  Embedding type after update: {type(check.data[0]['embedding'])}")
            print(f"  Value: {str(check.data[0]['embedding'])[:100]}...")

if __name__ == "__main__":
    fix_embeddings()
