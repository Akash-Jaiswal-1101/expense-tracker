"""
Tests for Step 7: Add Expense
Routes: GET /expenses/add  and  POST /expenses/add

Spec: .claude/specs/07-add-expense.md

Coverage checklist:
- Auth guard: unauthenticated GET redirects to /login (302)
- Auth guard: unauthenticated POST redirects to /login (302)
- Auth guard: following redirect lands on login page
- GET authenticated: returns 200
- GET authenticated: form contains 'amount' field
- GET authenticated: form contains 'category' field
- GET authenticated: form contains 'date' field
- GET authenticated: form contains 'description' field
- GET authenticated: date field pre-filled with today's date (YYYY-MM-DD)
- GET authenticated: all seven spec categories listed in form
- GET authenticated: page is a full HTML document (extends base.html)
- POST happy path: valid data returns 302 redirect to /profile
- POST happy path: valid data inserts exactly one expense row in DB
- POST happy path: inserted row has correct amount
- POST happy path: inserted row has correct category
- POST happy path: inserted row has correct date
- POST happy path: inserted row has correct description
- POST happy path: blank description accepted (302 + row inserted)
- POST happy path: success flash message visible after redirect
- POST happy path: new expense amount appears on /profile
- POST happy path: each of the seven valid categories accepted (parametrized)
- POST validation: missing/empty amount -> 200, error shown, no DB insert
- POST validation: non-numeric amount -> 200, error shown, no DB insert
- POST validation: zero amount ("0") -> 200, error shown, no DB insert
- POST validation: zero amount ("0.00") -> 200, error shown, no DB insert
- POST validation: negative amount -> 200, error shown, no DB insert
- POST validation: missing category -> 200, error shown, no DB insert
- POST validation: blank date -> 200, error shown, no DB insert
- POST validation: invalid date formats (parametrized) -> 200, error shown
- POST validation: invalid dates do not insert rows (parametrized subset)
- POST form preservation: amount echoed back on validation error
- POST form preservation: description echoed back on validation error
- POST form preservation: category echoed back on validation error
- POST form preservation: date echoed back on validation error
"""

import sqlite3
from datetime import date

import pytest

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """
    Isolated Flask app backed by a fresh temporary SQLite file.

    database/db.py hard-codes DB_PATH at module level.  We monkeypatch it so
    that every subsequent get_db() call goes to the temp file and never touches
    the real spendly.db.  init_db() is called explicitly to create tables.
    """
    db_file = str(tmp_path / "test_spendly.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })

    init_db()
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """
    A test client that has already registered and logged in.
    The test user has no pre-existing expenses (clean DB).
    """
    client.post("/register", data={
        "name": "Test User",
        "email": "tester@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123",
    })
    client.post("/login", data={
        "email": "tester@example.com",
        "password": "testpass123",
    })
    return client


# ---------------------------------------------------------------------------
# DB helper utilities (use parameterised SQL, never string formatting)
# ---------------------------------------------------------------------------

def _get_user_id(email: str) -> int:
    """Return the id of the user with the given email from the temp DB."""
    conn = sqlite3.connect(db_module.DB_PATH)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    assert row is not None, f"User '{email}' not found in test DB"
    return row[0]


def _count_expenses(user_id: int) -> int:
    """Return the number of expense rows owned by user_id."""
    conn = sqlite3.connect(db_module.DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def _fetch_expenses(user_id: int) -> list:
    """Return all (amount, category, date, description) tuples for user_id."""
    conn = sqlite3.connect(db_module.DB_PATH)
    rows = conn.execute(
        "SELECT amount, category, date, description FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Auth guard — both verbs must redirect unauthenticated requests to /login
# ---------------------------------------------------------------------------

class TestAuthGuard:

    def test_unauthenticated_get_returns_302(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must return 302"
        )

    def test_unauthenticated_get_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET /expenses/add must redirect to /login"
        )

    def test_unauthenticated_post_returns_302(self, client):
        response = client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
            "date": _today(),
            "description": "Lunch",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must return 302"
        )

    def test_unauthenticated_post_redirects_to_login(self, client):
        response = client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "Food",
            "date": _today(),
            "description": "Lunch",
        })
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST /expenses/add must redirect to /login"
        )

    def test_unauthenticated_get_lands_on_login_page_after_redirect(self, client):
        """Following the redirect must land on the login page, not the form."""
        response = client.get("/expenses/add", follow_redirects=True)
        body = response.data.decode("utf-8")
        assert (
            "login" in body.lower()
            or "sign in" in body.lower()
            or "Login" in body
        ), "After following redirect, unauthenticated user must reach the login page"


# ---------------------------------------------------------------------------
# GET /expenses/add — authenticated user sees the form
# ---------------------------------------------------------------------------

class TestGetAddExpenseForm:

    def test_authenticated_get_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_form_contains_amount_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert 'name="amount"' in body or "name='amount'" in body, (
            "Form must contain an input with name='amount'"
        )

    def test_form_contains_category_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert 'name="category"' in body or "name='category'" in body, (
            "Form must contain a field with name='category'"
        )

    def test_form_contains_date_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert 'name="date"' in body or "name='date'" in body, (
            "Form must contain an input with name='date'"
        )

    def test_form_contains_description_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert 'name="description"' in body or "name='description'" in body, (
            "Form must contain an input or textarea with name='description'"
        )

    def test_date_field_pre_filled_with_today(self, auth_client):
        """The date input must default to today's date in YYYY-MM-DD format."""
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert _today() in body, (
            f"Date field must be pre-filled with today's date: {_today()}"
        )

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ])
    def test_form_lists_all_spec_categories(self, auth_client, category):
        """All seven seed categories from the spec must appear in the form."""
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert category in body, (
            f"Add-expense form must include category option: '{category}'"
        )

    def test_page_is_full_html_document(self, auth_client):
        """Page must be a full HTML document, rendered from base.html."""
        response = auth_client.get("/expenses/add")
        body = response.data.decode("utf-8")
        assert "<html" in body.lower() or "<!doctype" in body.lower(), (
            "Add-expense page must render a full HTML document (extends base.html)"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — happy path
# ---------------------------------------------------------------------------

class TestPostAddExpenseHappyPath:

    def test_valid_post_returns_302(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Team lunch",
        })
        assert response.status_code == 302, (
            "Valid POST /expenses/add must return 302"
        )

    def test_valid_post_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Team lunch",
        })
        assert "/profile" in response.headers["Location"], (
            "Successful POST must redirect to /profile"
        )

    def test_valid_post_inserts_exactly_one_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "19.99",
            "category": "Transport",
            "date": "2026-09-20",
            "description": "Bus fare",
        })
        after = _count_expenses(user_id)
        assert after == before + 1, (
            "Valid POST must insert exactly one expense row into the DB"
        )

    def test_valid_post_stores_correct_amount(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        auth_client.post("/expenses/add", data={
            "amount": "99.99",
            "category": "Health",
            "date": "2026-09-10",
            "description": "Pharmacy",
        })
        amounts = [row[0] for row in _fetch_expenses(user_id)]
        assert 99.99 in amounts, (
            "Inserted expense must store the correct amount (99.99)"
        )

    def test_valid_post_stores_correct_category(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        auth_client.post("/expenses/add", data={
            "amount": "55.00",
            "category": "Entertainment",
            "date": "2026-09-01",
            "description": "Movie night",
        })
        categories = [row[1] for row in _fetch_expenses(user_id)]
        assert "Entertainment" in categories, (
            "Inserted expense must store the correct category"
        )

    def test_valid_post_stores_correct_date(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Other",
            "date": "2026-09-05",
            "description": "Misc",
        })
        dates = [row[2] for row in _fetch_expenses(user_id)]
        assert "2026-09-05" in dates, (
            "Inserted expense must store the correct date"
        )

    def test_valid_post_stores_correct_description(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        auth_client.post("/expenses/add", data={
            "amount": "30.00",
            "category": "Shopping",
            "date": "2026-09-03",
            "description": "New headphones",
        })
        descriptions = [row[3] for row in _fetch_expenses(user_id)]
        assert "New headphones" in descriptions, (
            "Inserted expense must store the correct description"
        )

    def test_blank_description_returns_302(self, auth_client):
        """Description is optional — leaving it blank must not block submission."""
        response = auth_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Bills",
            "date": "2026-09-12",
            "description": "",
        })
        assert response.status_code == 302, (
            "POST with blank description must return 302"
        )

    def test_blank_description_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Bills",
            "date": "2026-09-12",
            "description": "",
        })
        assert "/profile" in response.headers["Location"], (
            "POST with blank description must redirect to /profile"
        )

    def test_blank_description_inserts_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "7.50",
            "category": "Food",
            "date": "2026-09-08",
            "description": "",
        })
        after = _count_expenses(user_id)
        assert after == before + 1, (
            "POST with blank description must still insert a row"
        )

    def test_success_flash_message_visible_on_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Bills",
            "date": "2026-09-15",
            "description": "Electric bill",
        }, follow_redirects=True)
        body = response.data.decode("utf-8")
        assert (
            "success" in body.lower()
            or "added" in body.lower()
            or "Expense added" in body
        ), "A success flash message must be visible on the profile page after insert"

    def test_new_expense_amount_visible_on_profile(self, auth_client):
        """The amount of the inserted expense must appear in the /profile transactions list."""
        auth_client.post("/expenses/add", data={
            "amount": "123.45",
            "category": "Shopping",
            "date": "2026-09-22",
            "description": "Jacket",
        })
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        assert "123.45" in body, (
            "Newly added expense (123.45) must appear in the transactions list on /profile"
        )

    @pytest.mark.parametrize("category", [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ])
    def test_each_valid_category_is_accepted(self, auth_client, category):
        """All seven spec categories must be accepted without a validation error."""
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": category,
            "date": "2026-09-15",
            "description": "",
        })
        assert response.status_code == 302, (
            f"Category '{category}' must be accepted — expected 302, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — server-side validation errors
# ---------------------------------------------------------------------------

class TestPostAddExpenseValidation:

    # -- amount: missing / empty -----------------------------------------------

    def test_missing_amount_returns_200(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Lunch",
        })
        assert response.status_code == 200, (
            "Empty amount must re-render the form (200), not redirect"
        )

    def test_missing_amount_shows_error(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Lunch",
        })
        body = response.data.decode("utf-8")
        assert "amount" in body.lower() or "required" in body.lower(), (
            "Empty amount must display a validation error mentioning 'amount' or 'required'"
        )

    def test_missing_amount_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Lunch",
        })
        assert _count_expenses(user_id) == before, (
            "Empty amount must not insert an expense row"
        )

    # -- amount: non-numeric ---------------------------------------------------

    def test_non_numeric_amount_returns_200(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "abc",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Lunch",
        })
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form (200)"
        )

    def test_non_numeric_amount_shows_error(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "twelve",
            "category": "Food",
            "date": "2026-09-15",
            "description": "Lunch",
        })
        body = response.data.decode("utf-8")
        assert (
            "number" in body.lower()
            or "valid" in body.lower()
            or "amount" in body.lower()
        ), "Non-numeric amount must display a validation error"

    def test_non_numeric_amount_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "not-a-number",
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            "Non-numeric amount must not insert an expense row"
        )

    # -- amount: zero ----------------------------------------------------------

    @pytest.mark.parametrize("zero_value", ["0", "0.0", "0.00"])
    def test_zero_amount_returns_200(self, auth_client, zero_value):
        response = auth_client.post("/expenses/add", data={
            "amount": zero_value,
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        assert response.status_code == 200, (
            f"Zero amount '{zero_value}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("zero_value", ["0", "0.00"])
    def test_zero_amount_shows_error(self, auth_client, zero_value):
        response = auth_client.post("/expenses/add", data={
            "amount": zero_value,
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert (
            "zero" in body.lower()
            or "positive" in body.lower()
            or "greater" in body.lower()
            or "amount" in body.lower()
        ), f"Zero amount '{zero_value}' must display a validation error"

    def test_zero_amount_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            "Zero amount must not insert an expense row"
        )

    # -- amount: negative ------------------------------------------------------

    def test_negative_amount_returns_200(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "-10.00",
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        assert response.status_code == 200, (
            "Negative amount must re-render the form (200)"
        )

    def test_negative_amount_shows_error(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "-5.50",
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert (
            "positive" in body.lower()
            or "greater" in body.lower()
            or "zero" in body.lower()
            or "amount" in body.lower()
        ), "Negative amount must display a validation error"

    def test_negative_amount_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "-1.00",
            "category": "Food",
            "date": "2026-09-15",
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            "Negative amount must not insert an expense row"
        )

    # -- category: missing -----------------------------------------------------

    def test_missing_category_returns_200(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "",
            "date": "2026-09-15",
            "description": "Something",
        })
        assert response.status_code == 200, (
            "Missing category must re-render the form (200)"
        )

    def test_missing_category_shows_error(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "",
            "date": "2026-09-15",
            "description": "Something",
        })
        body = response.data.decode("utf-8")
        assert "category" in body.lower() or "required" in body.lower(), (
            "Missing category must display a validation error"
        )

    def test_missing_category_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "25.00",
            "category": "",
            "date": "2026-09-15",
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            "Missing category must not insert an expense row"
        )

    # -- date: blank -----------------------------------------------------------

    def test_blank_date_returns_200(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": "",
            "description": "",
        })
        assert response.status_code == 200, (
            "Blank date must re-render the form (200)"
        )

    def test_blank_date_shows_error(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": "",
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert "date" in body.lower() or "required" in body.lower() or "valid" in body.lower(), (
            "Blank date must display a validation error"
        )

    def test_blank_date_does_not_insert_row(self, auth_client):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": "",
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            "Blank date must not insert an expense row"
        )

    # -- date: invalid formats (parametrized) ----------------------------------

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",       # free text
        "2026/09/15",       # wrong separator
        "15-09-2026",       # DD-MM-YYYY
        "20260915",         # no separators
        "2026-13-01",       # invalid month (13)
        "2026-00-01",       # month zero
        "2026-01-32",       # day 32
        "2026-02-30",       # Feb 30 does not exist
        "yesterday",        # English word
    ])
    def test_invalid_date_format_returns_200(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": bad_date,
            "description": "",
        })
        assert response.status_code == 200, (
            f"Invalid date '{bad_date}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026/09/15",
        "15-09-2026",
        "2026-13-01",
        "2026-02-30",
    ])
    def test_invalid_date_format_shows_error(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": bad_date,
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert (
            "date" in body.lower()
            or "valid" in body.lower()
            or "required" in body.lower()
        ), f"Invalid date '{bad_date}' must display a validation error"

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "2026/09/15",
        "2026-13-01",
    ])
    def test_invalid_date_does_not_insert_row(self, auth_client, bad_date):
        user_id = _get_user_id("tester@example.com")
        before = _count_expenses(user_id)
        auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": bad_date,
            "description": "",
        })
        assert _count_expenses(user_id) == before, (
            f"Invalid date '{bad_date}' must not insert an expense row"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — form value preservation on validation error
# ---------------------------------------------------------------------------

class TestFormValuePreservationOnError:
    """
    Spec: "Flash an error message and re-render the form (preserving entered
    values) on validation failure."
    """

    def test_amount_preserved_when_category_missing(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "77.77",
            "category": "",
            "date": "2026-09-15",
            "description": "Test description",
        })
        body = response.data.decode("utf-8")
        assert "77.77" in body, (
            "Re-rendered form must echo back the entered amount (77.77) on validation error"
        )

    def test_description_preserved_when_amount_invalid(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "bad",
            "category": "Food",
            "date": "2026-09-15",
            "description": "My unique description text",
        })
        body = response.data.decode("utf-8")
        assert "My unique description text" in body, (
            "Re-rendered form must echo back the entered description on validation error"
        )

    def test_category_preserved_when_date_invalid(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Bills",
            "date": "not-a-date",
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert "Bills" in body, (
            "Re-rendered form must echo back the entered category on validation error"
        )

    def test_date_preserved_when_amount_negative(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "-99",
            "category": "Food",
            "date": "2026-09-25",
            "description": "",
        })
        body = response.data.decode("utf-8")
        assert "2026-09-25" in body, (
            "Re-rendered form must echo back the entered date on validation error"
        )
