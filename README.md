# Campus Lost & Found

A Flask + SQLAlchemy web app for posting items found on campus.

- **Home page** (`/`): anyone can browse found items, search them, and tick **Still unclaimed only**.
- **Item pages** (`/items/<id>`) and **user pages** (`/users/<username>`, listing that person's posts).
- **Register / sign in.** Once signed in, you can **post a found item** (what, where, when, photo URL) and **mark your own posts as returned**. Only the poster can change a post.
- **Saved in a database.** Everything is stored in SQLite (`instance/lostandfound.db`), so it's still there after a restart. On first run the app fills an empty database with fictitious users and items. Every demo account's password is `lostandfound`, e.g. `maya_r`.
- **Clear error messages.** Invalid forms show what to fix, a missing item or user shows a 404 page, and editing someone else's post shows a 403 page.

## Run it on a laptop

You need Python 3.10 or newer.

```bash
git clone <this repo> && cd lost-and-found
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app wsgi run --port 5050
```

Open http://127.0.0.1:5050. Stop the server with Ctrl+C. Your data stays in `instance/lostandfound.db`.

- Start over with fresh demo data: `flask --app wsgi seed --reset`
- Run the tests: `pip install pytest && python -m pytest`

## Putting it online (optional)

**Google Cloud Run:** `bash lost-and-found.sh --project <new-project-id> --billing <billing-account-id>`. The script creates the project, a Cloud SQL Postgres database (about $10/month) and the Cloud Run service, then prints the public URL. Add `--database-url <postgres-url>` to use a free Neon/Supabase database instead, or `--dry-run` to preview the commands. Run `bash lost-and-found.sh --help` for all options.

**Render:** `render.yaml` deploys the app to [Render](https://render.com) with a free Postgres database: **New → Blueprint →** pick this repo. On other hosts, use the `Procfile` and set the `DATABASE_URL` and `SECRET_KEY` environment variables. Set `SHOW_DEMO_HINT=0` to hide the demo login hint.
