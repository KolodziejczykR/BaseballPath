-- Saved schools persistence with notes and dedupe support.

create extension if not exists pgcrypto;

create table if not exists public.saved_schools (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  school_name text not null,
  school_logo_image text,
  dedupe_key text not null,
  school_data jsonb not null default '{}'::jsonb,
  note text,
  evaluation_run_id uuid references public.prediction_runs(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, dedupe_key)
);

create index if not exists idx_saved_schools_user_created_at
  on public.saved_schools(user_id, created_at desc);

create index if not exists idx_saved_schools_eval_run_id
  on public.saved_schools(evaluation_run_id);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists saved_schools_set_updated_at on public.saved_schools;
create trigger saved_schools_set_updated_at
before update on public.saved_schools
for each row execute function public.set_updated_at();

alter table public.saved_schools enable row level security;

drop policy if exists "saved_schools_select_own" on public.saved_schools;
create policy "saved_schools_select_own"
on public.saved_schools
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "saved_schools_insert_own" on public.saved_schools;
create policy "saved_schools_insert_own"
on public.saved_schools
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "saved_schools_update_own" on public.saved_schools;
create policy "saved_schools_update_own"
on public.saved_schools
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "saved_schools_delete_own" on public.saved_schools;
create policy "saved_schools_delete_own"
on public.saved_schools
for delete
to authenticated
using (auth.uid() = user_id);
