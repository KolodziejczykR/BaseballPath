# API Routers

This directory contains canonical route modules.

## Routers

- `account.py`
  - `GET /account/me`
  - `PATCH /account/me`
- `evaluations.py`
  - `POST /evaluations/run`
  - `GET /evaluations`
  - `GET /evaluations/{run_id}`
- `billing.py`
  - `POST /billing/create-checkout-session`
  - `POST /billing/create-portal-session`
  - `POST /billing/webhook`
- `preferences.py`
  - Existing school filtering endpoints.
- `waitlist.py`
  - Existing waitlist endpoints.

## Notes

- `main.py` imports routers from this directory.
