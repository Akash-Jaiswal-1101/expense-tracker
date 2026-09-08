import sqlite3
from datetime import date, timedelta, datetime
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


def _parse_date(value):
    """Return value if it's a valid YYYY-MM-DD string, else None."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not all([name, email, password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("Email already registered.", "error")
            return render_template("register.html")
        flash("Account created! Please sign in.", "success")
        return redirect(url_for("login"))
    abort(405)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("All fields are required.", "error")
            return render_template("login.html")
        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))
    abort(405)


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user_id = session["user_id"]

    date_from = _parse_date(request.args.get("date_from"))
    date_to   = _parse_date(request.args.get("date_to"))

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.", "error")
        date_from = date_to = None

    today = date.today()
    first_of_month = today.replace(day=1).isoformat()
    last_3m = (today - timedelta(days=90)).isoformat()
    last_6m = (today - timedelta(days=180)).isoformat()
    today_str = today.isoformat()

    presets = {
        "today": today_str,
        "this_month": first_of_month,
        "last_3m": last_3m,
        "last_6m": last_6m,
    }

    user         = get_user_by_id(user_id)
    stats        = get_summary_stats(user_id, date_from, date_to)
    transactions = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(user_id, date_from, date_to)
    return render_template("profile.html",
                           user=user,
                           stats=stats,
                           transactions=transactions,
                           categories=categories,
                           date_from=date_from,
                           date_to=date_to,
                           presets=presets)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001, use_reloader=False)
