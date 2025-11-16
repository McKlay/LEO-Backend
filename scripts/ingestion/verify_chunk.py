#!/usr/bin/env python3
"""
Verify a single chunk file.

Quick validation of a single chunk file's YAML frontmatter and content.

Usage:
    # Verify a chunk file
    python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-851/01-decree-main.md
    
    # Verbose output with suggestions
    python scripts/ingestion/verify_chunk.py kb/chunks/PD-No-851/01-decree-main.md --verbose
"""
import argparse
import sys
import yaml
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def verify_chunk_file(chunk_file: Path, verbose: bool = False):
    """Verify a single chunk file."""
    
    print(f"\n{'='*60}")
    print(f"VERIFYING CHUNK: {chunk_file.name}")
    print(f"{'='*60}\n")
    
    if not chunk_file.exists():
        print(f"❌ File not found: {chunk_file}")
        sys.exit(1)
    
    # Read file
    try:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        sys.exit(1)
    
    # Check frontmatter
    if not content.startswith('---'):
        print(f"❌ No YAML frontmatter found")
        print(f"   File must start with '---'")
        sys.exit(1)
    
    # Split frontmatter and content
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"❌ Invalid frontmatter format")
        print(f"   Must have opening and closing '---'")
        sys.exit(1)
    
    # Parse YAML
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        print(f"❌ YAML parsing error: {e}")
        sys.exit(1)
    
    print("✅ YAML frontmatter is valid\n")
    
    # Check required fields
    required_fields = {
        'chunk_id': 'Unique identifier for this chunk',
        'title': 'Descriptive title',
        'article_number': 'Article or section number'
    }
    
    missing_required = []
    for field, description in required_fields.items():
        if field not in frontmatter:
            missing_required.append(f"  • {field}: {description}")
    
    if missing_required:
        print("❌ Missing required fields:")
        for msg in missing_required:
            print(msg)
        print()
    else:
        print("✅ All required fields present\n")
    
    # Check recommended fields
    recommended_fields = {
        'keywords': 'List of search keywords',
        'semantic_type': 'Type of content (decree/rules/etc.)',
        'hierarchy': 'Document structure hierarchy'
    }
    
    missing_recommended = []
    for field, description in recommended_fields.items():
        if field not in frontmatter:
            missing_recommended.append(f"  • {field}: {description}")
    
    if missing_recommended:
        print("⚠️  Missing recommended fields:")
        for msg in missing_recommended:
            print(msg)
        print()
    
    # Validate field types
    if 'keywords' in frontmatter:
        if not isinstance(frontmatter['keywords'], list):
            print("❌ 'keywords' must be a list")
        elif len(frontmatter['keywords']) == 0:
            print("⚠️  'keywords' list is empty (add at least 3)")
        elif len(frontmatter['keywords']) < 3:
            print(f"⚠️  Only {len(frontmatter['keywords'])} keywords (recommended: 3+)")
        else:
            print(f"✅ Keywords: {len(frontmatter['keywords'])} keywords")
    
    # Check content
    chunk_content = parts[2].strip()
    content_length = len(chunk_content)
    word_count = len(chunk_content.split())
    
    if not chunk_content:
        print("❌ Chunk content is empty")
    elif content_length < 100:
        print(f"⚠️  Content is very short ({content_length} chars, {word_count} words)")
    else:
        print(f"✅ Content length: {content_length} chars, {word_count} words")
    
    # Show frontmatter if verbose
    if verbose:
        print(f"\n{'─'*60}")
        print("FRONTMATTER CONTENT:")
        print(f"{'─'*60}")
        for key, value in frontmatter.items():
            if isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            elif isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        
        print(f"\n{'─'*60}")
        print("CONTENT PREVIEW (first 300 chars):")
        print(f"{'─'*60}")
        preview = chunk_content[:300]
        if len(chunk_content) > 300:
            preview += "..."
        print(preview)
    
    # Final status
    print(f"\n{'='*60}")
    has_errors = missing_required or not chunk_content or content_length < 100
    
    if has_errors:
        print("❌ VERIFICATION FAILED - Please fix errors above")
        sys.exit(1)
    elif missing_recommended:
        print("⚠️  VERIFICATION PASSED WITH WARNINGS")
        print("Consider adding recommended fields for better search")
        sys.exit(0)
    else:
        print("✅ VERIFICATION PASSED")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description='Verify a single chunk file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'file',
        help='Path to chunk file to verify'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed frontmatter and content preview'
    )
    
    args = parser.parse_args()
    
    chunk_file = Path(args.file)
    verify_chunk_file(chunk_file, args.verbose)


if __name__ == '__main__':
    main()
