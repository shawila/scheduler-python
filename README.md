# scheduler-python

A Flask web app that integrates with Google Calendar via OAuth 2.0. Users connect their Google account, and the app stores their credentials to query busy hours on demand.

Also includes a standalone CLI script (`main.py`) that prints free 30-minute slots for any given day.

## Features

- Google OAuth 2.0 flow: connect a calendar with one redirect
- Stores per-user credentials in a local database (SQLite by default)
- `GET /get-busy-hours` returns calendar events for any date
- `app/slots.py` — pure, testable free-slot computation logic

## Prerequisites

- Python 3.9+
- A Google Cloud project with the **Google Calendar API** and **Google OAuth 2.0** enabled
- A `credentials.json` file downloaded from the Google Cloud Console (OAuth 2.0 Client ID, Desktop or Web type)

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd scheduler-python

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set SECRET_KEY to a random string

# 5. Place your credentials.json in the project root (do not commit it)

# 6. Run database migrations
flask db upgrade

# 7. Start the server
python run.py
```

## Environment Variables

| Variable       | Default             | Description                                  |
|----------------|---------------------|----------------------------------------------|
| `FLASK_ENV`    | —                   | Set to `development` to allow HTTP for OAuth |
| `SECRET_KEY`   | `your-secret-key`   | Flask session secret — change before deploy  |
| `DATABASE_URL` | `sqlite:///app.db`  | SQLAlchemy connection string                 |

## API Endpoints

### `GET /`
Redirects the user to the Google OAuth consent screen.

### `GET /callback`
OAuth redirect target. Stores or updates the user's calendar credentials in the database.

### `GET /get-busy-hours`

Returns calendar events for a given user and date.

| Parameter | Required | Format       | Default |
|-----------|----------|--------------|---------|
| `email`   | yes      | string       | —       |
| `date`    | no       | `YYYY-MM-DD` | today   |

**Example:**
```
GET /get-busy-hours?email=user@example.com&date=2024-08-01
```

**Response:**
```json
[
  {"start": "2024-08-01T09:00:00Z", "end": "2024-08-01T10:00:00Z"},
  {"start": "2024-08-01T14:00:00Z", "end": "2024-08-01T15:30:00Z"}
]
```

## Standalone CLI

`main.py` authenticates via a local browser flow and prints free 30-minute slots for today:

```bash
python main.py
```

Credentials are cached in `token.pickle` (gitignored) for subsequent runs.

## Running Tests

```bash
python3 -m pytest tests/ -v
```

Tests cover `app/slots.py` (pure slot computation logic) and require no Google API credentials.

## Project Structure

```
scheduler-python/
├── app/
│   ├── __init__.py        # Flask app factory
│   ├── config.py          # Configuration from environment
│   ├── extensions.py      # SQLAlchemy instance
│   ├── slots.py           # Pure free-slot computation (testable, no Google deps)
│   └── main/
│       ├── __init__.py
│       └── routes.py      # OAuth flow and calendar endpoints
├── app/models/
│   └── customer.py        # Customer model (stores OAuth tokens)
├── migrations/            # Alembic migrations
├── tests/
│   └── test_scheduler.py  # Unit tests for slot logic
├── main.py                # Standalone CLI script
├── run.py                 # Flask app entry point
├── requirements.txt
└── .env.example
```
