from datetime import date, datetime
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import db
from .auth import _safe_next
from .models import Item, User

bp = Blueprint("items", __name__)


def _filtered_query(base, q, unclaimed):
    if q:
        like = f"%{q}%"
        base = base.filter(
            db.or_(
                Item.title.ilike(like),
                Item.description.ilike(like),
                Item.location.ilike(like),
            )
        )
    if unclaimed:
        base = base.filter(Item.is_returned.is_(False))
    return base.order_by(Item.found_on.desc(), Item.created_at.desc())


def _list_args():
    q = request.args.get("q", "").strip()[:100]
    unclaimed = request.args.get("unclaimed") == "1"
    page = request.args.get("page", 1, type=int)
    return q, unclaimed, page


@bp.route("/")
def index():
    q, unclaimed, page = _list_args()
    query = _filtered_query(Item.query, q, unclaimed)
    pagination = query.paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
    )
    stats = {
        "total": Item.query.count(),
        "unclaimed": Item.query.filter_by(is_returned=False).count(),
    }
    return render_template(
        "items/index.html", pagination=pagination, q=q, unclaimed=unclaimed, stats=stats
    )


@bp.route("/items/<int:item_id>")
def detail(item_id):
    item = db.get_or_404(Item, item_id)
    return render_template("items/detail.html", item=item)


def _validate_item_form(form):
    errors = []
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "location": form.get("location", "").strip(),
        "found_on": form.get("found_on", "").strip(),
        "photo_url": form.get("photo_url", "").strip(),
    }
    if not data["title"]:
        errors.append("What did you find? Give the item a short title.")
    elif len(data["title"]) > 120:
        errors.append("Title must be 120 characters or fewer.")
    if not data["location"]:
        errors.append("Where did you find it?")
    elif len(data["location"]) > 120:
        errors.append("Location must be 120 characters or fewer.")
    if len(data["description"]) > 2000:
        errors.append("Description must be 2000 characters or fewer.")

    parsed_date = None
    try:
        parsed_date = datetime.strptime(data["found_on"], "%Y-%m-%d").date()
        if parsed_date > date.today():
            errors.append("The found date can't be in the future.")
    except ValueError:
        errors.append("When did you find it? Pick a date.")

    if data["photo_url"]:
        parsed = urlparse(data["photo_url"])
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors.append("Photo URL must start with http:// or https://.")
        elif len(data["photo_url"]) > 500:
            errors.append("Photo URL is too long.")

    return data, parsed_date, errors


@bp.route("/items/new", methods=["GET", "POST"])
@login_required
def new():
    data = {"found_on": date.today().isoformat()}
    if request.method == "POST":
        data, found_on, errors = _validate_item_form(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            item = Item(
                title=data["title"],
                description=data["description"],
                location=data["location"],
                found_on=found_on,
                photo_url=data["photo_url"] or None,
                owner=current_user,
            )
            db.session.add(item)
            db.session.commit()
            flash("Thanks! Your found item is posted.", "success")
            return redirect(url_for("items.detail", item_id=item.id))
    return render_template("items/form.html", data=data, today=date.today().isoformat())


def _owned_item_or_403(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    return item


@bp.route("/items/<int:item_id>/returned", methods=["POST"])
@login_required
def toggle_returned(item_id):
    item = _owned_item_or_403(item_id)
    item.mark_returned(not item.is_returned)
    db.session.commit()
    if item.is_returned:
        flash(f"Marked “{item.title}” as returned. Nice work!", "success")
    else:
        flash(f"“{item.title}” is back to unclaimed.", "info")
    nxt = request.form.get("next")
    return redirect(_safe_next(nxt) if nxt else url_for("items.detail", item_id=item.id))


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    item = _owned_item_or_403(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Post deleted.", "info")
    return redirect(url_for("items.user_page", username=current_user.username))


@bp.route("/users/<username>")
def user_page(username):
    user = User.query.filter(db.func.lower(User.username) == username.lower()).first_or_404()
    q, unclaimed, page = _list_args()
    query = _filtered_query(user.items, q, unclaimed)
    pagination = query.paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
    )
    stats = {
        "total": user.items.count(),
        "returned": user.items.filter_by(is_returned=True).count(),
    }
    return render_template(
        "users/show.html", user=user, pagination=pagination, q=q, unclaimed=unclaimed, stats=stats
    )


@bp.app_errorhandler(403)
@bp.app_errorhandler(404)
@bp.app_errorhandler(400)
@bp.app_errorhandler(405)
def http_error(err):
    return render_template("error.html", error=err), err.code


@bp.app_errorhandler(500)
def server_error(err):
    # Don't leave a half-finished transaction behind for the next request.
    db.session.rollback()
    return render_template("error.html", error=err), 500
