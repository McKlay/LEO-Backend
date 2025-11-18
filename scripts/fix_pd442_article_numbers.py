"""
Script to fix article_number format in PD-No-442 chunk files.
Converts from 'Article X' or 'Articles X-Y' to 'pd442_{descriptor}' format.
"""

import re
from pathlib import Path

# Mapping of filenames to proper article_number values
ARTICLE_NUMBER_MAP = {
    "10-book1-chapter2-articles25-28-private-sector-participation.md": "pd442_articles25_28_private_sector",
    "11-book1-chapter2-articles29-32-license-requirements-fees.md": "pd442_articles29_32_license_fees",
    "12-book1-chapter2-articles33-34-reports-prohibited-practices.md": "pd442_articles33_34_reports_prohibited",
    "13-book1-chapter2-articles35-36-enforcement-powers.md": "pd442_articles35_36_enforcement",
    "14-book1-chapter3-articles37-39-miscellaneous-provisions.md": "pd442_articles37_39_miscellaneous",
    "15-book1-title2-articles40-42-non-resident-aliens.md": "pd442_articles40_42_non_resident_aliens",
    "16-book2-title1-articles43-45-national-manpower-objectives.md": "pd442_articles43_45_manpower_objectives",
    "17-book2-title1-articles46-50-manpower-planning.md": "pd442_articles46_50_manpower_planning",
    "18-book2-title1-articles51-52-employment-services-incentives.md": "pd442_articles51_52_employment_incentives",
    "19-book2-title1-articles53-56-council-secretariat.md": "pd442_articles53_56_council",
    "20-book2-title2-articles57-62-apprenticeship-basics.md": "pd442_articles57_62_apprenticeship_basics",
    "21-book2-title2-articles63-72-apprenticeship-administration.md": "pd442_articles63_72_apprenticeship_admin",
    "22-book2-title2-articles73-81-learners-handicapped.md": "pd442_articles73_81_learners",
    "23-book3-title1-articles82-90-hours-of-work.md": "pd442_articles82_90_hours_work",
    "24-book3-title1-articles91-96-weekly-rest-holidays.md": "pd442_articles91_96_rest_holidays",
    "25-book3-title2-articles97-101-wages-definitions.md": "pd442_articles97_101_wage_definitions",
    "26-book3-title2-articles102-111-payment-of-wages.md": "pd442_articles102_105_wage_payment",
    "27-book3-title2-articles106-111-contractor-liability.md": "pd442_articles106_111_contractor_liability",
    "28-book3-title2-articles112-119-wage-prohibitions.md": "pd442_articles112_119_wage_prohibitions",
    "29-book3-title2-articles120-121-wage-commission.md": "pd442_articles120_121_wage_commission",
    "30-book3-title2-articles122-regional-wage-boards.md": "pd442_article122_wage_boards",
    "31-book3-title2-articles123-127-wage-standards.md": "pd442_articles123_127_wage_standards",
    "32-book3-title2-articles128-129-wage-administration.md": "pd442_articles128_129_wage_admin",
    "33-book3-title3-ch1-articles130-138-employment-women.md": "pd442_articles130_138_employment_women",
    "34-book3-title3-ch2-articles139-140-employment-minors.md": "pd442_articles139_140_employment_minors",
    "35-book3-title3-ch3-articles141-152-househelpers.md": "pd442_articles141_152_househelpers",
    "36-book3-title3-ch4-articles153-155-homeworkers.md": "pd442_articles153_155_homeworkers",
    "37-book4-title1-ch1-articles156-161-medical-dental.md": "pd442_articles156_161_medical_dental",
    "38-book4-title1-ch2-articles162-165-occupational-safety.md": "pd442_articles162_165_occupational_safety",
    "39-book4-title2-ch1-articles166-167-policy-definitions.md": "pd442_articles166_167_policy_definitions",
    "40-book4-title2-ch2-articles168-175-coverage-liability.md": "pd442_articles168_175_coverage_liability",
    "41-book4-title2-ch3-articles176-182-administration-ecc.md": "pd442_articles176_182_ecc_admin",
    "42-book4-title2-ch4-ch5-articles183-190-contributions-medical.md": "pd442_articles183_190_contributions",
    "43-book4-title2-ch6-articles191-193-disability-benefits.md": "pd442_articles191_193_disability",
    "44-book4-title2-ch7-ch8-articles194-204-death-benefits.md": "pd442_articles194_204_death_benefits",
    "45-book4-title2-ch9-articles205-208-records-penal.md": "pd442_articles205_208a_records_penal",
    "46-book4-titles3-4-articles209-210-medicare-education.md": "pd442_articles209_210_medicare",
    "47-book5-title1-articles211-212-labor-relations-policy.md": "pd442_articles211_212_labor_policy",
    "48-book5-title2-chapter1-articles213-216-nlrc-creation.md": "pd442_articles213_216_nlrc",
    "49-book5-title2-chapter2-3-articles217-225-nlrc-powers.md": "pd442_articles217_225_nlrc_powers",
    "50-book5-title3-articles226-233-bureau-labor-relations.md": "pd442_articles226_233_bureau_labor",
    "51-book5-title4-chapter1-articles234-240-union-registration.md": "pd442_articles234_240_union_registration",
    "52-book5-title4-chapter2-article241-part1-membership-rights.md": "pd442_article241_part1_membership",
    "53-book5-title4-chapter2-article241-part2-financial-accountability.md": "pd442_article241_part2_financial",
    "54-book5-title4-chapter3-title5-articles242-246-union-rights-coverage.md": "pd442_articles242_246_union_rights",
    "55-book5-title6-articles247-249-unfair-labor-practices.md": "pd442_articles247_249_unfair_practices",
    "56-book5-title7-articles250-259-collective-bargaining.md": "pd442_articles250_259_collective_bargaining",
    "57-book5-title7a-articles260-262b-grievance-voluntary-arbitration.md": "pd442_articles260_262b_grievance",
    "58-book5-title8-chapter1-article263-strikes-lockouts-policy.md": "pd442_article263_strikes_policy",
    "59-book5-title8-chapter1-articles264-266-prohibited-acts.md": "pd442_articles264_266_prohibited_acts",
    "60-book5-title8-chapter2-3-articles267-271-assistance-foreign-activities.md": "pd442_articles267_271_assistance",
    "61-book5-title8-chapter4-article272-penalties.md": "pd442_article272_penalties",
    "62-book5-title9-articles273-277-special-provisions.md": "pd442_articles273_277_special_provisions",
    "63-book6-title1-articles278-286-termination-employment.md": "pd442_articles278_286_termination",
    "64-book6-title2-book7-articles287-302-retirement-penal-provisions.md": "pd442_articles287_302_retirement_penal",
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
    chunks_dir = Path(__file__).parent.parent / "kb" / "chunks" / "PD-No-442"
    
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
