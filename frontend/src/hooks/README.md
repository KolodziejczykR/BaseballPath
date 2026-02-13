# Frontend Hooks

## `useRequireAuth.ts`

Purpose:
- Require a valid Supabase session for protected pages.
- Redirect unauthenticated users to:
  - `/login?next=<currentPath>`

Returns:
- `loading`
- `session`
- `user`
- `accessToken`

Used by:
- `src/app/predict/page.tsx`
- `src/app/dashboard/page.tsx`

You can add it to other pages that should be auth-gated.

