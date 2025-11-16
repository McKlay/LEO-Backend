#!/usr/bin/env python3
"""
Create a new document template for manual chunking.

Creates a new folder with metadata.json template and initial chunk file
structure.

Usage:
    # Create template with metadata
    python scripts/ingestion/create_template.py \\
        --name "RA-No-10361" \\
        --source "Republic Act No. 10361" \\
        --reference "RA 10361" \\
        --short-name "Domestic Workers Act" \\
        --type statute \\
        --year 2013
    
    # Create minimal template
    python scripts/ingestion/create_template.py --name "RA-No-10361"
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


METADATA_TEMPLATE = {
    "source": "",
    "reference": "",
    "short_name": "",
    "doc_type": "statute",
    "year": "",
    "url": "",
    "total_chunks": 0,
    "chunking_strategy": "manual",
    "last_updated": "",
    "notes": "Manual chunking in progress"
}

CHUNK_TEMPLATE = """---
chunk_id: {chunk_id}
title: {title}
article_number: {article_number}
semantic_type: decree
hierarchy:
  part: Main Document
  sections: Section 1
keywords:
  - keyword1
  - keyword2
  - keyword3
has_table: false
has_formula: false
has_list: false
---

# {title}

## Section 1

[Content goes here]
"""


def create_document_template(
    name: str,
    source: str = "",
    reference: str = "",
    short_name: str = "",
    doc_type: str = "statute",
    year: str = "",
    url: str = ""
) -> Path:
    """Create a new document template folder."""
    
    chunks_dir = project_root / 'kb' / 'chunks'
    document_folder = chunks_dir / name
    
    # Check if folder exists
    if document_folder.exists():
        print(f"❌ Document folder already exists: {name}")
        sys.exit(1)
    
    # Create folder
    document_folder.mkdir(parents=True, exist_ok=True)
    print(f"✅ Created folder: {document_folder}")
    
    # Create metadata.json
    metadata = METADATA_TEMPLATE.copy()
    metadata['source'] = source or f"[Document Source - {name}]"
    metadata['reference'] = reference or name
    metadata['short_name'] = short_name or name
    metadata['doc_type'] = doc_type
    metadata['year'] = year or str(datetime.now().year)
    metadata['url'] = url
    metadata['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    
    metadata_file = document_folder / 'metadata.json'
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Created metadata: {metadata_file.name}")
    
    # Create sample chunk file
    chunk_content = CHUNK_TEMPLATE.format(
        chunk_id=f"{name.lower().replace('-', '_')}_01",
        title=f"{short_name or name} - Main Provisions",
        article_number=name
    )
    
    chunk_file = document_folder / '01-main-provisions.md'
    with open(chunk_file, 'w', encoding='utf-8') as f:
        f.write(chunk_content)
    
    print(f"✅ Created sample chunk: {chunk_file.name}")
    
    # Create README
    readme_content = f"""# {name}

## Document Information

- **Source**: {metadata['source']}
- **Reference**: {metadata['reference']}
- **Type**: {metadata['doc_type']}
- **Year**: {metadata['year']}

## Chunking Status

- **Total Chunks**: {metadata['total_chunks']} (update metadata.json after chunking)
- **Last Updated**: {metadata['last_updated']}

## Next Steps

1. Read the source document
2. Plan chunk boundaries (see kb/chunks/README.md for guidelines)
3. Create chunk files (01-*.md, 02-*.md, etc.)
4. Update metadata.json with correct total_chunks
5. Validate: `python scripts/ingestion/validate_chunks.py --document {name}`
6. Ingest: `python scripts/ingestion/ingest_manual.py --folder {name}`

## Guidelines

- Each chunk should be semantically complete
- Target: 200-800 words per chunk
- Use descriptive filenames: `{"{number}"}-{"{section-type}"}-{"{description}"}.md`
- Include all required YAML frontmatter fields
- Add at least 3 keywords per chunk

See `kb/chunks/PD-No-851/` for a complete example.
"""
    
    readme_file = document_folder / 'README.md'
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ Created README: {readme_file.name}")
    
    return document_folder


def main():
    parser = argparse.ArgumentParser(
        description='Create new document template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required
    parser.add_argument(
        '--name',
        required=True,
        help='Document folder name (e.g., RA-No-10361)'
    )
    
    # Optional metadata
    parser.add_argument(
        '--source',
        help='Full source name (e.g., "Republic Act No. 10361")'
    )
    parser.add_argument(
        '--reference',
        help='Short reference (e.g., "RA 10361")'
    )
    parser.add_argument(
        '--short-name',
        help='Common name (e.g., "Domestic Workers Act")'
    )
    parser.add_argument(
        '--type',
        default='statute',
        choices=['statute', 'department_order', 'procedural_rules', 'handbook'],
        help='Document type'
    )
    parser.add_argument(
        '--year',
        help='Year of enactment'
    )
    parser.add_argument(
        '--url',
        help='Source URL'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("CREATE DOCUMENT TEMPLATE")
    print(f"{'='*60}\n")
    
    try:
        document_folder = create_document_template(
            name=args.name,
            source=args.source or "",
            reference=args.reference or "",
            short_name=args.short_name or "",
            doc_type=args.type,
            year=args.year or "",
            url=args.url or ""
        )
        
        print(f"\n{'='*60}")
        print("✅ TEMPLATE CREATED SUCCESSFULLY")
        print(f"{'='*60}")
        print(f"\nFolder: {document_folder}")
        print(f"\nNext steps:")
        print(f"1. Edit metadata.json with correct information")
        print(f"2. Create chunk files based on source document")
        print(f"3. Validate: python scripts/ingestion/validate_chunks.py --document {args.name}")
        print(f"4. Ingest: python scripts/ingestion/ingest_manual.py --folder {args.name}")
        
    except Exception as e:
        print(f"\n❌ Failed to create template: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
