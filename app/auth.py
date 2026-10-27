import re
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db
from .models import User

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def _safe_next(target):
    # Only follow relative redirects so ?next= can't send people off-site.
    if target and not urlparse(target).netloc and target.startswith("/"):
        return target
    return url_for("items.index")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("items.index"))

    form = {"username": "", "display_name": ""}
    if request.method == "POST":
        form["username"] = request.form.get("username", "").strip()
        form["display_name"] = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not USERNAME_RE.match(form["username"]):
            errors.append("Username must be 3–32 letters, numbers or underscores.")
        elif User.query.filter(db.func.lower(User.username) == form["username"].lower()).first():
            errors.append("That username is taken.")
        if not form["display_name"]:
            errors.append("Please enter your name.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords don't match.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(username=form["username"], display_name=form["display_name"][:80])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash(f"Welcome, {user.display_name}!", "success")
            return redirect(url_for("items.index"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("items.index"))

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            flash(f"Signed in as {user.username}.", "success")
            return redirect(_safe_next(request.args.get("next")))
        flash("Wrong username or password.", "error")

    return render_template("auth/login.html", username=username)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You've been signed out.", "info")
    return redirect(url_for("items.index"))
