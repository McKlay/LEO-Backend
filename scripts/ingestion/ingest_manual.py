#!/usr/bin/env python3
'''Ingest manually chunked documents into the database.'''
import argparse
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core import get_logger, setup_logging

# Initialize logging immediately
setup_logging(level="INFO", json_output=False)

logger = get_logger(__name__)


def run_ingestion(cmd_args: list) -> int:
    try:
        result = subprocess.run(
            ["python", "-m", "kb.ingest.sync_to_vectorstore"] + cmd_args,
            cwd=str(project_root)
        )
        return result.returncode
    except Exception as e:
        logger.error(f"Failed to run ingestion: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Ingest manually chunked documents'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--folder', help='Document folder (e.g., PD-No-851)')
    group.add_argument('--file', help='Single chunk file path')
    group.add_argument('--all', action='store_true', help='Ingest all documents')
    
    parser.add_argument('--dry-run', action='store_true', help='Preview without ingesting')
    parser.add_argument('--force', action='store_true', help='Force re-ingestion')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    chunks_dir = project_root / 'kb' / 'chunks'
    if not chunks_dir.exists():
        logger.error(f"Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    try:
        cmd_args = ["--manual"]
        
        if args.dry_run:
            cmd_args.append("--dry-run")
        if args.force:
            cmd_args.append("--force")
        
        if args.folder:
            folder_path = chunks_dir / args.folder
            if not folder_path.exists():
                logger.error(f"Document folder not found: {args.folder}")
                sys.exit(1)
            
            logger.info(f"Ingesting document: {args.folder}")
            cmd_args.extend(["--folder", args.folder])
            exit_code = run_ingestion(cmd_args)
            
        elif args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                logger.error(f"Chunk file not found: {args.file}")
                sys.exit(1)
            
            logger.info(f"Ingesting chunk: {file_path.name}")
            cmd_args.extend(["--file", args.file])
            exit_code = run_ingestion(cmd_args)
            
        elif args.all:
            logger.info("Ingesting all manual chunks")
            
            document_folders = sorted([d for d in chunks_dir.iterdir() if d.is_dir()])
            logger.info(f"Found {len(document_folders)} documents")
            
            exit_code = 0
            for doc_folder in document_folders:
                logger.info(f"Processing: {doc_folder.name}")
                doc_args = cmd_args + ["--folder", doc_folder.name]
                result = run_ingestion(doc_args)
                if result != 0:
                    exit_code = result
        
        if exit_code == 0:
            logger.info("Ingestion completed successfully")
        else:
            logger.error(f"Ingestion failed with exit code {exit_code}")
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()
