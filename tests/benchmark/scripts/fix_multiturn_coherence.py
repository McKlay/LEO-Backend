"""
Fix incoherent turn3 responses for 5 multi-turn benchmark queries.

For each query, turn3 (conversation_history[2]) must:
  1. Directly answer the turn2 clarification questions
  2. Preserve the retrieval signals (FTS anchors, dense keywords) described in query notes
  3. NOT introduce contradictory or off-topic pivots that ignore the clarification

Fixed queries: Q015, Q021, Q043, Q054, Q067
"""

import json
import shutil
from pathlib import Path

DATA_FILE = Path("tests/benchmark/data/benchmark-queries.json")
BACKUP_FILE = Path("tests/benchmark/data/benchmark-queries.coherence.bak.json")

# New turn3 texts — each one first answers the turn2 clarification, then preserves retrieval signals.
# Key constraints preserved:
#   Q015: SEnA anchor 'Within the 30 day mandatory conciliation mediation period' (L_R1 spoiler control)
#         + overtime/night shift keyword density for dense/lexical gold signal
#   Q021: regular holiday + daily-paid + rest day + SEnA anchor
#         (keyword matches enabling 260% rate semantic reasoning — per notes)
#   Q043: Labor Code minimum retirement + pribadong sektor + kasambahay
#         (dense → chunk_13 via age/years/private-sector; RA-10361 FTS via kasambahay)
#   Q054: regular employee + reduction-of-workforce (no "retrenchment" keyword to avoid Art.298 symbolic)
#         + separation pay + 13th month comparison (13th month → chunk_11 lexical spoiler, dense stays chunk_12)
#   Q067: lead with "unemployment insurance" to answer clarification + employer delinquency context
#         + Section 14-B; NO "RA 11199" citation (prevent ra-11199-10 symbolic per notes)

FIXES = {
    "Q015": (
        "I'm based in Metro Manila and I am a rank-and-file employee. "
        "I worked several overtime and night shifts beyond the regular eight-hour work day "
        "that were never properly compensated by my employer. "
        "How is extra pay computed for those additional hours, and what rate applies to night work? "
        "'Within the 30 day mandatory conciliation mediation period' "
        "can I file an overtime pay claim with DOLE?"
    ),
    "Q021": (
        "It was a regular holiday, and I am a daily-paid employee. "
        "I worked that day even though it fell on my rest day — "
        "am I entitled to premium pay on top of the regular holiday rate "
        "for working on a rest day coinciding with a regular holiday? "
        "'Within the 30 day mandatory conciliation mediation period' "
        "can I also file for unpaid wages?"
    ),
    "Q043": (
        "Nagtatanong ako tungkol sa minimum na hinihingi ng Labor Code — "
        "partikular ang sapilitang at opsyonal na pagreretiro sa pribadong sektor. "
        "Nais ko malaman kung ano ang pinakamababang edad at bilang ng taon ng serbisyo "
        "para maging karapat-dapat sa retirement pay. "
        "Interesado rin kami kung ang mga katulong sa bahay, tulad ng mga kasambahay, "
        "ay may katulad na pormal na probisyon sa batas para sa parehong uri ng benepisyo "
        "pagkatapos ng ilang taon ng serbisyo sa isang tahanan."
    ),
    "Q054": (
        "Regular po akong empleyado at sinabi ng employer na sila ay magbabawas ng bilang ng "
        "manggagawa dahil sa pagkalugi ng kumpanya. "
        "Kailangan naming malaman kung pila ang separation pay na dapat kong matanggap at "
        "kung paano ang tamang proseso para matanggap ito. "
        "Gusto ring malaman kung may papel o notipikasyon na kailangang isumite ng employer "
        "para ma-proseso ang bayad, at kung may deadline na panahon para dito. "
        "Lahi ba ang separation pay sa 13th month pay na dating natanggap ko?"
    ),
    "Q067": (
        "I am asking about unemployment insurance — I was recently separated involuntarily from my job. "
        "My employer has been delinquent in remitting my monthly SSS contributions and did not maintain "
        "proper employment records for over a year. "
        "What are the penalties for employers who commit non-remittance and contribution delinquency, "
        "and can I still claim unemployment insurance under Section 14-B despite my employer's delinquency?"
    ),
}

def main():
    # Backup
    shutil.copy2(DATA_FILE, BACKUP_FILE)
    print(f"Backup created: {BACKUP_FILE}\n")

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    qmap = {q["query_id"]: q for q in data["queries"]}
    updated = []

    for qid, new_text in FIXES.items():
        q = qmap[qid]
        ch = q.get("conversation_history", [])
        if len(ch) < 3:
            print(f"[{qid}] ERROR: conversation_history has only {len(ch)} turns, expected >=3")
            continue
        turn3 = ch[2]
        if turn3.get("role") != "user":
            print(f"[{qid}] WARNING: Turn3 role is '{turn3.get('role')}', expected 'user'")
        old_text = turn3.get("text", "")
        turn3["text"] = new_text
        updated.append(qid)
        print(f"[{qid}] Updated conversation_history[2]['text']")
        print(f"  OLD: {repr(old_text[:100])}")
        print(f"  NEW: {repr(new_text[:100])}")
        print()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Done. Updated {len(updated)} queries: {updated}")
    print(f"Original preservation: {BACKUP_FILE}")

    # Verify
    print("\n=== Verification ===")
    with open(DATA_FILE, encoding="utf-8") as f:
        data2 = json.load(f)
    qmap2 = {q["query_id"]: q for q in data2["queries"]}
    for qid in FIXES:
        q = qmap2[qid]
        t3 = q["conversation_history"][2]["text"]
        t2 = q["conversation_history"][1]["text"]
        print(f"  {qid} | lang={q['language']} | target={q['retrieval_target']}")
        print(f"    turn2 (clarification): {t2[:100]}")
        print(f"    turn3 (user response): {t3[:120]}")
        print()


if __name__ == "__main__":
    main()
