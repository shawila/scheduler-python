# Guest Booking with Email Confirmation

**Date:** 2026-06-16
**Status:** Approved

## Overview

Add a `POST /book` endpoint that lets a guest book a 30-minute-aligned appointment at a store. The booking is held as a `PendingBooking` until the guest confirms via an email link. On confirmation, a Google Calendar event is created on the store's calendar with the guest added as an attendee (Google natively sends the guest a calendar invite).

## Data Flow

```
Guest                        App                         Google Calendar
  |                            |                                |
  |-- POST /book ------------->|                                |
  |   (store, guest, time)     |-- freebusy check ------------>|
  |                            |<-- busy times ----------------|
  |                            |                                |
  |                            |-- MX check (guest email)       |
  |                            |-- slot alignment validation    |
  |                            |-- save PendingBooking (DB)     |
  |                            |-- send confirmation email ---->| (SMTP)
  |<-- 200 "check your email"--|                                |
  |                            |                                |
  |-- GET /confirm/:token ---->|                                |
  |                            |-- create Calendar event ------>|
  |                            |   (store creds + guest as      |
  |                            |    attendee → Google sends     |
  |                            |    invite to guest's email)    |
  |                            |-- save Booking (DB)            |
  |<-- 200 booking confirmed --|                                |
```

## Shared Scheduling Constants

Defined in `app/slots.py` alongside `compute_free_slots`:

| Constant | Value | Used by |
|---|---|---|
| `SLOT_DURATION_MINUTES` | `30` | `compute_free_slots`, `POST /book` validation |
| `MAX_BOOKING_DURATION_MINUTES` | `180` | `POST /book` validation |

## Models

### PendingBooking

Holds an unconfirmed booking request until the guest clicks the confirmation link (24-hour TTL).

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `confirmation_token` | String(64) | unique, not null — `secrets.token_urlsafe(32)` |
| `store_email` | String(120) | not null, must exist in Customer table |
| `guest_email` | String(120) | not null |
| `guest_name` | String(200) | not null |
| `start_datetime` | DateTime | not null, UTC |
| `end_datetime` | DateTime | not null, UTC |
| `expires_at` | DateTime | not null, set to now + 24h on creation |

### Booking

Persists a confirmed booking after the guest clicks the link and the Google Calendar event is created.

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK |
| `google_event_id` | String(200) | not null, returned by Calendar API |
| `store_email` | String(120) | not null |
| `guest_email` | String(120) | not null |
| `guest_name` | String(200) | not null |
| `start_datetime` | DateTime | not null, UTC |
| `end_datetime` | DateTime | not null, UTC |
| `created_at` | DateTime | default utcnow |

## Endpoints

### POST /book

**Request body (JSON):**
```json
{
  "store_email": "store@example.com",
  "guest_email": "guest@example.com",
  "guest_name": "John Doe",
  "date": "2024-08-02",
  "start_time": "11:00",
  "end_time": "12:30"
}
```

**Validation (fail fast, 400 on first failure):**
1. All fields present
2. `date` parses as `YYYY-MM-DD`, `start_time`/`end_time` parse as `HH:MM`
3. `start_time` < `end_time`
4. Both times are slot-aligned (minutes are `00` or `30`)
5. Duration is a non-zero multiple of `SLOT_DURATION_MINUTES`
6. Duration does not exceed `MAX_BOOKING_DURATION_MINUTES`
7. Store exists in the `Customer` table
8. Guest email domain has MX records (`dnspython`) — DNS timeout or error treated as validation failure: `400 {"error": "Could not verify guest email domain"}`
9. Requested time range is entirely free on the store's calendar (Google freebusy API)

**On success:**
- Save `PendingBooking` with token and 24h expiry
- Send confirmation email to guest with link
- Return `200 {"message": "Confirmation email sent to guest@example.com"}`

**Error responses:**
- `400` with `{"error": "<specific validation message>"}` for each validation failure
- `409` if the requested slot is already taken

### GET /confirm-booking/\<token\>

1. Look up `PendingBooking` by token — `404` if not found
2. Check `expires_at` — `410 Gone` if expired
3. Create Google Calendar event on store's calendar with guest as attendee
4. Save `Booking` record
5. Delete `PendingBooking`
6. Return `200` with event details:

```json
{
  "event_id": "google_event_id",
  "title": "Appointment",
  "start": "2024-08-02T11:00:00Z",
  "end": "2024-08-02T12:30:00Z",
  "html_link": "https://calendar.google.com/event?eid=..."
}
```

## Email

**Library:** Flask-Mail (SMTP)

**Confirmation email:**
- To: guest email
- Subject: `Confirm your appointment booking`
- Body: plain text with the confirmation link — `{BOOKING_CONFIRM_BASE_URL}/confirm-booking/{token}`

## New Dependencies

| Package | Purpose |
|---|---|
| `flask-mail>=0.10` | Send confirmation email via SMTP |
| `dnspython>=2.6` | MX record check on guest email domain |

## New Environment Variables

| Variable | Example | Description |
|---|---|---|
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP host |
| `MAIL_PORT` | `587` | SMTP port |
| `MAIL_USERNAME` | `you@gmail.com` | SMTP login |
| `MAIL_PASSWORD` | `app-password` | SMTP password or app password |
| `BOOKING_CONFIRM_BASE_URL` | `http://localhost:5000` | Base URL for confirmation links |

## File Changes

| File | Change |
|---|---|
| `app/slots.py` | Add `SLOT_DURATION_MINUTES`, `MAX_BOOKING_DURATION_MINUTES` constants |
| `app/models/pending_booking.py` | New model |
| `app/models/booking.py` | New model |
| `app/main/routes.py` | Add `POST /book` and `GET /confirm-booking/<token>` |
| `app/extensions.py` | Add Flask-Mail instance |
| `app/__init__.py` | Register Flask-Mail, import new models |
| `app/config.py` | Add mail and booking URL config |
| `requirements.txt` | Add flask-mail, dnspython |
| `.env.example` | Add mail and booking URL vars |
| `tests/test_booking_validation.py` | Unit tests for slot validation logic |
| `tests/test_booking_routes.py` | Route-level tests for POST /book and GET /confirm |
