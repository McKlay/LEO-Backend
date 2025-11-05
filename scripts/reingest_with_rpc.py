"""
Re-insert data using RPC function that properly handles vector types.
First, you need to create the insert_embedding RPC function in Supabase SQL Editor.
"""
import os
import json
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

load_dotenv()

def reingest_with_rpc():
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    print("="*70)
    print("STEP 1: Create RPC Function in Supabase")
    print("="*70)
    print("\nPlease run the SQL in: scripts/create_insert_rpc.sql")
    print("This creates a function that properly handles vector types.")
    print("\nPress Enter when you've created the function...")
    input()
    
    print("\n="*70)
    print("STEP 2: Re-inserting data using RPC function")
    print("="*70)
    
    # Sample documents
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
        },
        {
            "id": "labor_code_art298",
            "content": "Article 298. Notice of termination. The employer shall serve written notice upon the employee at least 30 days in advance of termination.",
            "metadata": {"source": "Labor Code of the Philippines", "article": "298", "type": "statute"}
        },
        {
            "id": "labor_code_art293",
            "content": "Article 293. Separation pay. Any employee dismissed from work shall be entitled to separation pay equivalent to at least one month salary or at least one month salary for every year of service, whichever is higher.",
            "metadata": {"source": "Labor Code of the Philippines", "article": "293", "type": "statute"}
        }
    ]
    
    # Clear existing data
    print("\n1. Clearing existing data...")
    try:
        client.table('labor_law_embeddings').delete().neq('id', 'dummy').execute()
        print("   ✓ Cleared")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # Insert using RPC
    print("\n2. Inserting documents...")
    for i, doc in enumerate(documents):
        print(f"\n   Document {i+1}: {doc['id']}")
        
        # Generate embedding
        response = openai_client.embeddings.create(
            model='text-embedding-3-small',
            input=doc['content']
        )
        embedding = response.data[0].embedding
        print(f"   Generated embedding: dim={len(embedding)}")
        
        # Insert using RPC
        try:
            result = client.rpc('insert_embedding', {
                'p_id': doc['id'],
                'p_content': doc['content'],
                'p_embedding_array': embedding,
                'p_metadata': doc['metadata']
            }).execute()
            print(f"   ✓ Inserted via RPC")
        except Exception as e:
            print(f"   ✗ RPC insert failed: {e}")
            print(f"   Make sure you've created the insert_embedding function!")
            return False
    
    # Verify
    print("\n3. Verifying vector search...")
    response = openai_client.embeddings.create(
        model='text-embedding-3-small',
        input='What is 13th month pay?'
    )
    query_vec = response.data[0].embedding
    
    result = client.rpc('match_documents', {
        'query_embedding': query_vec,
        'match_threshold': 0.0,
        'match_count': 5,
        'filter_metadata': '{}'
    }).execute()
    
    print(f"   Search results: {len(result.data)}")
    if result.data:
        for j, r in enumerate(result.data):
            print(f"   {j+1}. Similarity: {r.get('similarity'):.4f} - {r.get('content')[:60]}...")
        
        print("\n" + "="*70)
        print("✅ SUCCESS! Vector search is working!")
        print("="*70)
        return True
    else:
        print("\n   ❌ Still no results")
        return False

if __name__ == "__main__":
    reingest_with_rpc()
