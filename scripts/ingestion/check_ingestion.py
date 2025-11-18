#!/usr/bin/env python3
"""
Check manual chunk ingestion status.

Shows which documents and chunks have been ingested, their status,
and any issues that need attention.

Usage:
    # Check all documents
    python scripts/ingestion/check_ingestion.py
    
    # Check specific document
    python scripts/ingestion/check_ingestion.py --document PD-No-851
    
    # Show detailed chunk information
    python scripts/ingestion/check_ingestion.py --verbose
"""
import argparse
import asyncio
import json
import sys
import psycopg2
import io
from pathlib import Path
from typing import Dict, List

# Fix Unicode encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger
from core.config import Settings

logger = get_logger(__name__)


async def check_document_status(document_folder: Path, db_url: str) -> Dict:
    """
    Check ingestion status for a document.
    
    Returns:
        status_report dictionary
    """
    report = {
        'document': document_folder.name,
        'total_chunks': 0,
        'ingested_chunks': 0,
        'missing_chunks': [],
        'chunk_details': []
    }
    
    # Read metadata
    metadata_file = document_folder / 'metadata.json'
    if not metadata_file.exists():
        report['error'] = 'metadata.json not found'
        return report
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        report['source'] = metadata.get('source', 'Unknown')
        report['reference'] = metadata.get('reference', 'Unknown')
        report['total_chunks'] = metadata.get('total_chunks', 0)
    except Exception as e:
        report['error'] = f'Failed to read metadata: {e}'
        return report
    
    # Get chunk files
    chunk_files = sorted(document_folder.glob('*.md'))
    chunk_files = [f for f in chunk_files if f.name != 'README.md']
    
    # Check each chunk in database
    for chunk_file in chunk_files:
        chunk_name = chunk_file.stem
        
        # Query database directly for this chunk
        try:
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Check if chunk exists by article_number OR chunk_id in metadata
            # article_number should contain chunk_id after the fix
            cursor.execute("""
                SELECT id, article_number, metadata->>'file_stem' as file_stem
                FROM labor_law_sections 
                WHERE metadata->>'file_stem' = %s
                LIMIT 1
            """, (chunk_name,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            is_ingested = result is not None
            
            chunk_detail = {
                'file': chunk_file.name,
                'chunk_id': chunk_name,
                'ingested': is_ingested
            }
            
            if is_ingested:
                report['ingested_chunks'] += 1
                chunk_detail['embedding_id'] = result[0] if result else None
            else:
                report['missing_chunks'].append(chunk_file.name)
            
            report['chunk_details'].append(chunk_detail)
            
        except Exception as e:
            chunk_detail = {
                'file': chunk_file.name,
                'chunk_id': chunk_name,
                'ingested': False,
                'error': str(e)
            }
            report['chunk_details'].append(chunk_detail)
            report['missing_chunks'].append(chunk_file.name)
    
    return report


async def main():
    parser = argparse.ArgumentParser(
        description='Check manual chunk ingestion status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--document',
        help='Check specific document (e.g., PD-No-851)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed chunk information'
    )
    
    args = parser.parse_args()
    
    chunks_dir = project_root / 'kb' / 'chunks'
    
    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    # Get documents to check
    if args.document:
        document_folders = [chunks_dir / args.document]
        if not document_folders[0].exists():
            logger.error(f"Document folder not found: {args.document}")
            sys.exit(1)
    else:
        document_folders = [d for d in chunks_dir.iterdir() if d.is_dir()]
    
    print(f"\n{'='*60}")
    print("MANUAL CHUNK INGESTION STATUS")
    print(f"{'='*60}\n")
    
    try:
        # Get database settings
        settings = Settings()
        db_url = settings.supabase_db_url
        
        if not db_url:
            logger.error("Database URL not configured")
            sys.exit(1)
        
        total_documents = 0
        total_ingested = 0
        total_missing = 0
        
        for doc_folder in sorted(document_folders):
            report = await check_document_status(doc_folder, db_url)
            
            total_documents += 1
            total_ingested += report['ingested_chunks']
            total_missing += len(report['missing_chunks'])
            
            print(f"📁 {report['document']}")
            print(f"{'─'*60}")
            
            if 'error' in report:
                print(f"  ❌ Error: {report['error']}")
            else:
                print(f"  Source: {report.get('source', 'Unknown')}")
                print(f"  Reference: {report.get('reference', 'Unknown')}")
                print(f"  Chunks: {report['ingested_chunks']}/{report['total_chunks']} ingested")
                
                if report['missing_chunks']:
                    print(f"\n  ⚠️  Missing chunks ({len(report['missing_chunks'])}):")
                    for chunk in report['missing_chunks']:
                        print(f"    • {chunk}")
                else:
                    print(f"  ✅ All chunks ingested")
                
                if args.verbose and report['chunk_details']:
                    print(f"\n  Chunk details:")
                    for detail in report['chunk_details']:
                        status = '✓' if detail['ingested'] else '✗'
                        print(f"    {status} {detail['file']}")
                        if 'error' in detail:
                            print(f"        Error: {detail['error']}")
            
            print()
        
        # Summary
        print(f"{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Documents checked: {total_documents}")
        print(f"Chunks ingested: {total_ingested}")
        print(f"Chunks missing: {total_missing}")
        
        if total_missing > 0:
            print(f"\n⚠️  Some chunks are not ingested")
            print(f"Run: python scripts/ingestion/ingest_manual.py --all")
        else:
            print(f"\n✅ All chunks are ingested")
    
    except Exception as e:
        logger.error(f"Failed to check status: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
