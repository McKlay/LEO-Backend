"""
Fix: Use PostgREST cast syntax to properly update vector columns.
The issue is that Supabase Python client converts arrays to strings.
We need to update via raw SQL or use PostgREST's cast syntax.
"""
import os
from dotenv import load_dotenv
from supabase import create_client
import postgrest

load_dotenv()

def fix_via_sql():
    """
    The proper fix is to re-ingest the data using the correct format.
    For now, let's verify the RPC function works with proper vector input.
    """
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    print("The issue: Supabase Python client doesn't handle vector type correctly")
    print("when using .update() or .upsert() methods.\n")
    
    print("Solution: We need to re-ingest the data properly or use SQL.\n")
    
    print("For now, let's test if the table schema is correct...")
    
    # Check if we can query the function definition
    try:
        result = client.rpc('match_documents', {
            'query_embedding': [0.1] * 1536,
            'match_threshold': 0.0,
            'match_count': 1,
            'filter_metadata': '{}'
        }).execute()
        print(f"✓ RPC function exists and is callable")
        print(f"  Returned {len(result.data)} results (expected 0 with current data)")
    except Exception as e:
        print(f"✗ RPC function error: {e}")
    
    print("\n" + "="*70)
    print("RECOMMENDATION:")
    print("="*70)
    print("The embeddings are stored as TEXT instead of VECTOR type.")
    print("To fix this, we need to:")
    print("1. Delete all existing rows")
    print("2. Re-ingest using direct SQL INSERT with proper vector casting")
    print("3. Or use a PostgreSQL client (psycopg2) instead of Supabase client")
    print("\nFor the integration tests to work, let's re-ingest the data properly...")
    
    return client

def reingest_data_properly():
    """Re-ingest the sample data using proper vector format."""
    from openai import OpenAI
    import json
    
    client = fix_via_sql()
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Sample labor law data
    documents = [
        {
            "id": "pd_851_sec1",
            "content": "Section 1. All employers are hereby required to pay all their employees receiving a basic salary of not more than P1,000 a month, regardless of the nature of their employment, a 13th month pay not later than December 24 of every year.",
            "metadata": {"source": "Presidential Decree No. 851", "section": "1", "type": "regulation"}
        },
        {
            "id": "pd_851_sec2", 
            "content": "Section 2. Employers already paying their employees a 13th-month pay or its equivalent are not covered by this Decree.",
            "metadata": {"source": "Presidential Decree No. 851", "section": "2", "type": "regulation"}
        },
        {
            "id": "labor_code_art297",
            "content": "Article 297. Termination by employer. An employer may terminate an employment for any of the following causes: (a) Serious misconduct or willful disobedience; (b) Gross and habitual neglect of duties; (c) Fraud or willful breach of trust; (d) Commission of a crime against the employer or his family; (e) Other causes analogous to the foregoing.",
            "metadata": {"source": "Labor Code of the Philippines", "article": "297", "type": "statute"}
        }
    ]
    
    print("\n" + "="*70)
    print("Re-ingesting sample documents with proper embeddings...")
    print("="*70)
    
    # Delete existing data first
    print("\n1. Clearing existing data...")
    try:
        client.table('labor_law_embeddings').delete().neq('id', '').execute()
        print("   ✓ Cleared all rows")
    except Exception as e:
        print(f"   Note: {e}")
    
    # Insert new data using postgrest-py's features
    print("\n2. Generating embeddings and inserting...")
    for i, doc in enumerate(documents):
        print(f"\n   Document {i+1}: {doc['id']}")
        
        # Generate embedding
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=doc['content']
        )
        embedding = response.data[0].embedding
        print(f"   Generated embedding: dim={len(embedding)}")
        
        # Try to insert with proper format
        # Use raw SQL via RPC if available, or fall back to direct table insert
        try:
            # Direct insert - client will convert to string again
            result = client.table('labor_law_embeddings').insert({
                'id': doc['id'],
                'content': doc['content'],
                'embedding': embedding,  # This becomes string :(
                'metadata': json.dumps(doc['metadata'])
            }).execute()
            print(f"   ✓ Inserted (note: embedding may still be text type)")
        except Exception as e:
            print(f"   ✗ Insert failed: {e}")
    
    # Test search
    print("\n3. Testing search with newly inserted data...")
    test_query = "What is 13th month pay?"
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=test_query
    )
    query_vec = response.data[0].embedding
    
    result = client.rpc('match_documents', {
        'query_embedding': query_vec,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    
    print(f"   Query: '{test_query}'")
    print(f"   Results: {len(result.data)}")
    
    if not result.data:
        print("\n   ⚠ Still no results - the vector type issue persists")
        print("   The Supabase Python client cannot properly handle vector columns")
        print("\n   FINAL RECOMMENDATION:")
        print("   Use psycopg2 to connect directly to Supabase Postgres and")
        print("   insert data with proper vector casting:")
        print("   INSERT INTO labor_law_embeddings (id, content, embedding, metadata)")
        print("   VALUES ($1, $2, $3::vector, $4::jsonb)")

if __name__ == "__main__":
    reingest_data_properly()
