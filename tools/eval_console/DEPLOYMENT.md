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

## 2. Attach a Persistent Disk

The SQLite ratings database must survive restarts and redeploys.

> **Cost**: $0.25/GB/month (1 GB = ~$0.25/month). The web service itself remains on the free plan.

If using the Blueprint, the disk is defined in `render.yaml` automatically. For manual setup:

1. In your Render service → **Disks** tab → **Add Disk**
2. **Name**: `ratings-data`
3. **Mount Path**: `/data`
4. **Size**: 1 GB

---

## 3. Set Environment Variables

In the Render service → **Environment** tab, add:

| Variable | Value |
|---|---|
| `REVIEWER_1_PASSWORD` | *(strong password for Reviewer 1)* |
| `REVIEWER_2_PASSWORD` | *(strong password for Reviewer 2)* |
| `ADMIN_PASSWORD` | *(strong password for admin dashboard)* |
| `DATABASE_PATH` | `/data/ratings.db` |
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

All reviewer ratings are stored in `/data/ratings.db` on the Render disk.

To back up, use the Render **Shell** tab in the dashboard:

```bash
sqlite3 /data/ratings.db .dump > /tmp/ratings_backup.sql
```

Then download via the Render dashboard file browser, or use the export API:

```
GET /api/export/csv          # requires ADMIN_PASSWORD
```

This merges both reviewers' ratings with the original CSV columns (with Cohen's κ).
