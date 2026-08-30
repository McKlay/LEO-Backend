# LEO Expert Evaluation Console

Blinded web console for two labor-law experts to independently rate the 300 answers
(100 queries × 3 pipeline configs) in `tests/benchmark/results/exports/expert_evaluation.csv`.

See [docs/eval-and-benchmarking/EVAL_CONSOLE_IMPLEMENTATION_PLAN.md](../../docs/eval-and-benchmarking/EVAL_CONSOLE_IMPLEMENTATION_PLAN.md)
for the full design.

## Setup

Run from `tools/eval_console/` using the repo's existing virtual environment.

```powershell
cd tools/eval_console
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set real values for:

- `REVIEWER_1_PASSWORD`
- `REVIEWER_2_PASSWORD`
- `ADMIN_PASSWORD`
- `SECRET_KEY` (any long random string)
- `SUPABASE_URL` (from Supabase dashboard → Project Settings → API)
- `SUPABASE_KEY` (service role key from Supabase dashboard → Project Settings → API)

The `ratings` table must already exist in Supabase — see [DEPLOYMENT.md](DEPLOYMENT.md#2-create-the-ratings-table-in-supabase) for the SQL.

## Run

From `tools/eval_console/`:

```powershell
python -m uvicorn main:app --reload --port 8000
```

Then open:

- `http://127.0.0.1:8000/` — reviewer login
- `http://127.0.0.1:8000/review` — evaluation card UI (after login)
- `http://127.0.0.1:8000/progress` — admin progress dashboard + CSV export (admin password)
- `http://127.0.0.1:8000/docs` — Swagger API docs

## Notes

- Must be run with `tools/eval_console/` as the working directory — `main.py` resolves
  the source CSV and frontend files via relative/repo-root paths.
- Ratings are persisted in the Supabase Postgres `ratings` table via the REST API
  (no local disk storage); `init_db()` is a no-op since the table is created once via SQL.
- Config labels (Q/M/J) are never sent to the browser; each reviewer sees a
  deterministic per-query shuffle as "System A/B/C".
- `turn5_query` (Turn 6 follow-up context) is not in `expert_evaluation.csv` and is
  loaded directly from `tests/benchmark/data/benchmark-queries.json` at startup.
- Admin CSV export (`/api/export/csv`) merges both reviewers' ratings with the
  original CSV and computes Cohen's kappa per config; requires `ADMIN_PASSWORD`.
