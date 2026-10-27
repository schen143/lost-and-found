# Campus Lost & Found

A Flask web app for posting items found on campus.

- **Anyone** can browse found items, search them (title, description, location), and filter to **still unclaimed**.
- **Signed-in users** can post an item (what, where, when, optional photo URL) and mark their own posts as **returned** (or undo that, or delete the post).
- **Every user has a public page** at `/users/<username>` listing their posts.
- Data lives in a SQL database: SQLite locally, Postgres in production.
- On first start against an empty database, the app loads **8 fictitious users and 36 items**, so it never looks empty.

Every demo account uses the password `lostandfound`. Examples: `maya_r`, `jkim`, `priya_s`, `devon_t`.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app wsgi run --debug
```

Open http://127.0.0.1:5000. The SQLite file is created at `instance/lostandfound.db`.

Wipe and reseed the database:

```bash
.venv/bin/flask --app wsgi seed --reset
```

Run the tests:

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

## Put it online (Render, free tier)

The repo includes a `render.yaml` blueprint. It creates a Postgres database and a web service connected to it.

1. Push this repo to GitHub.
2. On https://render.com, choose **New → Blueprint** and pick the repo.
3. Click **Apply**. Render generates `SECRET_KEY`, sets `DATABASE_URL`, installs dependencies, and starts gunicorn.
4. When the deploy finishes, your public URL is `https://campus-lost-and-found-XXXX.onrender.com`.

The demo data is seeded automatically on the first boot.

Other hosts (Railway, Fly.io, Heroku) work the same way. The `Procfile` holds the start command. Point `DATABASE_URL` at a Postgres database and set `SECRET_KEY`.

### Configuration

| Variable         | Default                    | Purpose                                                         |
| ---------------- | -------------------------- | --------------------------------------------------------------- |
| `DATABASE_URL`   | `sqlite:///lostandfound.db` | Any SQLAlchemy URL. `postgres://` URLs are handled.              |
| `SECRET_KEY`     | dev-only value             | **Set this in production.** It signs the session cookies.        |
| `AUTO_SEED`      | `1`                        | Load demo data when the database is empty.                      |
| `SHOW_DEMO_HINT` | `1`                        | Show the demo login on the sign-in page. Set it to `0` for real use. |

## Project layout

```
app/
  __init__.py   app factory, DB setup, CSRF check
  models.py     User, Item
  auth.py       register / login / logout
  items.py      browse + search, item detail, post, mark returned, delete, user pages
  seed.py       fictitious data + `flask seed` command
  templates/    Jinja templates
  static/       stylesheet (light and dark mode)
tests/          pytest suite
wsgi.py         entry point for gunicorn / flask
```

## Security notes

- Passwords are hashed with Werkzeug (scrypt).
- Every POST form carries a per-session CSRF token.
- Only a post's author can mark it returned or delete it. Anyone else gets a 403.
- Photo URLs must be `http(s)`. All user text is escaped by Jinja.
- Redirect targets (`?next=`) must be relative paths on the same site.
