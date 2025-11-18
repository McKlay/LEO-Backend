#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
List all manually chunked documents.

Shows overview of all documents in kb/chunks/ with their metadata
and chunking status.

Usage:
    # List all documents
    python scripts/ingestion/list_documents.py
    
    # Show detailed information
    python scripts/ingestion/list_documents.py --verbose
    
    # Show only incomplete documents
    python scripts/ingestion/list_documents.py --incomplete
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List
import io

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def get_document_info(document_folder: Path) -> Dict:
    """Get information about a document."""
    info = {
        'folder': document_folder.name,
        'has_metadata': False,
        'total_chunks': 0,
        'actual_chunks': 0,
        'is_complete': False
    }
    
    # Check metadata
    metadata_file = document_folder / 'metadata.json'
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            info['has_metadata'] = True
            info['source'] = metadata.get('source', 'Unknown')
            info['reference'] = metadata.get('reference', 'Unknown')
            info['doc_type'] = metadata.get('doc_type', 'Unknown')
            info['year'] = metadata.get('year', 'Unknown')
            info['short_name'] = metadata.get('short_name', '')
            info['total_chunks'] = metadata.get('total_chunks', 0)
            info['chunking_strategy'] = metadata.get('chunking_strategy', 'manual')
            info['last_updated'] = metadata.get('last_updated', 'Unknown')
        except Exception as e:
            info['error'] = f"Failed to read metadata: {e}"
    
    # Count actual chunk files
    chunk_files = list(document_folder.glob('*.md'))
    chunk_files = [f for f in chunk_files if f.name != 'README.md']
    info['actual_chunks'] = len(chunk_files)
    
    # Check if complete
    if info['has_metadata']:
        info['is_complete'] = (
            info['total_chunks'] > 0 and 
            info['actual_chunks'] == info['total_chunks']
        )
    
    return info


def main():
    parser = argparse.ArgumentParser(
        description='List manually chunked documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed information'
    )
    parser.add_argument(
        '--incomplete',
        action='store_true',
        help='Show only incomplete documents'
    )
    
    args = parser.parse_args()
    
    chunks_dir = project_root / 'kb' / 'chunks'
    
    if not chunks_dir.exists():
        print(f"❌ Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    # Get all document folders
    document_folders = [d for d in chunks_dir.iterdir() if d.is_dir()]
    
    print(f"\n{'='*80}")
    print("MANUALLY CHUNKED DOCUMENTS")
    print(f"{'='*80}\n")
    
    documents = []
    for doc_folder in sorted(document_folders):
        info = get_document_info(doc_folder)
        documents.append(info)
    
    # Filter if needed
    if args.incomplete:
        documents = [d for d in documents if not d['is_complete']]
    
    # Display documents
    for info in documents:
        status = '✅' if info['is_complete'] else '⏳'
        print(f"{status} {info['folder']}")
        print(f"{'─'*80}")
        
        if 'error' in info:
            print(f"  ❌ {info['error']}")
        elif info['has_metadata']:
            print(f"  Source: {info.get('source', 'Unknown')}")
            print(f"  Reference: {info.get('reference', 'Unknown')}")
            print(f"  Type: {info.get('doc_type', 'Unknown')}")
            print(f"  Year: {info.get('year', 'Unknown')}")
            if info.get('short_name'):
                print(f"  Short Name: {info['short_name']}")
            print(f"  Chunks: {info['actual_chunks']}/{info['total_chunks']}")
            print(f"  Status: {'Complete' if info['is_complete'] else 'Incomplete'}")
            
            if args.verbose:
                print(f"  Strategy: {info.get('chunking_strategy', 'manual')}")
                print(f"  Last Updated: {info.get('last_updated', 'Unknown')}")
        else:
            print(f"  ⚠️  No metadata.json found")
            print(f"  Chunk files: {info['actual_chunks']}")
        
        print()
    
    # Summary
    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    total_docs = len(documents)
    complete_docs = len([d for d in documents if d['is_complete']])
    incomplete_docs = total_docs - complete_docs
    total_chunks = sum(d['actual_chunks'] for d in documents)
    
    print(f"Total documents: {total_docs}")
    print(f"Complete: {complete_docs}")
    print(f"Incomplete: {incomplete_docs}")
    print(f"Total chunks: {total_chunks}")
    
    if incomplete_docs > 0:
        print(f"\n⏳ {incomplete_docs} document(s) need completion")
    else:
        print(f"\n✅ All documents are complete")


if __name__ == '__main__':
    main()
