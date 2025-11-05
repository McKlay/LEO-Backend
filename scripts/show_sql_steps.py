"""
Execute SQL fix using direct HTTP requests to Supabase PostgREST API.
This bypasses the Python client's limitations.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def execute_sql_via_api():
    """Execute SQL commands via Supabase REST API."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    # Supabase SQL execution endpoint
    # Note: This requires the SQL execution to be enabled in your Supabase project
    
    print("Executing SQL fix step by step...")
    print("="*70)
    
    sql_steps = [
        ("Add vector column", 
         "ALTER TABLE labor_law_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(1536)"),
        
        ("Convert TEXT to VECTOR",
         "UPDATE labor_law_embeddings SET embedding_vec = embedding::vector WHERE embedding_vec IS NULL"),
        
        ("Drop old column",
         "ALTER TABLE labor_law_embeddings DROP COLUMN IF EXISTS embedding"),
        
        ("Rename column",
         "ALTER TABLE labor_law_embeddings RENAME COLUMN embedding_vec TO embedding"),
        
        ("Drop old index",
         "DROP INDEX IF EXISTS labor_law_embeddings_embedding_idx"),
        
        ("Create vector index",
         "CREATE INDEX labor_law_embeddings_embedding_idx ON labor_law_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    ]
    
    print("⚠ Note: Supabase REST API doesn't support arbitrary SQL execution.")
    print("You must run this SQL in the Supabase SQL Editor.\n")
    print("Here's each step separately:\n")
    
    for i, (name, sql) in enumerate(sql_steps, 1):
        print(f"{i}. {name}:")
        print(f"   {sql}")
        print()
    
    print("="*70)
    print("\nPlease run each SQL statement above in Supabase SQL Editor:")
    print("https://supabase.com/dashboard/project/qoombyuhqwuozjnreouz/sql/new")
    print("\nRun them ONE AT A TIME to see which one causes the error.")
    print("="*70)

if __name__ == "__main__":
    execute_sql_via_api()
