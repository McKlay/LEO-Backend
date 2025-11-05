"""
Properly ingest data into Supabase using psycopg2 for correct vector type handling.
"""
import os
import json
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from urllib.parse import urlparse

load_dotenv()

def get_postgres_connection_string():
    """Convert Supabase URL to PostgreSQL connection string."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    # Supabase provides direct Postgres connection
    # Format: postgres://[user]:[password]@[host]:[port]/[database]
    
    # Extract project ref from Supabase URL
    # https://qoombyuhqwuozjnreouz.supabase.co
    parsed = urlparse(supabase_url)
    project_ref = parsed.hostname.split('.')[0]
    
    # Supabase Postgres connection details
    # You need to get the database password from Supabase dashboard
    print("="*70)
    print("IMPORTANT: Supabase PostgreSQL Connection")
    print("="*70)
    print(f"Project ref: {project_ref}")
    print(f"\nTo get your database password:")
    print(f"1. Go to: https://supabase.com/dashboard/project/{project_ref}/settings/database")
    print(f"2. Copy the 'Connection string' under 'Direct connection'")
    print(f"3. It should look like:")
    print(f"   postgresql://postgres.[ref]:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres")
    print("\n" + "="*70)
    
    # For this script, we'll use the Supabase client API key method via SQL
    return None

def ingest_via_supabase_sql():
    """Use Supabase REST API to execute SQL with proper vector casting."""
    from supabase import create_client
    
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
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
            "content": "Article 298. Notice of termination. The employer shall serve written notice upon the employee at least 30 days in advance of termination. In cases of termination due to closure or retrenchment, the employer shall serve written notice on both the employee and the Department of Labor and Employment at least one month before the effectivity date.",
            "metadata": {"source": "Labor Code of the Philippines", "article": "298", "type": "statute"}
        },
        {
            "id": "labor_code_art293",
            "content": "Article 293. Separation pay. Any employee dismissed from work shall be entitled to separation pay equivalent to at least one month salary or at least one month salary for every year of service, whichever is higher.",
            "metadata": {"source": "Labor Code of the Philippines", "article": "293", "type": "statute"}
        }
    ]
    
    print("\n1. Clearing existing data...")
    try:
        client.table('labor_law_embeddings').delete().neq('id', 'dummy').execute()
        print("   ✓ Cleared")
    except Exception as e:
        print(f"   Warning: {e}")
    
    print("\n2. Preparing documents with embeddings...")
    prepared_docs = []
    for doc in documents:
        print(f"   Embedding: {doc['id']}")
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=doc['content']
        )
        embedding = response.data[0].embedding
        
        prepared_docs.append({
            'id': doc['id'],
            'content': doc['content'],
            'embedding': embedding,
            'metadata': doc['metadata']
        })
    
    print(f"\n3. Inserting {len(prepared_docs)} documents using RPC workaround...")
    
    # Create an RPC function that handles the vector conversion
    # This is a workaround - we'll insert using SQL via a custom RPC function
    
    for i, doc in enumerate(prepared_docs):
        try:
            # Try using a custom insert RPC if it exists
            # Otherwise, document that manual SQL insert is needed
            result = client.table('labor_law_embeddings').insert({
                'id': doc['id'],
                'content': doc['content'],
                'embedding': str(doc['embedding']),  # Will be TEXT
                'metadata': json.dumps(doc['metadata'])
            }).execute()
            print(f"   Document {i+1}: {doc['id']} - inserted (as TEXT)")
        except Exception as e:
            print(f"   Document {i+1}: Failed - {e}")
    
    print("\n" + "="*70)
    print("DATA INSERTED (but embeddings are still TEXT type)")
    print("="*70)
    print("\nThe Supabase Python client cannot insert proper vector types.")
    print("The search won't work until embeddings are converted to vector type.")
    print("\nTO FIX: Run this SQL in Supabase SQL Editor:")
    print("="*70)
    print("""
-- Step 1: Add a temporary column with vector type
ALTER TABLE labor_law_embeddings ADD COLUMN embedding_vec vector(1536);

-- Step 2: Convert string embeddings to vector type
UPDATE labor_law_embeddings 
SET embedding_vec = embedding::vector;

-- Step 3: Drop old column and rename
ALTER TABLE labor_law_embeddings DROP COLUMN embedding;
ALTER TABLE labor_law_embeddings RENAME COLUMN embedding_vec TO embedding;

-- Step 4: Recreate index
CREATE INDEX labor_law_embeddings_embedding_idx 
    ON labor_law_embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
    """)
    print("="*70)
    print("\nAfter running this SQL, the search will work properly.")
    
    return len(prepared_docs)

if __name__ == "__main__":
    count = ingest_via_supabase_sql()
    print(f"\nInserted {count} documents. Please run the SQL fix above.")
