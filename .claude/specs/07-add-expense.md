# Spec: Add Expense

## Overview
This feature lets logged-in users add a new expense through a dedicated form page at `/expenses/add`. It replaces the stub route already present in `app.py` with a fully working GET/POST handler that validates input, writes a parameterised INSERT into the `expenses` table, and redirects back to the profile page on success. This is the first write operation users can perform, making the app genuinely useful for tracking spending.

## Depends on
- Step 01 — Database Setup (expenses table must exist)
- Step 02 — Registration
- Step 03 — Login and Logout (session required)
- Step 05 — Backend Routes / Profile Page (redirect destination)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert new expense, redirect to `/profile` — logged-in only

## Database changes
No database changes. The `expenses` table already exists with columns: `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category, date, description (optional)
- **Modify:** `templates/base.html` — ensure the nav "Add Expense" link points to `/expenses/add` (may already exist)

## Files to change
- `app.py` — replace the stub `add_expense` GET route with a full GET/POST handler

## Files to create
- `templates/add_expense.html` — add expense form page

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (not relevant here, but keep in mind)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect unauthenticated users to `/login`
- Validate server-side: amount must be a positive number, category must be non-empty, date must be a valid YYYY-MM-DD string
- Flash a success message on successful insert
- Flash an error message and re-render the form (preserving entered values) on validation failure
- Categories should match the seed data values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- The `date` field should default to today's date

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data inserts a row into `expenses` and redirects to `/profile` with a success flash
- [ ] The new expense appears in the transactions list on the profile page
- [ ] Submitting with a missing amount shows a validation error and re-renders the form
- [ ] Submitting with a non-numeric amount shows a validation error
- [ ] Submitting with a negative or zero amount shows a validation error
- [ ] Submitting with a missing category shows a validation error
- [ ] Submitting with an invalid date shows a validation error
- [ ] The description field is optional — form submits successfully when left blank
- [ ] The date field pre-fills with today's date
