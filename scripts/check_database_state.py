"""
Check database state and RLS policies
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("SUPABASE_DB_URL")
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

try:
    # Check table exists
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'labor_law_embeddings'
    """)
    print(f"✅ Table exists: {cursor.fetchone() is not None}")
    
    # Check row count
    cursor.execute("SELECT COUNT(*) FROM labor_law_embeddings")
    count = cursor.fetchone()[0]
    print(f"📊 Total rows: {count}")
    
    # Check RLS is enabled
    cursor.execute("""
        SELECT relrowsecurity 
        FROM pg_class 
        WHERE relname = 'labor_law_embeddings'
    """)
    rls_enabled = cursor.fetchone()[0]
    print(f"🔒 RLS enabled: {rls_enabled}")
    
    # Check policies
    cursor.execute("""
        SELECT policyname, permissive, roles, cmd 
        FROM pg_policies 
        WHERE tablename = 'labor_law_embeddings'
    """)
    policies = cursor.fetchall()
    print(f"📜 Policies: {len(policies)}")
    for policy in policies:
        print(f"   - {policy}")
    
    # Try SELECT as current user
    cursor.execute("SELECT current_user, current_role")
    user = cursor.fetchone()
    print(f"👤 Current user/role: {user}")
    
    # Try direct SELECT
    cursor.execute("SELECT id, content FROM labor_law_embeddings LIMIT 3")
    rows = cursor.fetchall()
    print(f"📄 Can SELECT: {len(rows)} rows")
    for row in rows:
        print(f"   - {row[0]}: {row[1][:80]}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cursor.close()
    conn.close()
