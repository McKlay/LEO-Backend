"""
Script to fix article_number format in RA-No-11058 chunk files.
Converts from 'RA-11058-XX' to 'ra11058_{descriptor}' format.
"""

import re
from pathlib import Path

# Mapping of filenames to proper article_number values
ARTICLE_NUMBER_MAP = {
    "01-preamble-chapter1.md": "ra11058_preamble_chapter1",
    "02-chapter2-coverage-definitions-part1.md": "ra11058_chapter2_coverage_definitions_part1",
    "03-chapter2-definitions-part2.md": "ra11058_chapter2_definitions_part2",
    "04-chapter3-duties-right-to-know.md": "ra11058_chapter3_duties_right_to_know",
    "05-chapter3-workers-rights.md": "ra11058_chapter3_workers_rights",
    "06-chapter4-osh-program-committee.md": "ra11058_chapter4_osh_program_committee",
    "07-chapter4-safety-officer-personnel-training.md": "ra11058_chapter4_safety_officer_personnel_training",
    "08-chapter4-competency-welfare-cost.md": "ra11058_chapter4_competency_welfare_cost",
    "09-chapter5-6-liability-enforcement.md": "ra11058_chapter5_6_liability_enforcement",
    "10-chapter6-standards-compensation-penalties.md": "ra11058_chapter6_standards_compensation_penalties",
    "11-chapter7-miscellaneous-final.md": "ra11058_chapter7_miscellaneous_final",
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
    chunks_dir = Path(__file__).parent.parent / "kb" / "chunks" / "RA-No-11058"
    
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
