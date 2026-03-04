# CLAUDE.md - Frontend Development Guide

This file documents the current frontend implementation and expectations for BaseballPath.

## Project Overview

This frontend is a Next.js App Router application for BaseballPath.

## Current Waitlist Implementation

### Flow Summary

The waitlist is now a single-page flow:

1. User opens `/prelaunch`
2. User submits form fields:
   - `full_name` (captured in UI as name)
   - `email`
   - `high_school_year` (Player HS Graduation Year)
3. Frontend calls backend `POST /waitlist/join`
4. Success state is shown inline on the same page (no redirect)

There is no in-house multi-step waitlist survey flow anymore.

### Frontend Routes

- `src/app/prelaunch/page.tsx`
  - collects and validates waitlist form input
  - submits to `${NEXT_PUBLIC_API_URL}/waitlist/join`
  - renders inline success or error feedback

- `next.config.ts`
  - redirects legacy `/waitlist` and `/waitlist/:path+` traffic to `/prelaunch`

### Removed/Deprecated Waitlist Routes

These routes were removed from the active implementation:

- `/waitlist/verify`
- `/waitlist/direct_post_waitlist_survey`
- `/waitlist/success`
- `/waitlist/post_success_large_survey`
- `/waitlist/survey-complete`

### External Survey

The waitlist page can still include a CTA link to the third-party survey (SurveyMonkey), but that survey is outside the in-house waitlist data flow.

## Backend Contract Used by Frontend

### Request

`POST /waitlist/join`

```json
{
  "email": "player@example.com",
  "name": "Player Name",
  "high_school_year": "2028"
}
```

### Response

```json
{
  "success": true,
  "message": "Successfully joined the waitlist!",
  "id": "uuid"
}
```

On failure, backend returns `detail` in the HTTP error payload.

## Waitlist Database Schema (Current)

Current table used by the waitlist flow:

```sql
create table public.waitlist (
  id uuid not null default gen_random_uuid(),
  email text not null,
  high_school_year text null,
  created_at timestamp with time zone null default now(),
  full_name text null,
  constraint waitlist_pkey primary key (id),
  constraint waitlist_email_key unique (email)
);
```

## Implementation Notes

- Waitlist writes are server-side through backend API only.
- Frontend no longer uses direct Supabase waitlist insertion helpers.
- Keep `/prelaunch` resilient: show user-friendly error messages and keep submit idempotent against duplicate email entries.

## Development Commands

```bash
npm run dev
npm run build
npm run lint
```

## Key Frontend Files

```text
frontend/src/
├── app/
│   ├── prelaunch/
│   │   └── page.tsx
│   ├── layout.tsx
│   └── page.tsx
├── components/ui/
└── lib/
    ├── auth.ts
    └── supabase-browser.ts
```
