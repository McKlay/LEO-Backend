#!/usr/bin/env python3
"""
Validate manual chunks metadata format.

This script checks that all manual chunks follow the standardized format:
- article_number is a string in format: {source_prefix}_{descriptive_section_id}
- All required frontmatter fields are present
- YAML is valid
"""

import sys
from pathlib import Path
import yaml
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def validate_article_number(article_number: str, source_prefix: str) -> tuple[bool, str]:
    """
    Validate article_number format.
    
    Returns: (is_valid, error_message)
    """
    # Check if it's a string
    if not isinstance(article_number, str):
        return False, f"article_number must be a string, got {type(article_number).__name__}"
    
    # Check if it's numeric-only (invalid)
    if article_number.isdigit():
        return False, f"article_number cannot be numeric-only: '{article_number}'"
    
    # Check format: should start with source prefix
    expected_prefix = source_prefix.lower().replace("-", "").replace(" ", "")
    if not article_number.lower().startswith(expected_prefix):
        return False, f"article_number should start with '{expected_prefix}', got '{article_number}'"
    
    # Check format: should contain underscores
    if "_" not in article_number:
        return False, f"article_number should use underscores: '{article_number}'"
    
    # Check format: should be lowercase with underscores only
    if not re.match(r'^[a-z0-9_]+$', article_number):
        return False, f"article_number should only contain lowercase letters, numbers, and underscores: '{article_number}'"
    
    return True, ""

def validate_chunk_file(chunk_path: Path, source_prefix: str) -> list[str]:
    """
    Validate a single chunk file.
    
    Returns: list of error messages (empty if valid)
    """
    errors = []
    
    try:
        content = chunk_path.read_text(encoding='utf-8')
        
        # Check for YAML frontmatter
        if not content.startswith('---\n'):
            errors.append("Missing YAML frontmatter (should start with '---')")
            return errors
        
        # Extract frontmatter
        parts = content.split('---\n', 2)
        if len(parts) < 3:
            errors.append("Invalid YAML frontmatter format")
            return errors
        
        # Parse YAML
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            errors.append(f"Invalid YAML: {e}")
            return errors
        
        # Check required fields
        required_fields = [
            'chunk_id', 'title', 'article_number', 'semantic_type',
            'hierarchy', 'keywords', 'has_table', 'has_formula', 'has_list'
        ]
        
        for field in required_fields:
            if field not in frontmatter:
                errors.append(f"Missing required field: {field}")
        
        # Validate article_number format
        if 'article_number' in frontmatter:
            is_valid, error_msg = validate_article_number(
                frontmatter['article_number'],
                source_prefix
            )
            if not is_valid:
                errors.append(f"Invalid article_number format: {error_msg}")
        
        # Validate hierarchy structure
        if 'hierarchy' in frontmatter:
            if not isinstance(frontmatter['hierarchy'], dict):
                errors.append("hierarchy must be a dictionary")
        
        # Validate keywords
        if 'keywords' in frontmatter:
            if not isinstance(frontmatter['keywords'], list):
                errors.append("keywords must be a list")
        
    except Exception as e:
        errors.append(f"Error reading file: {e}")
    
    return errors

def validate_document(doc_dir: Path) -> tuple[int, int]:
    """
    Validate all chunks in a document directory.
    
    Returns: (total_chunks, error_count)
    """
    metadata_file = doc_dir / "metadata.json"
    
    if not metadata_file.exists():
        print(f"❌ {doc_dir.name}: No metadata.json found")
        return 0, 1
    
    # Load metadata
    import json
    try:
        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
        source_prefix = metadata.get('reference', doc_dir.name)
    except Exception as e:
        print(f"❌ {doc_dir.name}: Error reading metadata.json: {e}")
        return 0, 1
    
    # Find all markdown chunks
    chunk_files = sorted(doc_dir.glob("*.md"))
    
    if not chunk_files:
        print(f"⚠️  {doc_dir.name}: No chunk files found")
        return 0, 0
    
    total_errors = 0
    
    for chunk_file in chunk_files:
        errors = validate_chunk_file(chunk_file, source_prefix)
        
        if errors:
            print(f"\n❌ {doc_dir.name}/{chunk_file.name}:")
            for error in errors:
                print(f"   - {error}")
            total_errors += len(errors)
        else:
            print(f"✓ {doc_dir.name}/{chunk_file.name}")
    
    return len(chunk_files), total_errors

def main():
    """Main validation script."""
    chunks_dir = Path(__file__).parent.parent / "kb" / "chunks"
    
    if not chunks_dir.exists():
        print(f"❌ Chunks directory not found: {chunks_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("Manual Chunks Metadata Validation")
    print("=" * 60)
    
    # Find all document directories
    doc_dirs = [d for d in chunks_dir.iterdir() if d.is_dir()]
    
    if not doc_dirs:
        print(f"⚠️  No document directories found in {chunks_dir}")
        sys.exit(0)
    
    total_chunks = 0
    total_errors = 0
    
    for doc_dir in sorted(doc_dirs):
        chunks, errors = validate_document(doc_dir)
        total_chunks += chunks
        total_errors += errors
    
    print("\n" + "=" * 60)
    print(f"Validation Summary:")
    print(f"  Total chunks validated: {total_chunks}")
    print(f"  Total errors found: {total_errors}")
    
    if total_errors == 0:
        print("\n✅ All chunks passed validation!")
        sys.exit(0)
    else:
        print(f"\n❌ Found {total_errors} validation error(s)")
        sys.exit(1)

if __name__ == "__main__":
    main()
