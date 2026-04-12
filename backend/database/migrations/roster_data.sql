-- Roster Data schema: roster_players, roster_scrape_config, roster_position_needs
-- Run in Supabase SQL editor. Idempotent — safe to re-run.

-- ============================================================
-- roster_players: one row per player per team per season
-- ============================================================
create table if not exists public.roster_players (
  id uuid default gen_random_uuid() primary key,
  school_name text not null,
  team_name text,
  season int not null,
  division int,
  player_name text not null,
  jersey_number text,
  position text,
  normalized_position text,
  class_year text,
  normalized_class_year int,
  is_redshirt boolean default false,
  height_inches int,
  weight_lbs int,
  bats text,
  throws text,
  hometown text,
  high_school text,
  previous_school text,
  source_url text,
  scraped_at timestamptz not null default now()
);

-- Unique constraint: one entry per player per position per school per season
alter table public.roster_players
  drop constraint if exists roster_players_unique_player;
alter table public.roster_players
  add constraint roster_players_unique_player
  unique (school_name, season, player_name, position);

create index if not exists idx_roster_players_school_season
  on public.roster_players(school_name, season);
create index if not exists idx_roster_players_position
  on public.roster_players(normalized_position);
create index if not exists idx_roster_players_class_year
  on public.roster_players(normalized_class_year);

-- ============================================================
-- roster_scrape_config: one row per school, URL + scraping health
-- ============================================================
create table if not exists public.roster_scrape_config (
  id uuid default gen_random_uuid() primary key,
  school_name text not null unique,
  team_name text,
  division int,
  athletics_url text,
  roster_url text,
  platform text default 'sidearm',
  is_active boolean default true,
  requires_selenium boolean default true,
  last_scrape_at timestamptz,
  last_scrape_status text,
  last_scrape_player_count int default 0,
  consecutive_failures int default 0
);

create index if not exists idx_roster_scrape_config_active
  on public.roster_scrape_config(is_active) where is_active = true;
create index if not exists idx_roster_scrape_config_division
  on public.roster_scrape_config(division);

-- ============================================================
-- roster_position_needs: computed position needs per school per season
-- ============================================================
create table if not exists public.roster_position_needs (
  id uuid default gen_random_uuid() primary key,
  school_name text not null,
  season int not null,
  division int,

  -- Roster composition counts
  total_roster_size int,
  pitcher_count int,
  catcher_count int,
  infielder_count int,
  outfielder_count int,

  -- Class year distribution
  seniors_count int,
  juniors_count int,
  sophomores_count int,
  freshmen_count int,

  -- Position need scores (0.0 = no need, 1.0 = critical need)
  need_pitcher float,
  need_catcher float,
  need_first_base float,
  need_second_base float,
  need_shortstop float,
  need_third_base float,
  need_left_field float,
  need_center_field float,
  need_right_field float,
  need_designated_hitter float,

  -- Detailed breakdowns
  graduating_at_position jsonb default '{}'::jsonb,
  depth_by_position jsonb default '{}'::jsonb,

  -- Metadata
  data_quality text,
  computed_at timestamptz not null default now()
);

-- Unique constraint: one needs record per school per season
alter table public.roster_position_needs
  drop constraint if exists roster_position_needs_unique_school_season;
alter table public.roster_position_needs
  add constraint roster_position_needs_unique_school_season
  unique (school_name, season);

create index if not exists idx_roster_position_needs_school
  on public.roster_position_needs(school_name);
create index if not exists idx_roster_position_needs_season
  on public.roster_position_needs(season);

-- ============================================================
-- RLS: backend writes via service role (bypasses RLS)
-- ============================================================
alter table public.roster_players enable row level security;
alter table public.roster_scrape_config enable row level security;
alter table public.roster_position_needs enable row level security;

-- roster_players: read-only for authenticated users
drop policy if exists "roster_players_select_authenticated" on public.roster_players;
create policy "roster_players_select_authenticated" on public.roster_players
  for select to authenticated using (true);

-- roster_scrape_config: read-only for authenticated users
drop policy if exists "roster_scrape_config_select_authenticated" on public.roster_scrape_config;
create policy "roster_scrape_config_select_authenticated" on public.roster_scrape_config
  for select to authenticated using (true);

-- roster_position_needs: read-only for authenticated users
drop policy if exists "roster_position_needs_select_authenticated" on public.roster_position_needs;
create policy "roster_position_needs_select_authenticated" on public.roster_position_needs
  for select to authenticated using (true);

-- Note: INSERT/UPDATE/DELETE for all roster tables is done via service role (backend),
-- which bypasses RLS. No authenticated write policies needed.
