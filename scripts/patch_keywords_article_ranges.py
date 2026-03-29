"""
Patch: enumerate all article numbers for multi-article chunks in keywords[].

Multi-article sections (e.g., article_number='pd442_articles97_101_wage_definitions')
were ingested with only one representative article number in keywords[] instead of
the full range. This script finds all such sections, parses the range, and adds the
missing "Article N" entries to keywords[] so GIN symbolic lookup can find them.

Safe to re-run (idempotent — only adds terms not already present).
"""
import re
import psycopg2
from core.config import settings


def parse_article_range(article_number: str) -> list[int]:
    """
    Extract a list of article numbers from an article_number slug.

    Examples:
      'pd442_articles97_101_wage_definitions' → [97, 98, 99, 100, 101]
      'pd442_articles57_62_apprenticeship_basics' → [57, 58, 59, 60, 61, 62]
      'ra10361_article3_prohibitions_duties' → [3]   (single article)
      'pd851_decree_sec1_3' → []  (section-based, not article-range)
    """
    # Multi-article: articles<N>_<M>  (e.g., articles97_101)
    m = re.search(r'articles?(\d+)_(\d+)', article_number, re.IGNORECASE)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        if 1 <= start <= end <= start + 30:  # cap range to prevent runaway expansion
            return list(range(start, end + 1))
    # Single article: article<N>
    m = re.search(r'article(\d+)', article_number, re.IGNORECASE)
    if m:
        return [int(m.group(1))]
    return []


conn = psycopg2.connect(settings.supabase_db_url)
cur = conn.cursor()

# Fetch all sections with their current keywords
cur.execute("SELECT id, article_number, keywords FROM labor_law_sections")
rows = cur.fetchall()

patched = 0
skipped = 0

for row_id, article_number, current_keywords in rows:
    article_nums = parse_article_range(article_number)
    if not article_nums:
        skipped += 1
        continue

    needed = [f"Article {n}" for n in article_nums]
    current_set = set(current_keywords or [])

    missing = [term for term in needed if term not in current_set]
    if not missing:
        skipped += 1
        continue

    updated = list(current_set | set(missing))
    cur.execute(
        "UPDATE labor_law_sections SET keywords = %s WHERE id = %s",
        (updated, row_id),
    )
    print(f"  PATCHED {article_number}  added={missing}")
    patched += 1

conn.commit()
cur.close()
conn.close()

print(f"\nDone: {patched} sections patched, {skipped} skipped (already complete or non-article).")
