import re
from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import Item, User
from app.seed import DEMO_PASSWORD


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "CSRF_IN_TESTS": True,
        }
    )
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, username="maya_r", password=DEMO_PASSWORD):
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf(client)},
        follow_redirects=True,
    )


def text(resp):
    return " ".join(resp.get_data(as_text=True).split())


def test_seeded_homepage_lists_items(client):
    html = text(client.get("/"))
    assert html.count("<article") == 12
    assert "Page 1 of 3" in html
    assert "Unclaimed" in html


def test_search_and_unclaimed_filter(app, client):
    html = client.get("/?q=hydro").get_data(as_text=True)
    assert "Blue Hydro Flask" in html
    assert "Black North Face backpack" not in html

    with app.app_context():
        returned = Item.query.filter_by(is_returned=True).first()
        title = returned.title
    assert "1 result for" in text(client.get("/", query_string={"q": title}))
    assert "0 results for" in text(client.get("/", query_string={"q": title, "unclaimed": "1"}))


def test_post_requires_login(client):
    resp = client.get("/items/new")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_post_without_csrf_is_rejected(client):
    login(client)
    resp = client.post("/items/new", data={"title": "x", "location": "y", "found_on": "2026-01-01"})
    assert resp.status_code == 400


def test_create_mark_returned_and_user_page(app, client):
    login(client)
    token = csrf(client, "/items/new")
    resp = client.post(
        "/items/new",
        data={
            "title": "Purple umbrella",
            "location": "Benson Center",
            "found_on": date.today().isoformat(),
            "photo_url": "https://example.com/u.jpg",
            "description": "",
            "csrf_token": token,
        },
    )
    assert resp.status_code == 302
    item_url = resp.headers["Location"]
    item_id = int(item_url.rsplit("/", 1)[1])

    client.post(f"/items/{item_id}/returned", data={"csrf_token": token})
    with app.app_context():
        assert db.session.get(Item, item_id).is_returned

    page = client.get("/users/maya_r").get_data(as_text=True)
    assert "Purple umbrella" in page


def test_cannot_mark_someone_elses_item(app, client):
    with app.app_context():
        other = User.query.filter_by(username="jkim").one()
        item_id = other.items.first().id
    login(client)
    resp = client.post(f"/items/{item_id}/returned", data={"csrf_token": csrf(client, "/")})
    assert resp.status_code == 403


def test_rejects_javascript_photo_url_and_future_date(client):
    login(client)
    html = client.post(
        "/items/new",
        data={
            "title": "Thing",
            "location": "Somewhere",
            "found_on": (date.today() + timedelta(days=2)).isoformat(),
            "photo_url": "javascript:alert(1)",
            "csrf_token": csrf(client, "/items/new"),
        },
    ).get_data(as_text=True)
    assert "Photo URL must start with" in html
    assert "can&#39;t be in the future" in html


def test_friendly_error_pages(client):
    resp = client.get("/items/99999")
    assert resp.status_code == 404 and "Maybe it was lost too" in text(resp)
    resp = client.get("/users/nobody_here")
    assert resp.status_code == 404
    resp = client.get("/logout")
    assert resp.status_code == 405 and "can't be opened that way" in text(resp)


def test_bad_login_and_register_show_messages(client):
    html = text(login(client, password="wrong"))
    assert "Wrong username or password." in html
    html = text(
        client.post(
            "/register",
            data={
                "username": "maya_r",
                "display_name": "",
                "password": "short",
                "confirm": "different",
                "csrf_token": csrf(client, "/register"),
            },
        )
    )
    for msg in ["That username is taken.", "Please enter your name.",
                "at least 8 characters", "Passwords don&#39;t match."]:
        assert msg in html


def test_register_and_login(client):
    resp = client.post(
        "/register",
        data={
            "username": "new_student",
            "display_name": "New Student",
            "password": "supersecret",
            "confirm": "supersecret",
            "csrf_token": csrf(client, "/register"),
        },
        follow_redirects=True,
    )
    assert "Welcome, New Student" in resp.get_data(as_text=True)
