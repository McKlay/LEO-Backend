"""
Setup Supabase database schema.

This script executes the schema.sql file to create all necessary tables,
indexes, and functions in your Supabase instance.

Usage:
    python scripts/setup_supabase.py
"""
import os
from pathlib import Path
import psycopg2
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_database():
    """Execute schema.sql to set up database."""
    # Get database connection parameters from environment
    db_url = os.getenv("SUPABASE_DB_URL")
    
    # Alternative: construct from individual components if URL parsing fails
    if not db_url:
        project_id = os.getenv("PROJECT_REFERENCE_ID")
        if project_id:
            # Construct DB URL from components
            password = quote_plus("l3g@l@idch@tbot")  # URL-encode password with @ symbols
            db_url = f"postgresql://postgres:{password}@db.{project_id}.supabase.co:5432/postgres"
            print(f"ℹ️  Using constructed DB URL from PROJECT_REFERENCE_ID")
    
    if not db_url:
        print("❌ Error: SUPABASE_DB_URL or PROJECT_REFERENCE_ID not found in environment variables")
        return False
    
    # Read schema file
    schema_path = Path(__file__).parent.parent / "infra" / "supabase" / "schema.sql"
    
    if not schema_path.exists():
        print(f"❌ Error: Schema file not found at {schema_path}")
        return False
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    print(f"📋 Reading schema from: {schema_path}")
    print(f"🔌 Connecting to Supabase...")
    
    try:
        # Connect to database
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✓ Connected to database")
        print("🚀 Executing schema...")
        
        # Execute schema
        cursor.execute(schema_sql)
        
        print("✓ Schema executed successfully")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"\n📊 Created/verified tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Verify vector extension
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        if cursor.fetchone():
            print("\n✓ pgvector extension enabled")
        else:
            print("\n⚠️  Warning: pgvector extension not found")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Database setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error setting up database: {str(e)}")
        return False


if __name__ == "__main__":
    success = setup_database()
    exit(0 if success else 1)
