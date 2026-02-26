# API Dependencies

This directory contains shared FastAPI dependencies.

## `auth.py`

Provides:
- `AuthenticatedUser` dataclass
- `get_current_user` dependency

`get_current_user` behavior:
1. Reads `Authorization: Bearer <token>`.
2. Decodes JWT payload.
3. Validates issuer and audience.
4. Confirms token/user via Supabase auth API.
5. Returns `AuthenticatedUser` with:
   - `user_id`
   - `email`
   - `access_token`
   - decoded `claims`

Required env vars:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- optional:
  - `SUPABASE_JWT_ISSUER`
  - `SUPABASE_JWT_AUDIENCE`

