#!/usr/bin/env python3
"""
Validate manually chunked documents.

Validates all manually chunked documents for:
- YAML frontmatter completeness
- Required fields present
- Content not empty
- Metadata.json exists
- Total chunks matches metadata

Usage:
    # Validate all documents
    python scripts/ingestion/validate_chunks.py

    # Validate specific document
    python scripts/ingestion/validate_chunks.py --document PD-No-851

    # Strict mode (fail on warnings)
    python scripts/ingestion/validate_chunks.py --strict

    # Verbose output
    python scripts/ingestion/validate_chunks.py --verbose
"""
import argparse
import json
import yaml
from pathlib import Path
from typing import List, Tuple, Dict
import sys


def validate_frontmatter(chunk_file: Path) -> Tuple[bool, List[str], List[str]]:
    """
    Validate YAML frontmatter in a chunk file.
    
    Returns:
        (is_valid, list of errors, list of warnings)
    """
    errors = []
    warnings = []
    
    try:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for frontmatter
        if not content.startswith('---'):
            errors.append("No YAML frontmatter found (must start with '---')")
            return False, errors, warnings
        
        # Split frontmatter and content
        parts = content.split('---', 2)
        if len(parts) < 3:
            errors.append("Invalid frontmatter format (must have opening and closing '---')")
            return False, errors, warnings
        
        # Parse YAML
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
            return False, errors, warnings
        
        # Validate required fields
        required_fields = ['chunk_id', 'title', 'article_number']
        for field in required_fields:
            if field not in frontmatter:
                errors.append(f"Missing required field: '{field}'")
        
        # Validate recommended fields
        recommended_fields = ['keywords', 'semantic_type']
        for field in recommended_fields:
            if field not in frontmatter:
                warnings.append(f"Missing recommended field: '{field}'")
        
        # Validate keywords
        if 'keywords' in frontmatter:
            if not isinstance(frontmatter['keywords'], list):
                errors.append("'keywords' must be a list")
            elif len(frontmatter['keywords']) == 0:
                warnings.append("'keywords' list is empty")
            elif len(frontmatter['keywords']) < 3:
                warnings.append(f"Only {len(frontmatter['keywords'])} keywords (recommended: 3+)")
        
        # Validate content
        chunk_content = parts[2].strip()
        if not chunk_content:
            errors.append("Chunk content is empty")
        elif len(chunk_content) < 100:
            warnings.append(f"Chunk content is very short ({len(chunk_content)} chars)")
        
        # Validate chunk_id format
        if 'chunk_id' in frontmatter:
            chunk_id = frontmatter['chunk_id']
            if ' ' in str(chunk_id):
                errors.append(f"chunk_id contains spaces: '{chunk_id}'")
        
        return len(errors) == 0, errors, warnings
        
    except Exception as e:
        errors.append(f"Failed to read file: {e}")
        return False, errors, warnings


def validate_metadata(document_folder: Path) -> Tuple[bool, List[str], List[str]]:
    """
    Validate metadata.json in a document folder.
    
    Returns:
        (is_valid, list of errors, list of warnings)
    """
    errors = []
    warnings = []
    metadata_file = document_folder / "metadata.json"
    
    if not metadata_file.exists():
        errors.append("metadata.json not found")
        return False, errors, warnings
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Validate required fields
        required_fields = ['source', 'reference', 'doc_type', 'total_chunks']
        for field in required_fields:
            if field not in metadata:
                errors.append(f"Missing required field in metadata: '{field}'")
        
        # Validate recommended fields
        recommended_fields = ['year', 'url', 'short_name', 'chunking_strategy']
        for field in recommended_fields:
            if field not in metadata:
                warnings.append(f"Missing recommended field in metadata: '{field}'")
        
        # Validate total_chunks is a number
        if 'total_chunks' in metadata:
            if not isinstance(metadata['total_chunks'], int):
                errors.append("'total_chunks' must be an integer")
            elif metadata['total_chunks'] <= 0:
                errors.append(f"'total_chunks' must be positive (got {metadata['total_chunks']})")
        
        return len(errors) == 0, errors, warnings
        
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in metadata.json: {e}")
        return False, errors, warnings
    except Exception as e:
        errors.append(f"Failed to read metadata.json: {e}")
        return False, errors, warnings


def validate_document(document_folder: Path, verbose: bool = False) -> Tuple[bool, Dict]:
    """
    Validate all chunks in a document folder.
    
    Returns:
        (is_valid, validation_report)
    """
    report = {
        'document': document_folder.name,
        'metadata_valid': False,
        'chunks_valid': True,
        'total_chunks': 0,
        'expected_chunks': 0,
        'errors': [],
        'warnings': [],
        'chunk_reports': []
    }
    
    # Validate metadata
    meta_valid, meta_errors, meta_warnings = validate_metadata(document_folder)
    report['metadata_valid'] = meta_valid
    report['errors'].extend(meta_errors)
    report['warnings'].extend(meta_warnings)
    
    # Get expected chunk count
    metadata_file = document_folder / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                report['expected_chunks'] = metadata.get('total_chunks', 0)
        except:
            pass
    
    # Find all chunk files
    chunk_files = sorted(document_folder.glob('*.md'))
    chunk_files = [f for f in chunk_files if f.name != 'README.md']
    report['total_chunks'] = len(chunk_files)
    
    # Validate each chunk
    for chunk_file in chunk_files:
        chunk_valid, chunk_errors, chunk_warnings = validate_frontmatter(chunk_file)
        
        chunk_report = {
            'file': chunk_file.name,
            'valid': chunk_valid,
            'errors': chunk_errors,
            'warnings': chunk_warnings
        }
        report['chunk_reports'].append(chunk_report)
        
        if not chunk_valid:
            report['chunks_valid'] = False
        
        if verbose:
            print(f"  {'✓' if chunk_valid else '✗'} {chunk_file.name}")
            for error in chunk_errors:
                print(f"      ERROR: {error}")
            for warning in chunk_warnings:
                print(f"      WARN: {warning}")
    
    # Check chunk count mismatch
    if report['total_chunks'] != report['expected_chunks']:
        msg = f"Chunk count mismatch: found {report['total_chunks']}, expected {report['expected_chunks']}"
        report['errors'].append(msg)
    
    return report['metadata_valid'] and report['chunks_valid'], report


def main():
    parser = argparse.ArgumentParser(
        description='Validate manually chunked documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--document',
        help='Validate specific document folder (e.g., PD-No-851)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent.parent.parent
    chunks_dir = project_root / 'kb' / 'chunks'
    
    if not chunks_dir.exists():
        print(f"❌ Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    # Get documents to validate
    if args.document:
        document_folders = [chunks_dir / args.document]
        if not document_folders[0].exists():
            print(f"❌ Document folder not found: {args.document}")
            sys.exit(1)
    else:
        # Validate all document folders
        document_folders = [d for d in chunks_dir.iterdir() if d.is_dir()]
    
    print(f"\n{'='*60}")
    print("MANUAL CHUNK VALIDATION")
    print(f"{'='*60}\n")
    
    all_valid = True
    total_errors = 0
    total_warnings = 0
    
    for doc_folder in document_folders:
        print(f"📁 {doc_folder.name}")
        print(f"{'─'*60}")
        
        is_valid, report = validate_document(doc_folder, args.verbose)
        
        if not args.verbose:
            # Summary view
            print(f"  Metadata: {'✓ Valid' if report['metadata_valid'] else '✗ Invalid'}")
            print(f"  Chunks: {report['total_chunks']} found, {report['expected_chunks']} expected")
            print(f"  Status: {'✓ Valid' if is_valid else '✗ Invalid'}")
        
        # Show errors
        if report['errors']:
            print(f"\n  ❌ ERRORS ({len(report['errors'])}):")
            for error in report['errors']:
                print(f"    • {error}")
            total_errors += len(report['errors'])
        
        # Show warnings
        if report['warnings']:
            print(f"\n  ⚠️  WARNINGS ({len(report['warnings'])}):")
            for warning in report['warnings']:
                print(f"    • {warning}")
            total_warnings += len(report['warnings'])
        
        if not is_valid:
            all_valid = False
        
        print()
    
    # Final summary
    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Documents validated: {len(document_folders)}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")
    
    if args.strict and total_warnings > 0:
        print(f"\n❌ FAILED (strict mode: warnings treated as errors)")
        sys.exit(1)
    elif all_valid:
        print(f"\n✅ ALL VALIDATIONS PASSED")
        sys.exit(0)
    else:
        print(f"\n❌ VALIDATION FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
