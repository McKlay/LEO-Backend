# Expert Evaluation Console — Implementation Plan

**Status:** Decisions locked — ready for implementation   
**Purpose:** Web-based tool for two labor-law experts to independently rate 300 blinded answers from the LEO benchmark (100 queries × 3 pipeline configurations)   
**Source data:** `tests/benchmark/results/exports/expert_evaluation.csv`

---

## 1. Context and Constraints from the Benchmark Spec

The following requirements are non-negotiable — they come directly from the thesis methodology (`Evaluation and Benchmarking v2.md §5.4`):

| Constraint | Detail |
|---|---|
| **Total ratings** | 3 configs × 100 queries × 2 experts = **600 individual answer ratings** |
| **+ Turn 6 ratings** | 85 of the 300 rows have a follow-up answer in `system_answer_turn6` → each also needs a rating block |
| **Blinding** | Experts must not know which config (LLM-only / Stage2-only / Full Pipeline) produced an answer. Labels Q/M/J in the CSV map to System A/B/C via `expert_blinding_mapping.json` — this mapping must not leak to reviewers |
| **Independent rating** | The two reviewers rate separately; neither sees the other's scores until both are done |
| **Cohen's κ** | The methodology requires inter-rater reliability reporting — scores from both reviewers must be exportable in a format ready for κ computation |
| **4-point scale** | Legal accuracy: 1 = Incorrect, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct |
| **Hallucination** | Binary Yes/No per answer |
| **Citation fidelity** | Short text note per answer (e.g., "cites Art. 298 correctly") |
| **Clarification quality** | Only shown when `is_ambiguous = true` (90/300 rows) |
| **Multi-turn context** | `conversation_history` JSON must be rendered as a readable chat thread for 90 multi-turn rows |
| **Languages** | Answers in English, Filipino, and Cebuano — tool must display all three without garbling |

---

## 2. What the Expert Sees Per Query Card

Each of the 100 queries generates a single "evaluation card" that contains all 3 system answers and the ground truth side-by-side. The card layout (top to bottom):

```
┌─────────────────────────────────────────────────────────────────┐
│ QUERY CARD — Q036          [fil]  [separation_pay]  [1 of 100]  │
├─────────────────────────────────────────────────────────────────┤
│ [Ambiguous] badge (if is_ambiguous = true)                      │
│ [Multi-turn] badge (if query_type = multi_turn)                 │
├─────────────────────────────────────────────────────────────────┤
│ 📋 CONVERSATION HISTORY (collapsible, only for multi-turn)      │
│   👤 User: ... | 🤖 Assistant: ... | 👤 User: ...              │
├─────────────────────────────────────────────────────────────────┤
│ ❓ QUERY TEXT (rendered, not raw)                               │
├─────────────────────────────────────────────────────────────────┤
│ 📚 REFERENCE PANEL (always visible, right column or accordion)  │
│   Reference Answer | Gold Articles: [Art. 298] [DO 147-15]      │
├─────────────────────────────────────────────────────────────────┤
│ SYSTEM ANSWER — System X   │ SYSTEM ANSWER — System Y   │ ...   │
│ [rendered markdown]        │ [rendered markdown]        │       │
│ ─────────────────────────  │ ─────────────────────────  │       │
│ Legal Accuracy: ○1 ○2 ○3 ○4│ Legal Accuracy: ○1 ○2 ○3 ○4│     │
│ Hallucination: ○Yes ○No    │ Hallucination: ○Yes ○No    │       │
│ Citation notes: [textarea] │ Citation notes: [textarea] │       │
│ [if ambiguous]             │ [if ambiguous]             │       │
│ Clarification Q: ○1 ○2 ○3 ○4 (or N/A)                          │
│ Notes: [textarea]          │ Notes: [textarea]          │       │
├─────────────────────────────────────────────────────────────────┤
│ TURN 6 FOLLOW-UP BLOCK (only when system_answer_turn6 exists)   │
│   turn6_reference_answer shown                                  │
│   System X Turn6 answer | System Y Turn6 answer | System Z      │
│   [same rating fields as above]                                 │
├─────────────────────────────────────────────────────────────────┤
│ [← Prev]           [Save & Continue →]           [Flag card]    │
└─────────────────────────────────────────────────────────────────┘
```

> **Key UX rule:** The reference panel is always visible but visually distinct (shaded background). Ratings auto-save on every field blur — no data is lost if the browser is closed.

---

## 3. Technical Architecture

### 3.1 Components

```
tools/eval_console/              ← lives inside LEO-Backend repo
├── main.py                  # FastAPI app entry point
├── db.py                    # SQLite setup (ratings table)
├── models.py                # Pydantic schemas
├── routes/
│   ├── queries.py           # GET /queries, GET /queries/{id}
│   ├── ratings.py           # POST /ratings, GET /ratings/{eval_id}
│   └── export.py            # GET /export/csv (merged output + κ)
├── data/
│   ├── loader.py            # CSV → in-memory query store at startup
│   └── blinding.py          # maps Q/M/J → System A/B/C (server-side only)
├── frontend/
│   ├── index.html           # Login / reviewer selection
│   ├── review.html          # Main evaluation interface
│   ├── progress.html        # Admin progress dashboard (password-gated)
│   └── js/
│       ├── api.js           # fetch wrappers
│       ├── card.js          # Query card renderer (markdown, chat bubbles)
│       └── state.js         # Local autosave (localStorage + server sync)
├── .env.example             # Template: REVIEWER_1_PASSWORD, REVIEWER_2_PASSWORD, ADMIN_PASSWORD, DATABASE_PATH
├── requirements.txt         # fastapi, uvicorn, scikit-learn, python-dotenv
├── railway.json             # Railway deploy config (root dir, start command, volume mount)
└── Procfile                 # web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 3.2 Storage

The CSV is **read-only source data**. Ratings are stored separately in a SQLite database:

```sql
CREATE TABLE ratings (
    id          INTEGER PRIMARY KEY,
    eval_id     TEXT NOT NULL,          -- e.g. "E0107"
    reviewer_id TEXT NOT NULL,          -- "reviewer_1" | "reviewer_2"
    -- Main answer rating
    legal_accuracy      INTEGER,        -- 1-4
    hallucination       TEXT,           -- "yes" | "no"
    citation_notes      TEXT,
    clarification_score INTEGER,        -- 1-4 | NULL (if not ambiguous)
    notes               TEXT,
    -- Turn 6 rating (nullable if no turn6)
    turn6_legal_accuracy    INTEGER,
    turn6_hallucination     TEXT,
    turn6_citation_notes    TEXT,
    turn6_notes             TEXT,
    -- Metadata
    flagged             INTEGER DEFAULT 0,
    saved_at            TEXT,
    UNIQUE(eval_id, reviewer_id)
);
```

### 3.3 Blinding

The `config_label` (Q/M/J) is **never sent to the browser**. The server translates it to a randomized-per-session display label (System A / System B / System C) and consistently applies the same mapping within a reviewer's session. The actual mapping is stored server-side only, unlocked via the `/export` endpoint after both reviewers have finished.

---

## 4. Two-Reviewer Workflow

```
Reviewer 1 ──→ [localhost or hosted URL + ?reviewer=1]
                     │
                     ▼
              ┌──────────────┐      Ratings stored in SQLite
              │ Eval Console │  →   (eval_id, reviewer_id, scores...)
              └──────────────┘
Reviewer 2 ──→ [same URL + ?reviewer=2]
                     │
                     ▼
              [independent rating session, no visibility into Reviewer 1's scores]

After both complete:
Admin ──→ GET /export/csv
              │
              ▼
    merged_ratings.csv
    (original CSV columns + reviewer_1_* + reviewer_2_* + cohen_kappa_* columns)
```

**Key isolation rules:**
- Neither reviewer can see the other's scores in the UI at any time
- A "progress dashboard" (admin-only, password-protected) shows per-reviewer completion %, but not score values
- The `/export` endpoint that reveals variant labels is gated behind admin password + requires both reviewers to have reached 100% on core ratings

---

## 5. Progress and Navigation

| Feature | Detail |
|---|---|
| Progress bar | "XX / 100 queries rated" per reviewer, shown in header |
| Filter panel | Filter by topic (20 options), language, ambiguous/multi-turn, flagged, unrated |
| Jump to card | Direct input to navigate by query ID |
| Flag | Mark a card for second opinion or discussion |
| Resume | On next login, auto-navigate to first unrated card |
| Relative ranking (optional) | See Decision 4 below |

---

## 6. Export Format

`GET /export/csv` returns a file that extends the original CSV schema:

```
eval_id, query_id, query_text, language, ...(all original columns)...,
reviewer_1_legal_accuracy, reviewer_1_hallucination, reviewer_1_citation_notes,
reviewer_1_clarification_score, reviewer_1_notes,
reviewer_1_turn6_legal_accuracy, reviewer_1_turn6_hallucination, reviewer_1_turn6_notes,
reviewer_2_legal_accuracy, reviewer_2_hallucination, reviewer_2_citation_notes,
reviewer_2_clarification_score, reviewer_2_notes,
reviewer_2_turn6_legal_accuracy, reviewer_2_turn6_hallucination, reviewer_2_turn6_notes,
mean_legal_accuracy, cohens_kappa_legal_accuracy
```

The `cohens_kappa_legal_accuracy` column is computed server-side per config group (A/B/C) using `scikit-learn`'s `cohen_kappa_score`.

---

## 7. Implementation Phases

| Phase | Tasks | Output |
|---|---|---|
| **P0 — Setup** (0.5 day) | Initialize repo/folder, install deps (FastAPI, sqlite3, uvicorn), wire CSV loader | Server starts, serves query count |
| **P1 — Data layer** (0.5 day) | CSV loader → in-memory query store, blinding module, Supabase ratings schema (via REST API) | GET /queries returns blinded query list |
| **P2 — Backend API** (1 day) | All routes: queries, ratings (save/update), progress, export | Full API with Swagger docs |
| **P3 — Card UI** (1.5 days) | HTML/CSS for card layout, markdown renderer (marked.js), chat bubble renderer, rating widgets | Functional single card |
| **P4 — Navigation & state** (0.5 day) | Card navigation, autosave, resume-on-login, filter sidebar | Full review session flow |
| **P5 — Admin panel** (0.5 day) | Progress dashboard, export endpoint with κ computation | Admin can track + export |
| **P6 — Testing & hardening** (0.5 day) | Load all 300 rows, verify blinding, test export CSV against expected schema | Ready for reviewers |

**Estimated total:** ~5 development days

---

## 8. Decisions — Locked

| # | Decision | Choice |
|---|---|---|
| 1 | Repository placement | **Option B** — `tools/eval_console/` inside LEO-Backend |
| 2 | Tech stack | ~~FastAPI + SQLite~~ **Superseded:** FastAPI + Supabase Postgres (REST API) + Vanilla HTML/CSS/JS |
| 3 | Hosting | ~~Railway~~ **Superseded:** Cloud deploy on **Render** |
| 4 | Answer display | **Option A** — All 3 answers side-by-side |
| 5 | Session identity | **Option B** — Simple per-reviewer password in `.env` |

> **Note:** Decisions 2 and 3 were revised after initial implementation. The console
> now persists ratings in Supabase Postgres (already used by the main LEO backend)
> instead of a local SQLite file, and deploys to Render instead of Railway. See
> [DEPLOYMENT.md](../../tools/eval_console/DEPLOYMENT.md) for the current setup. The
> original SQLite/Railway rationale below is kept for historical context only.

---

### Decision 1 — Repository placement ✅

**Chosen: Option B — `tools/eval_console/` inside the existing LEO-Backend repo.**

The tool lives at `tools/eval_console/` relative to the repo root. It shares the existing Python virtual environment and can reference the source CSV and blinding mapping by relative path without any copying.

---

### Decision 2 — Tech stack ✅

**Chosen: Option A — FastAPI + SQLite backend, Vanilla HTML/CSS/JS frontend.**

**Platform for SQLite on cloud (Railway):** SQLite is a file-based database stored at a path like `data/ratings.db`. On Railway, a **persistent volume** is attached to the service and mounted to that path — the file survives redeploys and container restarts. The deployment flow is:

1. Railway creates a persistent volume (e.g. 1 GB, free tier).
2. `ratings.db` is written to the mounted volume path (e.g. `/data/ratings.db`).
3. On redeploy, the new container re-mounts the same volume — all ratings are preserved.
4. `DATABASE_PATH` is set as a Railway environment variable pointing to `/data/ratings.db`.

> **Why not Render or Fly.io?** Render's free tier uses ephemeral storage — the SQLite file is wiped on every redeploy, which would destroy all reviewer ratings. Fly.io supports persistent volumes but has a more complex CLI setup. Railway is the right choice here: persistent volumes work on the free tier, the Python/FastAPI buildpack is zero-config, and deployment takes ~15 minutes.

---

### Decision 3 — Hosting ✅

**Chosen: Option C — Railway cloud deploy.**

Deployment setup:
- Push `tools/eval_console/` to the LEO-Backend GitHub repo (already decided in Decision 1).
- Create a Railway project pointing at the repo, with root directory set to `tools/eval_console/`.
- Attach a persistent volume mounted at `/data/` for the SQLite database.
- Set environment variables: `REVIEWER_1_PASSWORD`, `REVIEWER_2_PASSWORD`, `ADMIN_PASSWORD`, `DATABASE_PATH=/data/ratings.db`.
- Both reviewers access the same Railway URL — no local Python setup required.

---

### Decision 4 — Answer display ✅

**Chosen: Option A — All 3 system answers shown side-by-side.**

The three blinded answers (System X / System Y / System Z) appear as three columns under the query and reference panel. Each column has its own independent rating widgets. Column order is fixed per query across both reviewers' sessions (deterministic shuffle seeded by `query_id`) so that if disagreements arise, the same layout was presented to both.

---

### Decision 5 — Session identity ✅

**Chosen: Option B — Simple per-reviewer password stored in `.env`.**

The login screen prompts for a reviewer name selection (Reviewer 1 / Reviewer 2) and the corresponding password. Passwords are stored as `REVIEWER_1_PASSWORD` and `REVIEWER_2_PASSWORD` in `.env` (never committed to git — added to `.gitignore`). An `ADMIN_PASSWORD` variable gates the progress dashboard and export endpoint.

---

## 9. Out of Scope

The following are explicitly not part of this tool:

- Real-time collaboration or live score sharing between reviewers
- Automated scoring or LLM-assisted pre-scoring of fields
- Integration with the production LEO API or LEO Frontend
- Any UI for editing or re-running benchmark queries
- Permanent public hosting after thesis submission

---

## 10. Dependency on Existing Assets

| Asset | Repo-relative path | Path from `tools/eval_console/` | Role |
|---|---|---|---|
| Source CSV | `tests/benchmark/results/exports/expert_evaluation.csv` | `../../tests/benchmark/results/exports/expert_evaluation.csv` | Read-only data source |
| Blinding mapping | `tests/benchmark/results/exports/expert_blinding_mapping.json` | `../../tests/benchmark/results/exports/expert_blinding_mapping.json` | Config label → System A/B/C translation (server-side only) |
| Benchmark spec | `docs/eval-and-benchmarking/Evaluation and Benchmarking v2.md` | Reference only | Rating criteria and scale definitions |
| Ratings table | Supabase Postgres `ratings` table (see [DEPLOYMENT.md](../../tools/eval_console/DEPLOYMENT.md#2-create-the-ratings-table-in-supabase)) | Accessed via `SUPABASE_URL`/`SUPABASE_KEY` (REST API) | Reviewer scores — persisted in the cloud, never committed to git |

The tool reads the CSV and blinding mapping at startup and never modifies them. Ratings live in Supabase, not on local/container disk.
