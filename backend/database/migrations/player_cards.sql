-- Player Cards & Share Links schema
-- Run in Supabase SQL editor or via migration tooling.

create extension if not exists pgcrypto;

-- ============================================================
-- Alter profiles table for new fields
-- ============================================================
alter table public.profiles add column if not exists high_school_name text;
alter table public.profiles add column if not exists video_links jsonb default '[]'::jsonb;

-- ============================================================
-- player_cards: one card per user, auto-updates with new evals
-- ============================================================
create table if not exists public.player_cards (
  id uuid default gen_random_uuid() primary key,
  user_id uuid not null unique references public.profiles(id) on delete cascade,
  latest_evaluation_run_id uuid references public.prediction_runs(id) on delete set null,
  display_name text not null,
  high_school_name text,
  class_year int,
  primary_position text,
  state text,
  stats_snapshot jsonb not null,
  prediction_level text,
  d1_probability float,
  p4_probability float,
  photo_storage_path text,
  video_links jsonb default '[]'::jsonb,
  bp_profile_link text,
  visible_preferences jsonb default '{}'::jsonb,
  preferences_snapshot jsonb default '{}'::jsonb,
  card_theme text default 'classic',
  is_active boolean default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_player_cards_user_id on public.player_cards(user_id);

-- ============================================================
-- card_share_links: trackable share URLs
-- ============================================================
create table if not exists public.card_share_links (
  id uuid default gen_random_uuid() primary key,
  card_id uuid not null references public.player_cards(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  slug text not null unique,
  platform text,
  label text,
  is_active boolean default true,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_card_share_links_slug on public.card_share_links(slug);
create index if not exists idx_card_share_links_card_id on public.card_share_links(card_id);

-- ============================================================
-- card_link_clicks: analytics for share link engagement
-- ============================================================
create table if not exists public.card_link_clicks (
  id uuid default gen_random_uuid() primary key,
  share_link_id uuid not null references public.card_share_links(id) on delete cascade,
  card_id uuid not null,
  user_id uuid not null,
  clicked_at timestamptz not null default now(),
  referrer text,
  user_agent text,
  ip_hash text,
  platform_detected text,
  is_unique boolean default true
);

create index if not exists idx_card_link_clicks_share_link on public.card_link_clicks(share_link_id, clicked_at desc);
create index if not exists idx_card_link_clicks_card_id on public.card_link_clicks(card_id);

-- ============================================================
-- Triggers: auto-update updated_at
-- ============================================================
drop trigger if exists player_cards_set_updated_at on public.player_cards;
create trigger player_cards_set_updated_at
before update on public.player_cards
for each row execute function public.set_updated_at();

-- ============================================================
-- RLS Policies
-- ============================================================
alter table public.player_cards enable row level security;
alter table public.card_share_links enable row level security;
alter table public.card_link_clicks enable row level security;

-- player_cards: users manage own
drop policy if exists "player_cards_select_own" on public.player_cards;
create policy "player_cards_select_own" on public.player_cards
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "player_cards_insert_own" on public.player_cards;
create policy "player_cards_insert_own" on public.player_cards
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "player_cards_update_own" on public.player_cards;
create policy "player_cards_update_own" on public.player_cards
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "player_cards_delete_own" on public.player_cards;
create policy "player_cards_delete_own" on public.player_cards
  for delete to authenticated using (auth.uid() = user_id);

-- card_share_links: users manage own
drop policy if exists "card_share_links_select_own" on public.card_share_links;
create policy "card_share_links_select_own" on public.card_share_links
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists "card_share_links_insert_own" on public.card_share_links;
create policy "card_share_links_insert_own" on public.card_share_links
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "card_share_links_delete_own" on public.card_share_links;
create policy "card_share_links_delete_own" on public.card_share_links
  for delete to authenticated using (auth.uid() = user_id);

-- card_link_clicks: owner can read, service role inserts
drop policy if exists "card_link_clicks_select_own" on public.card_link_clicks;
create policy "card_link_clicks_select_own" on public.card_link_clicks
  for select to authenticated using (auth.uid() = user_id);

-- Note: INSERT for card_link_clicks is done via service role (backend),
-- so no authenticated INSERT policy needed. The service role bypasses RLS.
