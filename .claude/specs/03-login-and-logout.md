# Spec: Login and Logout

## Overview
Implement session-based login and logout so registered users can authenticate and access protected pages. The existing stub `GET /login` route is upgraded to a full `GET`/`POST` handler that validates credentials, starts a Flask session, and redirects to the dashboard (or a placeholder). A `POST /logout` route clears the session and redirects to the landing page. This step gates all future authenticated features behind a real login wall.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user`, password hashing in place)

## Routes
- `GET /login` — render login form — public (already exists as stub, upgrade it)
- `POST /login` — validate credentials, set session, redirect to `/dashboard` or re-render with error — public
- `POST /logout` — clear session, redirect to `/` — logged-in only

## Database changes
No new tables or columns. A new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — returns a single `sqlite3.Row` for the matching user, or `None` if not found.

## Templates
- **Modify**: `templates/login.html`
  - Change the form `action` to `url_for('login')` with `method="post"`
  - Add `name` attributes to all inputs: `email`, `password`
  - Add a block to display flash error messages (e.g. "Invalid email or password")
  - Keep all existing visual design
- **Modify**: `templates/base.html`
  - Add a logout button/link (POST form) in the nav when `session.user_id` is set
  - Add a login link in the nav when no session is active

## Files to change
- `app.py` — upgrade `login()` to handle `GET` and `POST`; implement `logout()` as `POST`; import `session` from Flask; import `check_password_hash` from werkzeug; import `get_user_by_email` from db
- `database/db.py` — add `get_user_by_email(email)` helper
- `templates/login.html` — wire up form action/method and flash message display
- `templates/base.html` — add conditional nav links for login/logout state

## Files to create
None.

## New dependencies
No new dependencies. Uses Flask's built-in `session` and `werkzeug.security.check_password_hash` (already installed).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Use `werkzeug.security.check_password_hash` to verify passwords — never compare plaintext
- Store only `user_id` and `user_name` in `session` — never store the password hash
- `app.secret_key` must be set (already done in Step 02)
- Logout must use `POST` (not `GET`) to prevent CSRF via link prefetch; use a `<form method="post">` in the nav
- On login failure, re-render the form with a generic error "Invalid email or password" — do not reveal whether the email exists
- On login success, call `session.clear()` first then set `session['user_id']` and `session['user_name']`, then redirect to `url_for('dashboard')` (placeholder route is acceptable for now)
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- Use `url_for()` for every internal link — never hardcode URLs

## Definition of done
- [ ] `GET /login` renders the login form without errors
- [ ] Submitting valid credentials sets the session and redirects (no 500 error)
- [ ] Submitting an unknown email re-renders the form with "Invalid email or password"
- [ ] Submitting a correct email but wrong password re-renders the form with "Invalid email or password"
- [ ] Submitting with empty fields re-renders the form with a validation error
- [ ] `POST /logout` clears the session and redirects to `/`
- [ ] After logout, navigating to a protected route does not show the previous user's data
- [ ] The nav shows a logout button when logged in and a login link when logged out
