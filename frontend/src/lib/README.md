# Frontend Auth/Session Utilities

## Files

- `supabase-browser.ts`
  - Singleton Supabase browser client using:
    - `NEXT_PUBLIC_SUPABASE_URL`
    - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `auth.ts`
  - helper wrappers:
    - `getCurrentSession()`
    - `getCurrentUser()`
    - `getAccessToken()`
    - `getAuthHeader()`

## Where It Is Used

- `src/app/login/page.tsx` for auth flows.
- `src/hooks/useRequireAuth.ts` for route gating.
- protected pages:
  - `src/app/predict/page.tsx`
  - `src/app/dashboard/page.tsx`
  - `src/app/plans/page.tsx`

