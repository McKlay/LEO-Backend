"""
Apply SQL fix to convert TEXT embeddings to VECTOR type.
This script uses Supabase SQL execution via RPC.
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def apply_sql_fix():
    """Execute SQL commands to fix the vector type issue."""
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    print("="*70)
    print("Applying SQL Fix for Vector Type Issue")
    print("="*70)
    
    sql_commands = [
        {
            "name": "Add temporary vector column",
            "sql": "ALTER TABLE labor_law_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);"
        },
        {
            "name": "Convert TEXT to VECTOR",
            "sql": "UPDATE labor_law_embeddings SET embedding_vec = embedding::vector WHERE embedding_vec IS NULL;"
        },
        {
            "name": "Drop old TEXT column",
            "sql": "ALTER TABLE labor_law_embeddings DROP COLUMN IF EXISTS embedding;"
        },
        {
            "name": "Rename vector column",
            "sql": "ALTER TABLE labor_law_embeddings RENAME COLUMN embedding_vec TO embedding;"
        },
        {
            "name": "Recreate vector index",
            "sql": """
                DROP INDEX IF EXISTS labor_law_embeddings_embedding_idx;
                CREATE INDEX labor_law_embeddings_embedding_idx 
                    ON labor_law_embeddings 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
            """
        }
    ]
    
    print("\nNote: Supabase REST API has limited SQL execution capabilities.")
    print("Opening Supabase SQL Editor instructions...\n")
    
    print("PLEASE RUN THIS SQL IN SUPABASE SQL EDITOR:")
    print("="*70)
    print("Link: https://supabase.com/dashboard/project/qoombyuhqwuozjnreouz/sql/new")
    print()
    
    full_sql = """
-- Fix vector type issue in labor_law_embeddings table
-- Step 1: Add temporary vector column
ALTER TABLE labor_law_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- Step 2: Convert TEXT to VECTOR
UPDATE labor_law_embeddings SET embedding_vec = embedding::vector WHERE embedding_vec IS NULL;

-- Step 3: Drop old TEXT column
ALTER TABLE labor_law_embeddings DROP COLUMN IF EXISTS embedding;

-- Step 4: Rename vector column
ALTER TABLE labor_law_embeddings RENAME COLUMN embedding_vec TO embedding;

-- Step 5: Recreate vector index
DROP INDEX IF EXISTS labor_law_embeddings_embedding_idx;
CREATE INDEX labor_law_embeddings_embedding_idx 
    ON labor_law_embeddings 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
    
-- Verify the fix
SELECT 
    id, 
    content,
    pg_typeof(embedding) as embedding_type,
    metadata
FROM labor_law_embeddings 
LIMIT 3;
"""
    
    print(full_sql)
    print("="*70)
    
    # Save to file for easy copy-paste
    with open("scripts/fix_vector_type.sql", "w") as f:
        f.write(full_sql)
    
    print(f"\n✓ SQL saved to: scripts/fix_vector_type.sql")
    print("\nAfter running the SQL:")
    print("1. Press Enter to verify the fix")
    print("2. Then we'll run the integration tests")
    
    input("\nPress Enter when you've run the SQL in Supabase SQL Editor...")
    
    # Verify the fix
    print("\nVerifying vector type conversion...")
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Test search
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input="What is 13th month pay?"
        )
        query_vec = response.data[0].embedding
        
        result = client.rpc('match_documents', {
            'query_embedding': query_vec,
            'match_threshold': 0.0,
            'match_count': 5,
            'filter_metadata': '{}'
        }).execute()
        
        if len(result.data) > 0:
            print(f"✅ SUCCESS! Found {len(result.data)} results")
            print("\nTop results:")
            for i, r in enumerate(result.data[:3]):
                print(f"  {i+1}. Similarity: {r.get('similarity', 0):.4f}")
                print(f"     Content: {r.get('content', '')[:80]}...")
            
            print("\n" + "="*70)
            print("Vector type fix applied successfully!")
            print("Integration tests can now proceed.")
            print("="*70)
            return True
        else:
            print("⚠ Still getting 0 results. Please check:")
            print("  1. SQL was executed successfully")
            print("  2. No errors in Supabase SQL Editor")
            print("  3. Table has data: SELECT COUNT(*) FROM labor_law_embeddings;")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        print("Please ensure the SQL was executed successfully.")
        return False

if __name__ == "__main__":
    success = apply_sql_fix()
    if not success:
        print("\n⚠ Please fix the issues and run this script again.")
