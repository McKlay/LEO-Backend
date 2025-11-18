"""
Script to fix article_number format in RA-No-10361 chunk files.
Converts from 'RA-10361-XX' to 'ra10361_{descriptor}' format.
"""

import re
from pathlib import Path

# Mapping of filenames to proper article_number values
ARTICLE_NUMBER_MAP = {
    "01-preamble-article1.md": "ra10361_preamble_article1",
    "02-article2-rights.md": "ra10361_article2_rights",
    "03-article3-contract-requirements.md": "ra10361_article3_contract_requirements",
    "04-article3-prohibitions-duties.md": "ra10361_article3_prohibitions_duties",
    "05-article4-work-conditions.md": "ra10361_article4_work_conditions",
    "06-article4-wages.md": "ra10361_article4_wages",
    "07-article4-benefits.md": "ra10361_article4_benefits",
    "08-article5-termination.md": "ra10361_article5_termination",
    "09-articles6-8-agencies-disputes.md": "ra10361_articles6_8_agencies_disputes",
    "10-articles9-10-final.md": "ra10361_articles9_10_final",
}


def fix_article_number(file_path: Path, new_article_number: str):
    """Fix article_number in a single chunk file."""
    content = file_path.read_text(encoding='utf-8')
    
    # Pattern to match article_number line (handles quotes and no quotes)
    pattern = r'article_number:\s*["\']?.*?["\']?\s*\n'
    replacement = f'article_number: {new_article_number}\n'
    
    new_content = re.sub(pattern, replacement, content, count=1)
    
    if new_content != content:
        file_path.write_text(new_content, encoding='utf-8')
        return True
    return False


def main():
    chunks_dir = Path(__file__).parent.parent / "kb" / "chunks" / "RA-No-10361"
    
    if not chunks_dir.exists():
        print(f"Error: Directory not found: {chunks_dir}")
        return
    
    fixed_count = 0
    error_count = 0
    
    for filename, new_article_number in ARTICLE_NUMBER_MAP.items():
        file_path = chunks_dir / filename
        
        if not file_path.exists():
            print(f"⚠️  File not found: {filename}")
            error_count += 1
            continue
        
        try:
            if fix_article_number(file_path, new_article_number):
                print(f"✓ Fixed: {filename} -> {new_article_number}")
                fixed_count += 1
            else:
                print(f"⚠️  No change needed: {filename}")
        except Exception as e:
            print(f"❌ Error fixing {filename}: {e}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Fixed: {fixed_count} files")
    print(f"  Errors: {error_count} files")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
