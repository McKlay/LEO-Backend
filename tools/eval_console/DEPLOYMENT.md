# Eval Console — Railway Deployment Guide

## Prerequisites

- A [Railway](https://railway.app) account
- The LEO-Backend repo pushed to GitHub (branch: `feat/expert-evaluation-console`)

---

## 1. Create the Railway Project

1. Go to [railway.app/new](https://railway.app/new) → **Deploy from GitHub repo**
2. Select `LEO-Backend` and the `feat/expert-evaluation-console` branch (or `main` after merge)
3. When prompted for **Root Directory**, set it to: `tools/eval_console`

Railway auto-detects the Python/Nixpacks buildpack and uses `railway.json` for the start command.

---

## 2. Attach a Persistent Volume

The SQLite ratings database must survive redeploys.

1. In your Railway service → **Volumes** tab → **Add Volume**
2. Mount path: `/data`
3. Size: 1 GB (free tier is sufficient)

---

## 3. Set Environment Variables

In the Railway service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `REVIEWER_1_PASSWORD` | *(strong password for Reviewer 1)* |
| `REVIEWER_2_PASSWORD` | *(strong password for Reviewer 2)* |
| `ADMIN_PASSWORD` | *(strong password for admin dashboard)* |
| `DATABASE_PATH` | `/data/ratings.db` |
| `SECRET_KEY` | *(any long random string, e.g. 64 hex chars)* |

> Never commit `.env` — it is git-ignored. Use `.env.example` as reference only.

---

## 4. Deploy

Railway deploys automatically on push. To trigger manually:

**Railway dashboard** → **Deploy** → **Deploy Now**

Or via CLI:
```bash
railway up
```

The build installs `requirements.txt` and starts:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 5. Verify

After deploy, open the Railway-provided URL:

| Path | Purpose |
|---|---|
| `/` | Reviewer login |
| `/review` | Evaluation card UI (after login) |
| `/progress` | Admin dashboard + CSV export (requires `ADMIN_PASSWORD`) |
| `/docs` | Swagger API docs |

Check that the query count on login matches 100 queries.

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

All reviewer ratings are stored in `/data/ratings.db` on the Railway volume.

To back up before any destructive operation:

```bash
railway run -- sqlite3 /data/ratings.db .dump > ratings_backup.sql
```

The final export (with Cohen's κ) is available at:

```
GET /api/export/csv          # requires ADMIN_PASSWORD
```

This merges both reviewers' ratings with the original CSV columns.
