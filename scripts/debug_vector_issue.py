"""Debug the vector type issue."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def debug_table():
    client = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    
    print("Debugging labor_law_embeddings table...")
    print("="*70)
    
    # Check if data exists
    print("\n1. Checking if table has data...")
    result = client.table('labor_law_embeddings').select('id').execute()
    print(f"   Row count: {len(result.data)}")
    
    if len(result.data) == 0:
        print("   ⚠ Table is empty! Need to re-insert data.")
        return False
    
    # Check embedding column
    print("\n2. Checking embedding column...")
    result = client.table('labor_law_embeddings').select('id,embedding').limit(1).execute()
    if result.data:
        embedding = result.data[0].get('embedding')
        print(f"   Embedding type: {type(embedding)}")
        
        if isinstance(embedding, str):
            print(f"   ❌ Still TEXT! Length: {len(embedding)}")
            print(f"   First 100 chars: {embedding[:100]}")
            print("\n   The SQL conversion didn't work. Let's try a different approach.")
            return False
        elif isinstance(embedding, list):
            print(f"   ✅ It's a list! Dimension: {len(embedding)}")
            print(f"   This means the vector type is working!")
            return True
        else:
            print(f"   Unknown type: {embedding}")
            return False
    
    return False

if __name__ == "__main__":
    success = debug_table()
    
    if not success:
        print("\n" + "="*70)
        print("TROUBLESHOOTING:")
        print("="*70)
        print("The embedding column is still TEXT after running the SQL.")
        print("\nPossible issues:")
        print("1. The SQL didn't execute successfully")
        print("2. The data was cleared but not re-inserted")
        print("3. PostgreSQL user doesn't have ALTER TABLE permissions")
        print("\nNext step: Let's re-insert the data with a different method.")
