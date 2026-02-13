# BaseballPath

## Overview
This project is an AI/ML-assisted baseball recruitment platform that helps athletes find the best-fit colleges based on their stats and preferences.

## Getting Started

### 1. Start the Backend (FastAPI)

From the project root directory, run:

```bash
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

- Make sure you have all required model files in `backend/ml/models/`.
- If you change any backend code, just refresh/restart the server.
- The API will be available at [http://localhost:8000](http://localhost:8000)

#### Troubleshooting
- If you get a CORS error, make sure the backend includes CORS middleware (already set up in `main.py`).
- If you get a "prediction pipeline not available" error, check that all model files exist in `backend/ml/models/`.

### 2. Start the Frontend (React)

From the `frontend` directory, run:

```bash
npm install   # Only needed the first time
npm start
```

- The app will open at [http://localhost:3000](http://localhost:3000)
- Make sure the backend is running on port 8000 for predictions to work.

### 3. Usage
- Fill out the form with your stats and click **Predict** to get your college projection probabilities.
- You can load an example or clear the form with the provided buttons.

---

## Project Structure
- `backend/` — FastAPI backend, ML models, and API logic
- `frontend/` — React app for user input and results display

---

## Development Notes
- If you add new models or change the pipeline, make sure to update the model files in `backend/ml/models/`.
- For production, update CORS settings and use a production server (e.g., gunicorn + nginx for backend, Vercel/Netlify for frontend).

---

For any issues, check the backend terminal for errors and ensure all dependencies are installed.

## Setup Instructions
- See `backend/README.md` and `frontend/README.md` for component-specific setup. 

## Auth + Billing Setup (New)

This repo now includes production-oriented auth, persisted evaluations, and Stripe plan handling.

### Supabase SQL Migration

Run:

```sql
-- In Supabase SQL editor:
-- backend/database/migrations/20260211_auth_and_entitlements.sql
```

### Backend Environment Variables

Required for protected account/evaluation APIs:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_ANON_KEY` (for issuer/audience expectations and client consistency)

Optional auth validation overrides:

- `SUPABASE_JWT_ISSUER` (defaults to `${SUPABASE_URL}/auth/v1`)
- `SUPABASE_JWT_AUDIENCE` (defaults to `authenticated`)

Stripe billing:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_PRO`
- `STRIPE_PRICE_ID_ELITE`
- `APP_BASE_URL` (e.g., `http://localhost:3000` or production URL)

### Frontend Environment Variables

- `NEXT_PUBLIC_API_URL` (backend base URL)
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Detailed Documentation

- Backend API overview:
  - `backend/api/README.md`
- Router organization:
  - `backend/api/routers/README.md`
- Auth dependency details:
  - `backend/api/deps/README.md`
- Supabase client details:
  - `backend/api/clients/README.md`
- Service layer details:
  - `backend/api/services/README.md`
- Payment plans and how to change them:
  - `backend/api/services/PAYMENT_PLANS.md`
- Migration instructions and verification:
  - `backend/database/migrations/README.md`
- Frontend auth utility docs:
  - `frontend/src/lib/README.md`
- Frontend route guard docs:
  - `frontend/src/hooks/README.md`
