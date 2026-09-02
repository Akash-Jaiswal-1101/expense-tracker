import sqlite3
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

app = Flask(__name__)
app.secret_key = "dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "August 2026",
        "initials": "DU",
    }
    stats = {
        "total_spent": "₹342.49",
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "Aug 28", "description": "Groceries top-up",  "category": "Food",          "amount": "₹9.99"},
        {"date": "Aug 22", "description": "Miscellaneous",      "category": "Other",         "amount": "₹15.00"},
        {"date": "Aug 18", "description": "Clothing",           "category": "Shopping",      "amount": "₹80.00"},
        {"date": "Aug 14", "description": "Movie tickets",      "category": "Entertainment", "amount": "₹25.00"},
        {"date": "Aug 10", "description": "Pharmacy",           "category": "Health",        "amount": "₹45.00"},
    ]
    categories = [
        {"name": "Bills",         "total": "₹120.00", "pct": 35},
        {"name": "Shopping",      "total": "₹80.00",  "pct": 23},
        {"name": "Health",        "total": "₹45.00",  "pct": 13},
        {"name": "Transport",     "total": "₹35.00",  "pct": 10},
        {"name": "Entertainment", "total": "₹25.00",  "pct": 7},
        {"name": "Food",          "total": "₹22.49",  "pct": 7},
        {"name": "Other",         "total": "₹15.00",  "pct": 5},
    ]
    return render_template("profile.html",
                           user=user,
                           stats=stats,
                           transactions=transactions,
                           categories=categories)


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
