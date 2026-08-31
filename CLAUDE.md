# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

"Spendly" — a Flask expense tracker app. This is a scaffolded project where core files (`database/db.py`, `static/js/main.js`) start as stubs for students to implement.

## Setup & Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app (once app.py exists)
flask run

# Run tests
pytest

# Run a specific test
pytest tests/test_foo.py::test_name
```

## Architecture

- **Flask** web framework with **SQLite** via the standard `sqlite3` module (no ORM)
- **`database/db.py`** — central database module; must expose `get_db()`, `init_db()`, and `seed_db()`. `get_db()` returns a SQLite connection with `row_factory` set and foreign keys enabled.
- **`templates/`** — Jinja2 templates extending `base.html` (not yet created). Auth templates (`login.html`, `register.html`) already exist.
- **`static/js/main.js`** — client-side JS, starts empty and is built up incrementally.
- **`app.py`** — Flask app entry point (not yet created; students build this).

## Key Conventions

- Templates use `{% extends "base.html" %}` and `{% block content %}` / `{% block title %}`.
- Forms POST to `/login` and `/register`; errors are passed to templates as `{{ error }}`.
- The `database/` directory is a Python package (`__init__.py` present).
