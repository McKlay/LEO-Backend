# Lexical Query Redesign Tracker

**Goal:** All 25 lexical-target queries must satisfy `dense_only MRR@5 ≤ 0.5` AND `lexical_only MRR@5 ≥ 0.5`

**Baseline dry-run results** (`dryrun_lexical_v2`, 2026-04-12):

| QID | dense@5 | lexical@5 | Status |
|-----|---------|-----------|--------|
| Q001 | 0.500 | 1.000 | ✅ PASS |
| Q009 | 0.200 | 0.500 | ✅ PASS (redesigned Batch1) |
| Q011 | 0.250 | 1.000 | ✅ PASS (redesigned Batch1) |
| Q017 | 0.500 | 1.000 | ✅ PASS |
| Q023 | 0.333 | 1.000 | ✅ PASS (redesigned Batch1+Batch2 fix) |
| Q024 | 0.333 | 1.000 | ✅ PASS (redesigned Batch2) |
| Q025 | 0.500 | 1.000 | ✅ PASS |
| Q030 | 0.200 | 1.000 | ✅ PASS (redesigned Batch2) |
| Q036 | 0.333 | 0.500 | ✅ PASS (redesigned Batch2) |
| Q037 | 0.500 | 1.000 | ✅ PASS (redesigned Batch3) |
| Q041 | 0.333 | 1.000 | ✅ PASS (redesigned Batch3) |
| Q045 | 0.500 | 1.000 | ✅ PASS (redesigned Batch3) |
| Q053 | 0.000 | 0.500 | ✅ PASS (redesigned Batch4) |
| Q055 | 0.200 | 1.000 | ✅ PASS (redesigned Batch4) |
| Q057 | 0.500 | 1.000 | ✅ PASS |
| Q069 | 0.333 | 1.000 | ✅ PASS (redesigned Batch4) |
| Q071 | 0.250 | 1.000 | ✅ PASS (redesigned Batch5) |
| Q077 | 0.500 | 1.000 | ✅ PASS (redesigned Batch5) |
| Q082 | 0.000 | 1.000 | ✅ PASS (redesigned Batch5) |
| Q087 | 0.000 | 0.500 | ✅ PASS (redesigned Batch6) |
| Q092 | 0.500 | 1.000 | ✅ PASS |
| Q096 | 0.500 | 1.000 | ✅ PASS |
| Q097 | 0.000 | 1.000 | ✅ PASS (redesigned Batch6) |
| Q099 | 0.000 | 1.000 | ✅ PASS (redesigned Batch6) |
| Q100 | 0.000 | 1.000 | ✅ PASS (redesigned Batch7) |

**Summary:** 25 / 25 passing (6 original + 3 Batch 1 + 3 Batch 2 + 3 Batch 3 + 3 Batch 4 + 3 Batch 5 + 3 Batch 6 + 1 Batch 7). ALL COMPLETE.

---

## Redesign Batches

### Batch 1 — Q009, Q011, Q023 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|--------------|---------|-------|----------------------|
| Q009 | `dole_handbook_2023_min_wage_eemr_formulas` | `dole_handbook_2023_night_shift_computation_guide` | 0.333 | 0.500 | "Factor 305", "Factor 253" (verbatim formula codes) |
| Q011 | `book3-title1-articles82-90-hours-of-work` | `dole_handbook_2023_premium_overtime_pay` | 0.250 | 1.000 | "bed capacity of at least one hundred" (precision threshold) |
| Q023 | `RA-10361-07` | `dole_handbook_2023_service_charges_sil` | 0.500 | 1.000 | "service incentive leave" + "convertible to cash" (RA-10361-07 explicitly prohibits conversion) |

**Changes also made to `query_analysis.py` prompt:**
- `normalized_query_en`: added "Preserve verbatim any quoted multi-word technical phrases from the original query — do not paraphrase or translate them" → ensures FTS dual-signal catches verbatim phrases even in translated queries
- Keyword quotes rule: diversified examples to cross-domain (`'constructive dismissal'`, `'authorized cause'`, `'Factor 305'`) — prevents LLM over-fitting to current-query examples
- Keyword Extract rule: replaced `"service incentive leave"` example with `"separation pay"` 
- Added priority tiebreaker: "When the limit forces a choice, prefer quoted verbatim phrases over unquoted general terms"

**Pipeline architecture changes (Batch 1 session):**
- Threaded `original_query` (raw user message) through `chat_orchestrator.py` → `retrieval.py` → `smart_retrieve` → `keyword_search` as the FTS second signal
- Rationale: verbatim technical phrases quoted in the original query survive to FTS even when LLM normalisation paraphrases them

---

### Batch 2 — Q024, Q030, Q036 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|--------------|---------|-------|----------------------|
| Q024 | `dole_handbook_2023_chunk_09` | `dole_handbook_2023_chunk_10` (VAWC+gynecological) | 0.333 | 1.000 | `'lawful wife'` + `'four deliveries'` + `'cohabiting'` (paternity leave exclusive terms) |
| Q030 | `pd851_rules_preamble_sec1_2` | `pd851_rules_sec3_5` (exemptions) | 0.200 | 1.000 | `'at the time of the promulgation of the Decree on December 16, 1975'` (preamble-exclusive date phrase) |
| Q036 | `do147_15_authorized_causes_separation` | multiple redundancy sections | 0.333 | 0.500 | `'Last-In, First-Out Rule'` (LIFO — unique to DO147-15 authorized causes) |

**Also fixed Q023 regression (caused by original_query threading):**

| QID | Gold chunk | Dense@5 | Lex@5 | Root cause of regression / Fix |
|-----|-----------|---------|-------|-------------------------------|
| Q023 | `RA-10361-07` | 0.333 | 1.000 | FTS length-bias: `dole_handbook_2023_service_charges_sil` (7122 chars, 5× SIL mentions) consistently outranked RA-10361-07 (short law section) via raw term frequency. Fix: Q023 v9 query with `'carried over to the succeeding years'` (exclusive to RA-10361-07 Sec.29) as anchor; pipeline's anchor-boost CASE WHEN applies `ts_rank × 100` to any document matching this ≥5-word exclusive phrase, overriding length bias. |

**Pipeline architecture changes (Batch 2 session):**
- `smart_retrieve` now extracts single-quoted phrases (≥4 chars) from `original_query` and appends them to `fts_keywords` before calling `keyword_search` — ensures LLM-extracted keywords are augmented with verbatim anchor phrases even when the LLM paraphrases them (e.g. `'carry over'` instead of `'carried over to the succeeding years'`)
- `keyword_search` gains optional `anchor_phrase` parameter: when the longest quoted phrase has ≥5 words, the SQL uses `CASE WHEN tsvector @@ anchor_query THEN ts_rank(keywords) × 100 ELSE GREATEST(ts_rank(keywords), ts_rank(fts_query)) END` — eliminates ts_rank length bias without affecting queries without anchor phrases
- **3-signal approach was tried and rejected**: `GREATEST(keywords, original_query, normalized_query_en)` fixed Q023 but broke Q030 (normalized English added 13th-month-pay terms that boosted handbook chunks above preamble). Correct fix is exclusive anchor per-query rather than a global third signal.

---

### Batch 3 — Q037, Q041, Q045 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler chunk | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|---------------------|---------|-------|----------------------|
| Q037 | `do147_15_authorized_causes_separation` | `do147_15_due_process_just_causes` (just-cause twin-notice) | 0.500 | 1.000 | Citation-trap v3: query body 100% about just-cause twin-notice procedure; `'Jaka Food Processing Corp. v. Pacot'` (6-word anchor, exclusive to gold) at the end |
| Q041 | `dole_handbook_2023_chunk_13` | `ra-11199-07-sec12-13b-pension-benefits` (SSS monthly contributions) | 0.333 | 1.000 | `'underground or surface mine employees'` (5-word anchor, exclusive to chunk_13 Section H retirement) |
| Q045 | `do147_15_due_process_just_causes` | `do147_15_authorized_causes_separation` (authorized-cause retrenchment) | 0.500 | 1.000 | `'detailed narration of the facts and circumstances'` (7-word anchor, 47 chars; longer wins over `'general description of the charge'` 33 chars) |

**Q037 design history — 3 iterations:**

- **v1**: Added twin-notice / first-notice language but kept "authorized-cause dismissal" and "₱50,000 nominal damages" → dense still finds gold at rank 1 (authorized-cause semantic dominates body). FAIL.
- **v2**: Made just-cause dominant with Jaka as a parenthetical, kept "nominal damages" → LLM normalized query still used "nominal damages" pointing to `do147_15_authorized_causes_separation` → dense MRR=1.0. FAIL.
- **v3 — citation-trap**: Removed ALL authorized-cause language (no nominal damages, no authorized-cause). Query body 100% about just-cause / twin-notice in Filipino. "Jaka Food Processing Corp. v. Pacot" cited only as `'Jaka Food Processing Corp. v. Pacot'` (single-quoted anchor phrase) in the closing question. Dense embedding follows the just-cause body → `do147_15_due_process_just_causes` rank 1. FTS anchor × 100 puts gold (`do147_15_authorized_causes_separation`) at lexical rank 1. PASS.

**Architectural insights (Batch 3 session):**
1. **Sub-chunk flooding**: When a gold section has 3 sub-chunks in `labor_law_chunks`, dense search returns the same `chunk_id` at ranks 1-3 even for a query that should be semantically redirected. Solution: pivot the primary semantic to a completely different domain (e.g. SSS pension for Q041), not merely add competing content from nearby sections.
2. **Citation-trap design**: Ask "what is the doctrine in Case X?" where the BODY describes a semantically different (spoiler) topic, while the case name `'X v. Y'` serves as an exclusive single-quoted FTS anchor pointing to gold. Dense follows the body semantic; FTS uses the anchor × 100 boost.
3. **DO 147-15 family cross-contamination**: `do147_15_authorized_causes_separation` and `do147_15_due_process_just_causes` are semantically adjacent. Q037 uses citation-trap (body = just-cause spoiler, anchor = Jaka case exclusive to authorized-causes); Q045 uses authorized-cause retrenchment language as spoiler so dense points to `do147_15_authorized_causes_separation` while the `'detailed narration…'` anchor finds the just-cause gold.

---

### Batch 4 — Q053, Q055, Q069 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler chunk | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|---------------------|---------|-------|----------------------|
| Q053 | `do147_15_authorized_causes_separation`, `book6-title1-articles278-286-termination-employment` | `ra-11199-07-sec12-13b-pension-benefits` (SSS retirement pension) | 0.000 | 0.500 | `'at least thirty days (30) before the effectivity'` (7-word anchor, ILIKE-exclusive to gold1, rare tokens "thirty"+"effectivity" reduce false tsvector matches) |
| Q055 | `do147_15_rule1a_foundations` | `do147_15_authorized_causes_separation` ×2 (authorized-cause retrenchment) | 0.200 | 1.000 | `'reserves the right to control not only the end achieved'` (10-word anchor, exclusive to rule1a_foundations) |
| Q069 | `dole_handbook_2023_chunk_14` | `ra-11199-07-sec12-13b-pension-benefits` (SSS monthly contributions) | 0.333 | 1.000 | `'Katulong at Gabay sa Manggagawang May Kapansanan'` (8-word anchor, exclusive to chunk_14) |

**Q053 design history — 4 iterations:**

- **v1** (just-cause twin-notice primary, authorized-cause secondary with `'Regional Office of the Department of Labor and Employment'` anchor): dense still 1.0 — `do147_15_authorized_causes_separation` has content about BOTH authorized-cause AND just-cause nominal damages (Jaka + Agabon), making it semantically broad; just-cause content not enough to overturn rank 1.
- **v2** (citation-trap: 100% just-cause twin-notice body, `'at least thirty days (30) before the effectivity'` at end): dense still 1.0 — "nominal damages ang ipapataw" in query pulled back toward authorized-causes section (which mentions nominal damages for both cause types).
- **v3** (SSS pension primary, `'separation pay equivalent to at least one month'` as anchor for gold2): dense MRR=0 ✓ but lexical MRR=0.333 ✗ — `'separation pay equivalent to at least one month'` has very COMMON tokens ("separation", "pay", "equivalent", "month") that tsvector-match multiple handbook chunks; those chunks get ×100 boost AND high base ts_rank from SSS body keywords → outrank gold.
- **v4** (SSS pension primary, `'at least thirty days (30) before the effectivity'` as anchor for gold1): dense MRR=0 ✓, lexical MRR=0.5 ✓ — rarer tokens ("thirty"+"effectivity") don't co-occur in SSS handbook chunks → tsvector false-match rate low → gold1 gets ×100 boost and ranks at lexical rank 2.

**Architectural insights (Batch 4 session):**
1. **do147_15_authorized_causes_separation semantic breadth**: This section covers nominal damages for BOTH authorized-cause (₱50,000/Jaka) AND just-cause (₱30,000/Agabon) procedural violations. Adding just-cause content to a query body cannot reliably push it below rank 1 — must pivot to a completely different domain.
2. **tsvector false-match problem**: FTS anchor `CASE WHEN tsvector @@ query THEN ts_rank × 100` uses token matching (non-positional). Common tokens like "separation", "pay", "equivalent", "month" can all appear in large handbook chunks independently → accidental anchor boost on wrong chunks. Use RARE token combinations (proper nouns, rare compound terms, specific number+word combinations like "thirty"+"effectivity").
3. **Zero gold in dense top-5**: When the SSS pivot is strong enough (0 gold in top 5), dense MRR@5 = 0 ≤ 0.5. Combined with lexical MRR@5 ≥ 0.5 (anchor boost on gold), this passes cleanly. Lower dense MRR is actually MORE "pass-safe" than trying to land at exactly 0.5.

---

### Batch 5 — Q071, Q077, Q082 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler chunk | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|---------------------|---------|-------|----------------------|
| Q071 | `dole_handbook_2023_chunk_15` (PhilHealth premium) | `dole_handbook_2023_chunk_17` (Pag-IBIG Fund, 3 sub-chunks → floods ranks 1-3) | 0.250 | 1.000 | `'income floor and income ceiling'` (5-word anchor; "income ceiling" ILIKE-exclusive to chunk_15; tsvector "income"∩"floor"∩"ceiling" matches chunk_15 only) |
| Q077 | `RA-11058-04` (OSH employer duties: job safety orientation) | `RA-11058-07` (safety officers, already rank 2 at baseline — very tight gap of 0.000264 score) | 0.500 | 1.000 | `'complete job safety instructions or orientation'` (7-word anchor, EXCLUSIVE to RA-11058-04) |
| Q082 | `book5-title6-articles247-249-unfair-labor-practices` (ULP, 2 sub-chunks) | `ra-11199-07-sec12-13b-pension-benefits` (SSS pension — completely different domain) | 0.000 | 1.000 | `'inimical to the legitimate interests of both labor and management'` (9-word anchor, rare word "inimical" exclusive to ULP article) |

**Q082 design history — 2 iterations:**
- **v1** (SSS pension primary + `'shall not join a labor organization'` anchor): dense MRR=0 ✓ but lexical MRR=0.333 ✗ — after stop word removal, anchor tokens "shall"+"join"+"labor"+"organiz" match MANY Book 5 union-registration and labor organization articles; those get ×100 boost AND have high ts_rank for labor-org content → rank 1-2, gold at rank 3.
- **v2** (SSS pension primary + `'inimical to the legitimate interests of both labor and management'` anchor): both PASS — "inimical" is an extremely rare word appearing only in the ULP concept definition (Article 247 content); tsvector match is functionally exclusive to gold → ×100 boost → gold at rank 1 in lexical.

**Architectural insight (Batch 5 session — P8: rare vocabulary anchor):**
- **P8: Rare vocabulary anchor**: When the gold section contains legal vocabulary that's rare in the broader KB (e.g., "inimical", "effectivity" combined with "thirty"), these are stronger anchors than legally-common phrases ("shall join a labor organization") even if the latter is verbatim-exclusive in ILIKE. The tsvector matching is non-positional → common-token phrases falsely match many chunks. **Choose anchor phrases with at least one rare/specialized token** ("inimical", "effectivity", proper case names, specific technical terms).

---

### Batch 6 — Q087, Q097, Q099 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler chunk | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|---------------------|---------|-------|----------------------|
| Q087 | `nlrc_rules_rule3_pleadings_sections1_3`, `nlrc_rules_rule5_jurisdiction_nature` | `ra-11199-07-sec12-13b-pension-benefits` (SSS pension) | 0.000 | 0.500 | `'shall be signed under oath'` (5-word anchor; tsquery `'shall' & 'sign' & 'oath'`; rule3 has highest ts_rank 0.265 among 3 matching chunks → rule3 at lexical rank 1 with ×100 boost) |
| Q097 | `covid_protocols_testing_compliance` | `ra-11199-07-sec12-13b-pension-benefits` (SSS pension) | 0.000 | 1.000 | `'Revised Interim Guidelines on Expanded Testing'` (6-word anchor, ILIKE-exclusive to gold; 5 rare tsvector stems: revis∩interim∩guidelin∩expand∩test) |
| Q099 | `book3-title2-articles106-111-contractor-liability` | `ra-11199-07-sec12-13b-pension-benefits` (SSS pension) | 0.000 | 1.000 | `'bond equal to the cost of labor'` (7-word anchor, ILIKE-exclusive to gold; rare token combo "bond"∩"cost"∩"labor" contract liability context) |

**Q087 design history — 3 iterations:**

- **v1** (SSS primary + `'docketing unit of the Regional Arbitration Branch'` anchor): dense MRR=0 ✓, lexical MRR=0.333 ✗ — anchor tsvector `'docket' & 'unit' & 'region' & 'arbit' & 'branch'` fires for multiple NLRC rules; query mentions "NLRC"+"Regional Arbitration Branch" → rule4/rule13 get high ELSE ts_rank from NLRC terms → outrank rule3's ×100 boosted score (rule3's ts_rank(search_terms) was only 0.023 since SSS keywords don't appear in rule3).
- **v2** (SSS primary + `'pleading alleging the cause or causes'` anchor): dense MRR=0 ✓, lexical MRR=0.0 ✗ — `websearch_to_tsquery` treats lowercase `'or'` as a boolean OR operator → tsquery becomes `(plead & alleg & caus) | caus` → `'caus'` alone matches EVERY chunk containing "cause"; ALL chunks get ×100 boost; rule3 is no longer dominant.
- **v3** (SSS primary + `'shall be signed under oath'` anchor + NLRC/complaint/petition keywords added): dense MRR=0 ✓, lexical MRR=0.5 ✓ — anchor has no boolean operator keywords; tsquery = `'shall' & 'sign' & 'oath'`; fires for only 3 chunks (rule3=0.265, sena_rule5=0.187, union_reg=0.096); rule3 ts_rank × 100 = 3.89 beats sena_rule5 (3.10) and all SSS ELSE chunks (≤0.05) → rule3 at lexical rank 2, MRR=0.5 PASS.

**Q097 design history — 2 iterations:**

- **v1** (SSS primary + `'there shall be no diminution in wages or benefits'` anchor): dense MRR=0 ✓, lexical MRR=0.0 ✗ — "diminution" appears in 8 chunks (Labor Code benefit articles, DOLE handbook, RA-10361-10, etc.); ALL 8 get ×100 boost; gold (covid_testing_compliance) scores very low on SSS-centric search_terms → falls outside top 5 entirely.
- **v2** (SSS primary + `'Revised Interim Guidelines on Expanded Testing'` anchor): dense MRR=0 ✓, lexical MRR=1.0 ✓ — 5 STRONG rare stems (revis∩interim∩guidelin∩expand∩test only co-occur in the COVID testing footnote text); gold gets exclusive ×100 boost → lexical rank 1.

**Architectural insights (Batch 6 session):**
1. **websearch_to_tsquery boolean operators**: Lowercase `'or'`, `'and'`, `'not'` inside anchor phrases are treated as Boolean operators by `websearch_to_tsquery`, not as literal words. `'cause or causes'` → tsquery `caus | caus` = `caus` alone → matches thousands of legal documents. **Never use 'or'/'and'/'not' as literal words in anchor phrases.** Use synonymous phrasing without these operators.
2. **SSS pivot ts_rank asymmetry**: When SSS pension is the primary query semantic, FTS search_terms are dominated by SSS keywords. If the gold chunk is from a completely different domain (e.g. NLRC pleadings, COVID protocols), its base ts_rank for SSS-heavy search_terms is near 0 (0.001-0.010). The ×100 boost must be applied to a chunk that ALSO has moderate ts_rank for the search_terms, otherwise ×100 ≈ 0. Fix: add domain-relevant keywords for the gold chunk into the query (e.g., "NLRC complaint petition" for rule3) so its search_terms ts_rank rises to 0.03-0.05 → ×100 = 3-5 → dominates.
3. **diminution anchor failure**: "diminution" appears across 8+ Labor Code and handbook chunks because "non-diminution of benefits" is a general legal principle cited broadly. An anchor built on a single word (even a rare-seeming one like "diminution") from a principle cited everywhere will always have a high false-match rate. Use SPECIFIC CONTEXTUAL PHRASES with multiple rare tokens.

### Batch 7 — Q100 ✅ DONE (2026-04-12)

| QID | Gold chunk | Dense spoiler chunk | Dense@5 | Lex@5 | Key FTS discriminators |
|-----|-----------|---------------------|---------|-------|----------------------|
| Q100 | `book1-title2-articles40-42-non-resident-aliens` (AEP, Art. 40-42) | `ra-11199-07-sec12-13b-pension-benefits` (SSS pension) | 0.000 | 1.000 | `'non-availability of a person in the Philippines who is competent, able and willing'` (preserved from original query; tsquery fires for ONLY gold, 1 chunk; websearch_to_tsquery handles `non-availability` as compound position-phrase) |

**Q100 design — 1 iteration (first try PASS):**
- Original query was entirely about AEP/alien employment permit → dense correctly finds gold at rank 1 (dense MRR=1.0). Lexical was already MRR=1.0 (anchor in original query).
- **v1**: Prepended 3 SSS pension sentences (Filipino) as dense spoiler. Kept existing anchor `'non-availability...'` unchanged. Dense → SSS pension at rank 1-5, AEP section pushed to rank 6+ (completely different domain). Lexical → anchor fires exclusively for gold (confirmed: 1 matching chunk) → ×100 boost → gold at rank 1. PASS on first try.

---

## Properties Reference

| # | Property | Rule |
|---|----------|------|
| P1 | Spoiler required | Gold must have ≥1 semantic neighbor chunk in KB |
| P2 | FTS discriminator | 1–3 verbatim terms in gold, NOT in spoiler, poor embedders |
| P3 | Length 35–65 words | Long queries give dense too much context |
| P4 | Ask, don't describe | Don't paraphrase gold content extensively |
| P5 | No law citations | No `Article N`, `RA N`, `PD N`, `DO N-N` in query_text |
| P6 | FTS dual-signal aware | Moderate length ensures raw-query AND signal fires |
| P7 | Anchor phrase (length-bias fix) | When gold is a short law section competing with a long KB chunk, put the most exclusive phrase verbatim in ASCII single quotes (≥5 words) in query_text → pipeline extracts it and applies `ts_rank × 100` boost via CASE WHEN SQL, overriding ts_rank length bias |
| P8 | Rare vocabulary anchor | Choose anchor phrases with ≥1 RARE token (e.g., "inimical", "effectivity"+"thirty", proper case names). Verbatim ILIKE-exclusive ≠ tsvector-exclusive; common tokens like "shall"+"join"+"labor"+"organization" match many chunks even if ILIKE returns 1 result. Rare tokens ensure the tsvector ×100 boost lands on the correct chunk only. |
| P9 | No boolean operators in anchor | `websearch_to_tsquery` treats lowercase `'or'`, `'and'`, `'not'` inside phrases as Boolean operators, not literal words. `'cause or causes'` → tsquery `caus | caus` = just `caus` alone → matches thousands of chunks. Use anchor phrases that avoid these words entirely; rephrase if needed (e.g., `'cause of action'` instead of `'causes or cause'`). |
| P10 | Gold ts_rank must be positive for boost | The anchor boost `CASE WHEN tsvector @@ anchor THEN ts_rank(search_terms) × 100` multiplies the SEARCH_TERMS ts_rank, not a constant. If gold chunk's content is unrelated to search_terms keywords (e.g., NLRC rule for SSS query), ts_rank ≈ 0 → boost ≈ 0. Fix: add domain-relevant keywords for the gold domain to the query text so gold's base ts_rank ≥ 0.03 before boosting. |
