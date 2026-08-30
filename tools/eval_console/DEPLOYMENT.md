# Eval Console — Render Deployment Guide

## Prerequisites

- A [Render](https://render.com) account (free)
- The LEO-Backend repo pushed to GitHub

---

## 1. Create the Render Service

### Option A — Blueprint (recommended)

Render will read `render.yaml` automatically:

1. Go to [dashboard.render.com/new/blueprint](https://dashboard.render.com/new/blueprint)
2. Connect your GitHub repo and select the `LEO-Backend` repository
3. Render detects `tools/eval_console/render.yaml` and pre-fills the service config
4. Click **Apply**

### Option B — Manual

1. Go to [dashboard.render.com/new/web](https://dashboard.render.com/new/web)
2. Connect your GitHub repo
3. Set **Root Directory** to `tools/eval_console`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. **Plan**: Free

---

## 2. Create the Ratings Table in Supabase

Run this once in your Supabase project → **SQL Editor** → **New query**:

```sql
CREATE TABLE IF NOT EXISTS ratings (
    id                      SERIAL PRIMARY KEY,
    eval_id                 TEXT NOT NULL,
    reviewer_id             TEXT NOT NULL,
    legal_accuracy          INTEGER,
    hallucination           TEXT,
    citation_notes          TEXT,
    clarification_score     INTEGER,
    notes                   TEXT,
    turn6_legal_accuracy    INTEGER,
    turn6_hallucination     TEXT,
    turn6_citation_notes    TEXT,
    turn6_notes             TEXT,
    flagged                 INTEGER DEFAULT 0,
    saved_at                TEXT,
    UNIQUE(eval_id, reviewer_id)
);
```

> This only needs to be done once. The app uses your existing Supabase project with the service role key — no disk, no extra cost.

---

## 3. Set Environment Variables

In the Render service → **Environment** tab, add:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `https://qoombyuhqwuozjnreouz.supabase.co` |
| `SUPABASE_KEY` | *(service role key from Supabase → Project Settings → API → `service_role`)* |
| `REVIEWER_1_PASSWORD` | *(strong password for Reviewer 1)* |
| `REVIEWER_2_PASSWORD` | *(strong password for Reviewer 2)* |
| `ADMIN_PASSWORD` | *(strong password for admin dashboard)* |
| `SECRET_KEY` | *(any long random string, e.g. 64 hex chars)* |

> Never commit `.env` — it is git-ignored. Use `.env.example` as reference only.
>
> Variables marked `sync: false` in `render.yaml` must be set manually here — Render will not pull them from the file.

---

## 4. Deploy

Render deploys automatically on every push to the connected branch. To trigger manually:

**Render dashboard** → **Manual Deploy** → **Deploy latest commit**

The build installs `requirements.txt` and starts:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 5. Verify

After deploy, open the Render-provided URL (`https://<service-name>.onrender.com`):

| Path | Purpose |
|---|---|
| `/` | Reviewer login |
| `/review` | Evaluation card UI (after login) |
| `/progress` | Admin dashboard + CSV export (requires `ADMIN_PASSWORD`) |
| `/docs` | Swagger API docs |

Check that the query count on login matches 100 queries.

> **Note**: Free-tier Render services spin down after 15 minutes of inactivity. The first request after idle may take ~30 seconds to cold-start. This does not affect the persistent disk or any saved ratings.

---

## 6. Source Data

The two read-only files the app loads at startup are committed to the repo:

```
tests/benchmark/results/exports/expert_evaluation.csv
tests/benchmark/results/exports/expert_blinding_mapping.json
```

These paths are resolved relative to the repo root via `loader.py`. No manual upload is needed.

---

## 7. Ratings Backup

All reviewer ratings are stored in the `ratings` table in your Supabase project.

To back up, use the Supabase dashboard → **Table Editor** → select `ratings` → **Export as CSV**.

The final export (with Cohen's κ) is also available via the API:

```
GET /api/export/csv          # requires X-Admin-Password header
```

This merges both reviewers' ratings with the original CSV columns (with Cohen's κ).
