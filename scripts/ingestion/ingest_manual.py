#!/usr/bin/env python3
"""
Ingest manually chunked documents into the database.

This script ingests pre-chunked documents from kb/chunks/ into the Supabase
vector store with proper embeddings and metadata.

Usage:
    # Ingest specific document
    python scripts/ingestion/ingest_manual.py --folder PD-No-851
    
    # Ingest all documents
    python scripts/ingestion/ingest_manual.py --all
    
    # Dry run (preview without ingesting)
    python scripts/ingestion/ingest_manual.py --folder PD-No-851 --dry-run
    
    # Force re-ingestion
    python scripts/ingestion/ingest_manual.py --folder PD-No-851 --force
    
    # Ingest single chunk file
    python scripts/ingestion/ingest_manual.py --file kb/chunks/PD-No-851/01-decree-main.md
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kb.ingest.sync_to_vectorstore import ingest_manual_chunks
from core import get_logger

logger = get_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description='Ingest manually chunked documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Input selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--folder',
        help='Document folder name (e.g., PD-No-851)'
    )
    group.add_argument(
        '--file',
        help='Single chunk file path'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Ingest all manual chunks'
    )
    
    # Options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview chunks without ingesting'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-ingestion (skip deduplication)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Get chunks directory
    chunks_dir = project_root / 'kb' / 'chunks'
    
    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    try:
        if args.folder:
            # Ingest specific folder
            folder_path = chunks_dir / args.folder
            if not folder_path.exists():
                logger.error(f"Document folder not found: {args.folder}")
                sys.exit(1)
            
            logger.info(f"Ingesting document: {args.folder}")
            await ingest_manual_chunks(
                folder_path=folder_path,
                dry_run=args.dry_run,
                force=args.force
            )
        
        elif args.file:
            # Ingest single file
            file_path = Path(args.file)
            if not file_path.exists():
                logger.error(f"Chunk file not found: {args.file}")
                sys.exit(1)
            
            logger.info(f"Ingesting chunk: {file_path.name}")
            await ingest_manual_chunks(
                file_path=file_path,
                dry_run=args.dry_run,
                force=args.force
            )
        
        elif args.all:
            # Ingest all documents
            logger.info("Ingesting all manual chunks")
            
            # Get all document folders
            document_folders = [d for d in chunks_dir.iterdir() if d.is_dir()]
            
            logger.info(f"Found {len(document_folders)} documents to ingest")
            
            for doc_folder in sorted(document_folders):
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {doc_folder.name}")
                logger.info(f"{'='*60}")
                
                await ingest_manual_chunks(
                    folder_path=doc_folder,
                    dry_run=args.dry_run,
                    force=args.force
                )
        
        logger.info("\n✅ Ingestion completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
