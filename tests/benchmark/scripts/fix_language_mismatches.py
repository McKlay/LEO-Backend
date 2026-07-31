"""
Fix language mismatches in benchmark-queries.json.
All translations preserve verbatim English FTS anchors exactly.
"""
import json
import shutil
from pathlib import Path

BQ_PATH = Path("tests/benchmark/data/benchmark-queries.json")

# Back up original
backup = BQ_PATH.with_suffix(".bak.json")
shutil.copy2(BQ_PATH, backup)
print(f"Backup created: {backup}")

with open(BQ_PATH, encoding="utf-8") as f:
    bq = json.load(f)

FIXES = {
    # ── Lexical target: fil → ceb ─────────────────────────────────────────────
    "Q030": {
        # topic: thirteenth_month_pay | FTS anchor: 'at the time of the promulgation of the Decree on December 16, 1975'
        "query_text": (
            "Kung naghatag na ang usa ka employer og Christmas bonus nga katumbas sa 1/12 "
            "sa buwanang kita sa ilang mga empleyado, mahimo ba silang dili na kinahanglan "
            "mosunod sa ubang mga balaod alang sa taunang bonus? Kinahanglan ba kini nga "
            "makatubag sa pamantayan nga 'at the time of the promulgation of the Decree "
            "on December 16, 1975'?"
        ),
    },
    "Q053": {
        # topic: termination_due_process | FTS anchor: 'at least thirty days (30) before the effectivity'
        "query_text": (
            "Sa kahimtang sa SSS retirement pension, pila ang gikinahanglan nga monthly "
            "contributions aron mahimong eligible ang miyembro? Mahimo bang pilion ang "
            "lump-sum kaysa monthly benefit alang sa gamay pang kontribusyon? Sa "
            "termination sa empleyado, ang employer gi-obligar sa paghatag og abiso nga "
            "'at least thirty days (30) before the effectivity' sa pagpapaalis. Giunsa kini?"
        ),
    },
    "Q077": {
        # topic: osh_safety | FTS anchor: 'complete job safety instructions or orientation'
        "query_text": (
            "Sa OSH law, ang covered workplace nagkinahanglan og safety officer aron "
            "ma-oversee ang safety and health program ug regular nga susihon ang mga "
            "hazard. Pila ang gikinahanglan nga safety officer depende sa gidaghanon sa "
            "mga manggagawa? Ingon bahin sa mga katungdanan sa employer, kinahanglan "
            "usab nga ihatag ang 'complete job safety instructions or orientation' sa "
            "mga bag-ong empleyado?"
        ),
    },
    "Q082": {
        # topic: labor_relations_unions | FTS anchor: 'inimical to the legitimate interests of both labor and management'
        "query_text": (
            "Para sa SSS monthly pension, pila ang gikinahanglan nga monthly contributions "
            "sa miyembro aron mahimong eligible? Gawas sa pension, adunay dugang nga mga "
            "benepisyo usab ang SSS. Sa Labor Code, ang mga buhat nga 'inimical to the "
            "legitimate interests of both labor and management' gitawag nga unfair labor "
            "practices. Unsa ang mga pananglitan niini?"
        ),
    },
    # ── Dense target: fil → ceb ───────────────────────────────────────────────
    "Q033": {
        # topic: thirteenth_month_pay | no verbatim anchor needed (dense target)
        "query_text": (
            "Nagtrabaho ko sa payroll sa usa ka kumpanya. Nanginahanglan ko og tabang sa "
            "pagkalkula sa mandatory nga taunang benepisyo nga gihatag sa tanang rank-and-file "
            "nga empleyado sa pribadong sektor sa katapusan sa tuig. Ang husto nga kalkulasyon "
            "usa ka proporsyonal nga bahin sa basic nga suweldo base sa gidaghanon sa bulan "
            "nga nag-alagad ang empleyado — pananglitan, ang empleyado nga nagsugod sa tunga "
            "sa tuig makadawat lang sa katunga sa tibuuk nga kantidad. Aduna kami mga empleyado "
            "nga wala mupasok sa pipila ka adlaw nga walay bayad — maka-apekto ba kini sa "
            "pro-rating sa ilang benepisyo? Aduna bay mga employer nga adunay legal nga basehan "
            "aron dili magbayad niining benepisyo kung ang kumpanya adunay pagkalugi sa sulod "
            "sa tuig? Ug unsa ang silot sa mga employer nga wala nagbayad sa husto nga oras? "
            "Nagpangutana usab kami bahin sa mga kasambahay nga nagtrabaho sulod sa balay: "
            "aduna ba silay katungod sa pagdawat niining benepisyo, o aduna ba silang lain nga "
            "kategorya sa minimum nga suweldo ug espesyal nga mga benepisyo nga gitakda sa balaod?"
        ),
    },
    # ── Hybrid target: fil → ceb ──────────────────────────────────────────────
    "Q080": {
        # topic: osh_safety | no verbatim anchor needed (hybrid target)
        "query_text": (
            "Unsa ang mga katungdanan sa employer sa paghatag og hazard information sa mga "
            "manggagawa? Ug sa ilalim sa OSH program, unsang mga kumpanya ang kinahanglan "
            "mag-designate og safety officer, ug giunsa pagtino ang sapat nga gidaghanon niini?"
        ),
    },
    # ── Lexical target: fil → en ──────────────────────────────────────────────
    "Q071": {
        # topic: philhealth_pagibig | FTS anchor: 'income floor and income ceiling'
        "query_text": (
            "Pag-IBIG Fund provides housing loans to members with sufficient contributions. "
            "How many months of contributions are needed before a member becomes eligible? "
            "In addition, members may also avail of short-term loans from Pag-IBIG. As for "
            "PhilHealth, the premium is computed with an 'income floor and income ceiling' "
            "as the basis. How does this work?"
        ),
    },
    "Q087": {
        # topic: nlrc_procedure | FTS anchor: 'shall be signed under oath'
        "query_text": (
            "For an SSS retirement pension, what is the minimum number of monthly contributions "
            "required to become eligible? SSS provides both a regular pension and a lump-sum "
            "benefit. SSS sickness and maternity benefits also require sufficient contributions. "
            "On another matter, an NLRC complaint or petition 'shall be signed under oath' "
            "before it is filed. How does the filing process work?"
        ),
    },
    "Q100": {
        # topic: recruitment_overseas | FTS anchor: 'non-availability of a person in the Philippines who is competent, able and willing'
        "query_text": (
            "For an SSS retirement pension, how many monthly contributions are required to "
            "become eligible? SSS provides both a regular pension and a lump-sum benefit. "
            "SSS sickness and maternity benefits also require sufficient contributions. On a "
            "separate matter, the issuance of an Alien Employment Permit (AEP) requires a "
            "finding of 'non-availability of a person in the Philippines who is competent, "
            "able and willing' to perform the work. Can an AEP holder transfer to a "
            "different employer?"
        ),
    },
    # ── Hybrid target: fil → en (multi-turn — also update conversation_history) ──
    "Q049": {
        # topic: termination_due_process | ambiguous opener — keep vague
        "query_text": "I have a problem at work right now.",
        "_update_conv_history_0": "I have a problem at work right now.",
    },
}

# Apply fixes
updated = []
for q in bq["queries"]:
    qid = q["query_id"]
    if qid in FIXES:
        fix = FIXES[qid]
        old_text = q.get("query_text", "")
        q["query_text"] = fix["query_text"]
        print(f"\n[{qid}] Updated query_text")
        print(f"  OLD: {old_text[:80]!r}")
        print(f"  NEW: {fix['query_text'][:80]!r}")

        # For multi-turn queries, sync conversation_history[0].text if present
        if "_update_conv_history_0" in fix:
            ch = q.get("conversation_history", [])
            if ch and ch[0].get("role") == "user":
                old_ch = ch[0].get("text", ch[0].get("content", ""))
                key = "text" if "text" in ch[0] else "content"
                ch[0][key] = fix["_update_conv_history_0"]
                print(f"  Also updated conversation_history[0]['{key}']: {old_ch!r} → {fix['_update_conv_history_0']!r}")
        updated.append(qid)
    bq["queries"][bq["queries"].index(q)] = q

# Write back
with open(BQ_PATH, "w", encoding="utf-8") as f:
    json.dump(bq, f, ensure_ascii=False, indent=2)

print(f"\n\nDone. Updated {len(updated)} queries: {updated}")
print(f"Original preserved at: {backup}")

# Verify
with open(BQ_PATH, encoding="utf-8") as f:
    verify = json.load(f)
verify_map = {q["query_id"]: q for q in verify["queries"]}
print("\n=== Verification ===")
for qid in sorted(FIXES.keys()):
    q = verify_map[qid]
    print(f"  {qid} | lang={q['language']} | target={q['retrieval_target']}")
    print(f"       text[:100]: {q['query_text'][:100]!r}")
