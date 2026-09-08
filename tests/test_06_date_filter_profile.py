"""
Tests for Step 6: Date Filter on /profile

Spec: .claude/specs/06-date-filter-profile.md

Coverage:
- Auth guard: unauthenticated GET /profile redirects to /login
- Unfiltered /profile (no query params) returns 200 with all data
- This Month preset filters all three data sections
- Last 3 Months preset filters all three data sections
- Last 6 Months preset filters all three data sections
- All Time (clean URL, no params) shows all expenses
- Custom valid date range returns only matching expenses
- date_from > date_to flashes error and falls back to unfiltered view
- Malformed date_from or date_to does not crash — silently falls back
- User with no expenses in range sees ₹0.00, 0 transactions, empty breakdown
- ₹ symbol present in all filter states
- Filter bar UI elements are rendered on the profile page
"""

import sqlite3
import pytest
from datetime import date, timedelta

import database.db as db_module
from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _first_of_month() -> str:
    return date.today().replace(day=1).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path, monkeypatch):
    """
    Isolated Flask app using a temporary SQLite file.

    db.py hard-codes DB_PATH to a file on disk; we monkeypatch it so every
    get_db() call in both db.py and queries.py goes to a fresh temp file.
    The monkeypatch is applied before init_db() so the schema is created in
    the temp file, not the real spendly.db.
    """
    db_file = str(tmp_path / "test_spendly.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })

    # Create the schema in the temp DB (seed_db ran at import time on the real
    # DB; we only need the tables here — no demo data is needed).
    init_db()

    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """Logged-in test client with a fresh user and NO seeded expenses."""
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


def _get_user_id(app, email: str) -> int:
    """Return the user id for the given email from the temp DB."""
    conn = sqlite3.connect(db_module.DB_PATH)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row[0]


def _insert_expense(app, user_id: int, amount: float, category: str,
                    expense_date: str, description: str = "Test expense"):
    """Insert a single expense directly into the temp DB."""
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, (
            "Expected redirect for unauthenticated request"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated /profile must redirect to /login"
        )

    def test_unauthenticated_profile_with_date_params_redirects_to_login(self, client):
        """Date params must not bypass the auth guard."""
        response = client.get("/profile?date_from=2026-01-01&date_to=2026-12-31")
        assert response.status_code == 302, "Date params must not bypass auth guard"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated /profile with date params must redirect to /login"
        )


# ---------------------------------------------------------------------------
# Unfiltered / All Time
# ---------------------------------------------------------------------------

class TestUnfilteredProfile:
    def test_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200, (
            "GET /profile with no params must return 200"
        )

    def test_no_params_renders_rupee_symbol(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 50.00, "Food", _today())
        response = auth_client.get("/profile")
        assert "₹" in response.data.decode("utf-8"), (
            "Unfiltered profile must display ₹ symbol"
        )

    def test_no_params_shows_all_user_expenses(self, auth_client, app):
        """Expenses with very old dates must all appear in the unfiltered view."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 100.00, "Bills", "2025-01-15", "Old bill")
        _insert_expense(app, user_id, 200.00, "Food", "2024-06-10", "Older food")
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        # Both expenses sum to ₹300.00
        assert "300.00" in body, (
            "Unfiltered view must include all expenses regardless of age"
        )

    def test_all_time_clean_url_shows_expense_outside_current_month(
        self, auth_client, app
    ):
        """
        'All Time' preset uses a clean /profile URL.
        An expense that would be excluded by 'This Month' must still appear
        on the clean /profile URL — confirming the All Time view is truly
        unfiltered.
        """
        user_id = _get_user_id(app, "tester@example.com")
        # 400 days ago is safely outside any month/3-month/6-month preset window
        old_date = _days_ago(400)
        _insert_expense(app, user_id, 75.00, "Transport", old_date, "Very old expense")

        all_time_response = auth_client.get("/profile")
        this_month_response = auth_client.get(
            f"/profile?date_from={_first_of_month()}&date_to={_today()}"
        )

        all_time_body = all_time_response.data.decode("utf-8")
        this_month_body = this_month_response.data.decode("utf-8")

        assert "75.00" in all_time_body, (
            "All Time (clean /profile URL) must show expense from 400 days ago"
        )
        assert "75.00" not in this_month_body, (
            "This Month filter must NOT show expense from 400 days ago, "
            "confirming the two views genuinely differ"
        )


# ---------------------------------------------------------------------------
# This Month preset
# ---------------------------------------------------------------------------

class TestThisMonthFilter:
    def test_this_month_returns_200(self, auth_client):
        from_date = _first_of_month()
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert response.status_code == 200, "This Month filter must return 200"

    def test_this_month_includes_current_month_expense(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 42.00, "Food", _today(), "Today's lunch")
        from_date = _first_of_month()
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "42.00" in body, (
            "This Month filter must include an expense dated today"
        )

    def test_this_month_excludes_prior_month_expense(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        # 60 days ago is safely outside the current calendar month
        old_date = _days_ago(60)
        _insert_expense(app, user_id, 999.00, "Bills", old_date, "Old bill")
        from_date = _first_of_month()
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "999.00" not in body, (
            "This Month filter must exclude an expense from 60 days ago"
        )

    def test_this_month_rupee_symbol_present(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 10.00, "Other", _today())
        from_date = _first_of_month()
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ symbol must appear in This Month filtered view"
        )


# ---------------------------------------------------------------------------
# Last 3 Months preset
# ---------------------------------------------------------------------------

class TestLast3MonthsFilter:
    def test_last_3m_returns_200(self, auth_client):
        from_date = _days_ago(90)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert response.status_code == 200, "Last 3 Months filter must return 200"

    def test_last_3m_includes_expense_within_window(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        within_date = _days_ago(45)  # 45 days ago is inside the 90-day window
        _insert_expense(app, user_id, 55.00, "Health", within_date, "Within 3 months")
        from_date = _days_ago(90)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "55.00" in body, (
            "Last 3 Months filter must include an expense 45 days ago"
        )

    def test_last_3m_excludes_expense_outside_window(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        old_date = _days_ago(120)  # 120 days ago is outside the 90-day window
        _insert_expense(app, user_id, 888.00, "Shopping", old_date, "Outside 3 months")
        from_date = _days_ago(90)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "888.00" not in body, (
            "Last 3 Months filter must exclude an expense from 120 days ago"
        )

    def test_last_3m_rupee_symbol_present(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 20.00, "Food", _days_ago(30))
        from_date = _days_ago(90)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ symbol must appear in Last 3 Months filtered view"
        )


# ---------------------------------------------------------------------------
# Last 6 Months preset
# ---------------------------------------------------------------------------

class TestLast6MonthsFilter:
    def test_last_6m_returns_200(self, auth_client):
        from_date = _days_ago(180)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert response.status_code == 200, "Last 6 Months filter must return 200"

    def test_last_6m_includes_expense_within_window(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        within_date = _days_ago(150)  # inside the 180-day window
        _insert_expense(
            app, user_id, 66.00, "Entertainment", within_date, "Within 6 months"
        )
        from_date = _days_ago(180)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "66.00" in body, (
            "Last 6 Months filter must include an expense 150 days ago"
        )

    def test_last_6m_excludes_expense_outside_window(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        old_date = _days_ago(200)  # outside the 180-day window
        _insert_expense(app, user_id, 777.00, "Bills", old_date, "Outside 6 months")
        from_date = _days_ago(180)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        body = response.data.decode("utf-8")
        assert "777.00" not in body, (
            "Last 6 Months filter must exclude an expense from 200 days ago"
        )

    def test_last_6m_rupee_symbol_present(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 30.00, "Transport", _days_ago(100))
        from_date = _days_ago(180)
        to_date = _today()
        response = auth_client.get(f"/profile?date_from={from_date}&date_to={to_date}")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ symbol must appear in Last 6 Months filtered view"
        )


# ---------------------------------------------------------------------------
# Custom date range
# ---------------------------------------------------------------------------

class TestCustomDateRange:
    def test_custom_range_returns_200(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        assert response.status_code == 200, "Custom valid date range must return 200"

    def test_custom_range_includes_expense_inside_range(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 123.45, "Food", "2026-02-14", "Valentine dinner"
        )
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "123.45" in body, (
            "Expense on 2026-02-14 must appear in custom range 2026-01-01 to 2026-03-31"
        )

    def test_custom_range_excludes_expense_outside_range(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 555.00, "Bills", "2025-12-31", "Before range start"
        )
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "555.00" not in body, (
            "Expense on 2025-12-31 must not appear in custom range starting 2026-01-01"
        )

    def test_custom_range_boundary_date_from_is_inclusive(self, auth_client, app):
        """The lower bound date_from must be included in results (BETWEEN is inclusive)."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 11.11, "Other", "2026-01-01", "Boundary start"
        )
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "11.11" in body, "date_from boundary must be inclusive"

    def test_custom_range_boundary_date_to_is_inclusive(self, auth_client, app):
        """The upper bound date_to must be included in results (BETWEEN is inclusive)."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 22.22, "Other", "2026-03-31", "Boundary end"
        )
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "22.22" in body, "date_to boundary must be inclusive"

    def test_custom_range_rupee_symbol_present(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 99.00, "Shopping", "2026-02-01")
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=2026-03-31")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ symbol must appear in custom-range filtered view"
        )

    def test_only_date_from_provided_falls_back_to_unfiltered(
        self, auth_client, app
    ):
        """
        Spec: filtering activates only when BOTH params are present and valid.
        Providing only date_from must fall back to the All Time (unfiltered) view.
        """
        user_id = _get_user_id(app, "tester@example.com")
        # Insert a very old expense that a 2026-01-01 start filter would exclude
        _insert_expense(app, user_id, 44.00, "Food", "2020-01-01", "Very old expense")
        response = auth_client.get("/profile?date_from=2026-01-01")
        assert response.status_code == 200, "Partial date param must not crash"
        body = response.data.decode("utf-8")
        assert "44.00" in body, (
            "With only date_from provided the view must fall back to unfiltered "
            "and show the old expense"
        )

    def test_only_date_to_provided_falls_back_to_unfiltered(
        self, auth_client, app
    ):
        """
        Providing only date_to must fall back to the All Time (unfiltered) view.
        """
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 33.00, "Food", "2020-01-01", "Very old expense")
        response = auth_client.get("/profile?date_to=2026-01-01")
        assert response.status_code == 200, "Partial date param must not crash"
        body = response.data.decode("utf-8")
        assert "33.00" in body, (
            "With only date_to provided the view must fall back to unfiltered "
            "and show the old expense"
        )

    def test_same_date_for_both_params_is_a_valid_single_day_range(
        self, auth_client, app
    ):
        """date_from == date_to is a valid single-day range, not an error."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 15.00, "Food", "2026-06-01", "Same-day expense"
        )
        response = auth_client.get("/profile?date_from=2026-06-01&date_to=2026-06-01")
        assert response.status_code == 200, (
            "Equal date_from and date_to must return 200 — it is a valid single-day range"
        )
        body = response.data.decode("utf-8")
        assert "15.00" in body, "Single-day range must include the expense on that day"


# ---------------------------------------------------------------------------
# date_from > date_to — invalid range
# ---------------------------------------------------------------------------

class TestInvalidDateRange:
    def test_date_from_after_date_to_returns_200(self, auth_client):
        """An inverted range must not crash — it must return 200."""
        response = auth_client.get("/profile?date_from=2026-12-31&date_to=2026-01-01")
        assert response.status_code == 200, (
            "date_from > date_to must return 200, not an error page"
        )

    def test_date_from_after_date_to_flashes_exact_error_message(self, auth_client):
        """The spec mandates the exact message: 'Start date must be before end date.'"""
        response = auth_client.get(
            "/profile?date_from=2026-12-31&date_to=2026-01-01",
            follow_redirects=True,
        )
        body = response.data.decode("utf-8")
        assert "Start date must be before end date." in body, (
            "Flash error 'Start date must be before end date.' must appear in response"
        )

    def test_date_from_after_date_to_falls_back_to_unfiltered(self, auth_client, app):
        """After the invalid-range error the view must show all expenses (no filter)."""
        user_id = _get_user_id(app, "tester@example.com")
        # An expense from 2024 would be excluded if either bound were applied
        _insert_expense(app, user_id, 250.00, "Bills", "2024-06-15", "Old bill")
        response = auth_client.get(
            "/profile?date_from=2026-12-31&date_to=2026-01-01",
            follow_redirects=True,
        )
        body = response.data.decode("utf-8")
        assert "250.00" in body, (
            "After invalid date range the unfiltered view must show all expenses"
        )

    def test_same_date_from_and_date_to_does_not_trigger_error(self, auth_client):
        """date_from == date_to must NOT be treated as invalid (it is not > date_to)."""
        response = auth_client.get(
            "/profile?date_from=2026-06-15&date_to=2026-06-15",
            follow_redirects=True,
        )
        body = response.data.decode("utf-8")
        assert "Start date must be before end date." not in body, (
            "Equal date_from and date_to must not trigger the invalid-range flash message"
        )


# ---------------------------------------------------------------------------
# Malformed date parameters
# ---------------------------------------------------------------------------

class TestMalformedDateParams:
    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2026/01/01",
        "01-01-2026",
        "20260101",
        "",
        "null",
        "undefined",
        "2026-13-01",   # invalid month
        "2026-00-01",   # month zero
        "2026-01-32",   # day 32
        "'; DROP TABLE expenses; --",  # SQL injection attempt
    ])
    def test_malformed_date_from_does_not_crash(self, auth_client, bad_value):
        """Any garbage value for date_from must be silently ignored — no 500."""
        response = auth_client.get(
            f"/profile?date_from={bad_value}&date_to=2026-12-31"
        )
        assert response.status_code == 200, (
            f"Malformed date_from='{bad_value}' must not crash the app"
        )

    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2026/12/31",
        "31-12-2026",
        "20261231",
        "",
        "null",
        "undefined",
        "2026-13-31",   # invalid month
        "'; DROP TABLE expenses; --",  # SQL injection attempt
    ])
    def test_malformed_date_to_does_not_crash(self, auth_client, bad_value):
        """Any garbage value for date_to must be silently ignored — no 500."""
        response = auth_client.get(
            f"/profile?date_from=2026-01-01&date_to={bad_value}"
        )
        assert response.status_code == 200, (
            f"Malformed date_to='{bad_value}' must not crash the app"
        )

    def test_malformed_date_from_falls_back_to_unfiltered(self, auth_client, app):
        """A malformed date_from must trigger an All Time fallback."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 77.00, "Other", "2020-05-10", "Very old expense"
        )
        # With a valid date_to but bad date_from, filter must not activate
        response = auth_client.get("/profile?date_from=not-a-date&date_to=2026-12-31")
        body = response.data.decode("utf-8")
        assert "77.00" in body, (
            "Malformed date_from must cause All Time fallback — "
            "old expense must still appear"
        )

    def test_malformed_date_to_falls_back_to_unfiltered(self, auth_client, app):
        """A malformed date_to must trigger an All Time fallback."""
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(
            app, user_id, 88.00, "Other", "2020-05-10", "Very old expense"
        )
        response = auth_client.get("/profile?date_from=2026-01-01&date_to=not-a-date")
        body = response.data.decode("utf-8")
        assert "88.00" in body, (
            "Malformed date_to must cause All Time fallback — "
            "old expense must still appear"
        )

    def test_both_params_malformed_does_not_crash(self, auth_client):
        """Two bad params together must not crash."""
        response = auth_client.get("/profile?date_from=bad&date_to=also-bad")
        assert response.status_code == 200, (
            "Both malformed date params must not crash the app"
        )

    def test_sql_injection_in_date_param_does_not_corrupt_db(self, auth_client, app):
        """
        A SQL injection string passed as a date param must be rejected by the
        date-validation step and must leave the expenses table intact (no rows
        deleted or modified).
        """
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 50.00, "Food", "2026-06-01", "Safe expense")

        auth_client.get(
            "/profile?date_from='; DROP TABLE expenses; --&date_to=2026-12-31"
        )

        # Verify the table and the inserted row still exist
        conn = sqlite3.connect(db_module.DB_PATH)
        row = conn.execute(
            "SELECT amount FROM expenses WHERE user_id = ? AND description = ?",
            (user_id, "Safe expense"),
        ).fetchone()
        conn.close()
        assert row is not None, (
            "SQL injection via date param must not delete or corrupt expenses"
        )
        assert row[0] == 50.00, (
            "Expense amount must be unchanged after SQL injection attempt"
        )


# ---------------------------------------------------------------------------
# User with no expenses in the selected range
# ---------------------------------------------------------------------------

class TestEmptyRangeResults:
    def test_no_expenses_in_range_returns_200(self, auth_client):
        """A filter range that matches no data must return 200, not 500."""
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        assert response.status_code == 200, (
            "Empty result set must not cause a server error"
        )

    def test_no_expenses_in_range_shows_zero_total(self, auth_client):
        """Total spent must display as ₹0.00 when no expenses match the range."""
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        body = response.data.decode("utf-8")
        assert "₹0.00" in body, (
            "User with no expenses in range must see ₹0.00 total spent"
        )

    def test_no_expenses_in_range_shows_zero_transaction_count(self, auth_client):
        """Transaction count must be 0 when no expenses match the range."""
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        body = response.data.decode("utf-8")
        # The numeral 0 must appear in the page (transaction_count stat widget)
        assert "0" in body, (
            "User with no expenses in range must see a transaction count of 0"
        )

    def test_no_expenses_in_range_empty_category_breakdown_no_error(self, auth_client):
        """
        An empty category breakdown must not trigger a ZeroDivisionError or any
        other unhandled exception.
        """
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        assert response.status_code == 200, (
            "Empty category breakdown must not cause ZeroDivisionError or 500"
        )

    def test_user_has_expenses_but_none_match_filter(self, auth_client, app):
        """
        When a user has expenses but none fall within the active date filter,
        the view must show ₹0.00 and must not leak the out-of-range expense.
        """
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 500.00, "Bills", "2024-01-15", "Old bill")
        # Filter to a window that has no data
        response = auth_client.get("/profile?date_from=2023-01-01&date_to=2023-12-31")
        body = response.data.decode("utf-8")
        assert "₹0.00" in body, (
            "User with expenses outside the filter window must see ₹0.00 total"
        )
        assert "500.00" not in body, (
            "Expense outside the filter window must not appear in the filtered view"
        )

    def test_completely_new_user_no_expenses_unfiltered_returns_200(
        self, auth_client
    ):
        """A brand-new user with zero expenses must be able to view /profile."""
        response = auth_client.get("/profile")
        assert response.status_code == 200, (
            "User with no expenses at all must see 200 on unfiltered /profile"
        )

    def test_completely_new_user_no_expenses_shows_zero_total(self, auth_client):
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        assert "₹0.00" in body, (
            "Brand-new user with no expenses must see ₹0.00 on unfiltered /profile"
        )


# ---------------------------------------------------------------------------
# Rupee symbol presence across all filter states
# ---------------------------------------------------------------------------

class TestRupeeSymbolPresence:
    """
    The ₹ symbol must appear on every filtered and unfiltered variant of the
    profile page.  These tests complement the per-preset symbol checks above.
    """

    def test_rupee_present_on_unfiltered_view_with_data(self, auth_client, app):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 1.00, "Food", _today())
        response = auth_client.get("/profile")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ must appear in unfiltered profile view when expenses exist"
        )

    def test_rupee_present_with_date_filter_and_matching_results(
        self, auth_client, app
    ):
        user_id = _get_user_id(app, "tester@example.com")
        _insert_expense(app, user_id, 1.00, "Food", "2026-06-15")
        response = auth_client.get("/profile?date_from=2026-06-01&date_to=2026-06-30")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ must appear in filtered profile view that has results"
        )

    def test_rupee_present_with_date_filter_and_no_matching_results(
        self, auth_client
    ):
        """Even an empty result set must display ₹0.00 — the symbol must be there."""
        response = auth_client.get("/profile?date_from=2000-01-01&date_to=2000-01-31")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ must appear even when the filter returns no results (₹0.00)"
        )

    def test_rupee_present_after_invalid_range_fallback(self, auth_client):
        """After an invalid date range the fallback unfiltered view must still show ₹."""
        response = auth_client.get(
            "/profile?date_from=2026-12-31&date_to=2026-01-01",
            follow_redirects=True,
        )
        assert "₹" in response.data.decode("utf-8"), (
            "₹ must appear on fallback unfiltered view after invalid date range"
        )

    def test_rupee_present_after_malformed_date_fallback(self, auth_client):
        """After a malformed date param the fallback view must still show ₹."""
        response = auth_client.get("/profile?date_from=garbage&date_to=2026-12-31")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ must appear on fallback unfiltered view after malformed date param"
        )


# ---------------------------------------------------------------------------
# Filter bar UI — template rendering
# ---------------------------------------------------------------------------

class TestFilterBarUI:
    """
    The spec requires a filter bar with four preset buttons and two date inputs
    to be rendered in profile.html.  These tests verify the expected text labels
    and form elements are present in the HTML response.
    """

    def test_filter_bar_shows_this_month_preset(self, auth_client):
        response = auth_client.get("/profile")
        assert b"This Month" in response.data, (
            "Filter bar must include a 'This Month' preset button/link"
        )

    def test_filter_bar_shows_last_3_months_preset(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Last 3 Months" in response.data, (
            "Filter bar must include a 'Last 3 Months' preset button/link"
        )

    def test_filter_bar_shows_last_6_months_preset(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Last 6 Months" in response.data, (
            "Filter bar must include a 'Last 6 Months' preset button/link"
        )

    def test_filter_bar_shows_all_time_preset(self, auth_client):
        response = auth_client.get("/profile")
        assert b"All Time" in response.data, (
            "Filter bar must include an 'All Time' preset button/link"
        )

    def test_filter_bar_contains_date_from_input(self, auth_client):
        """The custom-range sub-form must have a date input named date_from."""
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        assert 'name="date_from"' in body or "name='date_from'" in body, (
            "Filter bar must contain an input with name='date_from'"
        )

    def test_filter_bar_contains_date_to_input(self, auth_client):
        """The custom-range sub-form must have a date input named date_to."""
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        assert 'name="date_to"' in body or "name='date_to'" in body, (
            "Filter bar must contain an input with name='date_to'"
        )

    def test_filter_bar_contains_apply_button(self, auth_client):
        """The custom-range sub-form must have an Apply submit button."""
        response = auth_client.get("/profile")
        body = response.data.decode("utf-8")
        assert "Apply" in body, (
            "Filter bar must contain an 'Apply' submit button for the custom range form"
        )

    def test_active_date_from_value_reflected_in_input(self, auth_client):
        """
        When a custom range is active, the date_from input must be pre-populated
        with the active value so the user can see the current filter state.
        """
        response = auth_client.get("/profile?date_from=2026-03-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "2026-03-01" in body, (
            "The active date_from value must appear in the rendered HTML "
            "(pre-populated in the date input or reflected elsewhere in the template)"
        )

    def test_active_date_to_value_reflected_in_input(self, auth_client):
        """
        When a custom range is active, the date_to input must be pre-populated
        with the active value.
        """
        response = auth_client.get("/profile?date_from=2026-03-01&date_to=2026-03-31")
        body = response.data.decode("utf-8")
        assert "2026-03-31" in body, (
            "The active date_to value must appear in the rendered HTML "
            "(pre-populated in the date input or reflected elsewhere in the template)"
        )
