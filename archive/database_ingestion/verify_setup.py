"""
Verify database setup and connections.

Usage:
    python scripts/database_ingestion/verify_setup.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor
from core import get_logger
from core.logging import setup_logging
from core.config import settings

setup_logging(level="INFO", json_output=False)
logger = get_logger(__name__)


def check_database_connection():
    """Test PostgreSQL connection."""
    logger.info("Checking database connection...")
    try:
        conn = psycopg2.connect(settings.supabase_db_url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        logger.info(f"✅ Database connected: {version.split(',')[0]}")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def check_pgvector_extension():
    """Verify pgvector extension is installed."""
    logger.info("Checking pgvector extension...")
    try:
        conn = psycopg2.connect(settings.supabase_db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT installed_version 
            FROM pg_available_extensions 
            WHERE name = 'vector';
        """)
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result[0]:
            logger.info(f"✅ pgvector installed: version {result[0]}")
            return True
        else:
            logger.error("❌ pgvector extension not installed")
            return False
    except Exception as e:
        logger.error(f"❌ pgvector check failed: {e}")
        return False


def check_required_tables():
    """Verify all required tables exist."""
    logger.info("Checking required tables...")
    required_tables = [
        'labor_law_sources',
        'labor_law_sections',
        'labor_law_chunks',
        'ingestion_history'
    ]
    
    try:
        conn = psycopg2.connect(settings.supabase_db_url)
        cur = conn.cursor()
        
        for table in required_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table,))
            exists = cur.fetchone()[0]
            
            if exists:
                logger.info(f"  ✅ {table}")
            else:
                logger.error(f"  ❌ {table} NOT FOUND")
                cur.close()
                conn.close()
                return False
        
        cur.close()
        conn.close()
        logger.info("✅ All required tables exist")
        return True
    except Exception as e:
        logger.error(f"❌ Table check failed: {e}")
        return False


def check_indexes():
    """Verify critical indexes."""
    logger.info("Checking indexes...")
    critical_indexes = [
        'idx_labor_law_sections_embedding_hnsw',
        'idx_labor_law_sections_fts',
        'idx_labor_law_sections_article_number',
        'idx_labor_law_sections_source_id'
    ]
    
    try:
        conn = psycopg2.connect(settings.supabase_db_url)
        cur = conn.cursor()
        
        for index in critical_indexes:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND indexname = %s
                );
            """, (index,))
            exists = cur.fetchone()[0]
            
            if exists:
                logger.info(f"  ✅ {index}")
            else:
                logger.warning(f"  ⚠️ {index} NOT FOUND")
        
        cur.close()
        conn.close()
        logger.info("✅ Index check complete")
        return True
    except Exception as e:
        logger.error(f"❌ Index check failed: {e}")
        return False


def check_openai_connection():
    """Test OpenAI API connection."""
    logger.info("Checking OpenAI API connection...")
    try:
        import openai
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.openai_api_key)
        # Test with minimal embedding request
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="test"
        )
        logger.info(f"✅ OpenAI API connected (embedding dimension: {len(response.data[0].embedding)})")
        return True
    except Exception as e:
        logger.error(f"❌ OpenAI API connection failed: {e}")
        return False


def check_source_documents():
    """Check if source documents directory exists and has files."""
    logger.info("Checking source documents...")
    docs_dir = project_root / "kb" / "docs"
    
    if not docs_dir.exists():
        logger.error(f"❌ Documents directory not found: {docs_dir}")
        return False
    
    txt_files = list(docs_dir.glob("*.txt"))
    
    if not txt_files:
        logger.warning(f"⚠️ No .txt files found in {docs_dir}")
        return False
    
    logger.info(f"✅ Found {len(txt_files)} source documents in {docs_dir}")
    return True


def main():
    logger.info("\n" + "="*60)
    logger.info("DATABASE INGESTION SETUP VERIFICATION")
    logger.info("="*60 + "\n")
    
    checks = [
        ("Database Connection", check_database_connection),
        ("pgvector Extension", check_pgvector_extension),
        ("Required Tables", check_required_tables),
        ("Database Indexes", check_indexes),
        ("OpenAI API", check_openai_connection),
        ("Source Documents", check_source_documents),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Check '{name}' failed with exception: {e}")
            results.append((name, False))
        logger.info("")  # Add spacing
    
    # Summary
    logger.info("="*60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("="*60)
    logger.info(f"Result: {passed}/{total} checks passed")
    
    if passed == total:
        logger.info("\n✅ All checks passed! Setup is ready for ingestion.")
        return 0
    else:
        logger.error(f"\n❌ {total - passed} check(s) failed. Please fix issues before ingestion.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
