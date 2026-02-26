# API Clients

This directory holds shared external client setup helpers.

## `supabase.py`

Exposes:
- `get_supabase_url()`
- `get_supabase_service_key()`
- `get_supabase_anon_key()`
- `get_supabase_admin_client()`
- `require_supabase_admin_client()`

Usage pattern:
- Prefer `require_supabase_admin_client()` in request handlers/services where the dependency is mandatory.
- Use `get_supabase_admin_client()` only when you intentionally want a nullable client.

Required env vars:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

