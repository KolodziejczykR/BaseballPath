# PBR Player Profile Scraper

Scrapes committed player profiles from [Prep Baseball Report](https://www.prepbaseballreport.com) to build training data for BaseballPath ML models.

## What it does

1. **Phase 1 (Commitments):** Crawls the PBR `/commitments` page filtered by class year (2022-2027), paginating through all pages to collect every committed player's profile URL and basic info (name, state, high school, position, committed school).

2. **Phase 2 (Profiles):** Visits each player's individual profile page and scrapes all "Best Of" stats **with the date each metric was recorded** -- the key data missing from our original scrape. This includes pitching (FB/CH/CB/SL velo + spin), hitting (exit velo, bat speed, hand speed, etc.), running (60yd, 30yd, 10yd), and defense (INF/OF/C velo, pop time).

3. **Phase 3 (Schools):** For each committed school, follows the `/schools/{slug}` link to get conference and division, then classifies into P4 / Non-P4 D1 / Non-D1. School results are cached so each school is only scraped once.

## Output

**Single CSV:** `backend/data/rescraped/pbr_all_players.csv`

69 columns total -- every stat has a paired `_date` column:

| Category | Columns |
|----------|---------|
| Player info | name, link, player_state, high_school, class, primary_position, commitment, age, positions, height, weight, throwing_hand, hitting_handedness |
| Pitching | fastball_velo_max, fastball_velo_range, fastball_spin, changeup_velo_range, changeup_spin, curveball_velo_range, curveball_spin, slider_velo_range, slider_spin (each with `_date`) |
| Power | exit_velo_max, exit_velo_avg, distance_max, sweet_spot_p (each with `_date`) |
| Hitting | hand_speed_max, bat_speed_max, rot_acc_max, hard_hit_p (each with `_date`) |
| Running | sixty_time, thirty_time, ten_yard_time, run_speed_max (each with `_date`) |
| Defense | inf_velo, of_velo, c_velo, pop_time (each with `_date`) |
| School | player_region, conference, division, college_location, committment_group |
| Meta | scraped_at |

Supporting files (also in `backend/data/rescraped/`):
- `commitments_urls.csv` -- player URLs collected in Phase 1
- `school_cache.json` -- cached school conference/division lookups
- `checkpoint.json` -- scraping progress (for resume)
- `scraper.log` -- full log

## Prerequisites

```bash
pip install selenium
```

Chrome + ChromeDriver must be installed. The scraper uses the existing `SeleniumDriverManager` from `backend/school_info_scraper/selenium_driver.py`.

## How to run

All commands run from the project root (`code/`).

### Full pipeline (recommended first run)

```bash
# Scrape everything: commitment URLs -> profiles -> school info
python3 -m backend.pbr_scraper.runner
```

### Two-phase approach (recommended for large runs)

Phase 1 is fast (~30 min). Phase 2 is the long one (~40-50 hours for all 6 class years). Running them separately lets you inspect the URL list before committing to the full scrape.

```bash
# Phase 1: Collect all committed player URLs (~53k players)
python3 -m backend.pbr_scraper.runner --commitments-only

# Phase 2: Scrape each profile (checkpoints every 25 players)
python3 -m backend.pbr_scraper.runner --profiles-only
```

### Resuming after interruption

The scraper checkpoints progress. If it gets interrupted (Ctrl+C, crash, etc.), just re-run the same command -- it will skip already-scraped profiles automatically.

```bash
# Picks up where it left off
python3 -m backend.pbr_scraper.runner --profiles-only
```

### Subset of class years

```bash
# Only scrape 2026 and 2027 classes
python3 -m backend.pbr_scraper.runner --years 2026 2027
```

### Retry failed profiles

Some profiles may fail due to timeouts or page errors. After a full run, retry them:

```bash
python3 -m backend.pbr_scraper.runner --retry-failed
```

### Debug mode (visible browser)

```bash
python3 -m backend.pbr_scraper.runner --visible --years 2027
```

### Adjust request delay

```bash
# Slower (safer, less likely to get blocked)
python3 -m backend.pbr_scraper.runner --delay 5.0

# Faster (riskier)
python3 -m backend.pbr_scraper.runner --delay 2.0
```

## Scale estimates

| Class | Pages | ~Players |
|-------|-------|----------|
| 2022 | 106 | 10,600 |
| 2023 | 108 | 10,800 |
| 2024 | 105 | 10,500 |
| 2025 | 108 | 10,800 |
| 2026 | 95 | 9,500 |
| 2027 | 12 | 1,200 |
| **Total** | **534** | **~53,400** |

At ~3 seconds per profile page, Phase 2 takes roughly 40-50 hours. The checkpoint system means you can stop and restart freely.

## Architecture

```
backend/pbr_scraper/
  config.py                 # Settings, column mappings, region/division classification
  commitments_scraper.py    # Phase 1: paginate /commitments, collect player URLs
  profile_scraper.py        # Phase 2: scrape individual profile stats + dates
  school_scraper.py         # Phase 3: scrape /schools/{slug}, cache results
  runner.py                 # Main pipeline, checkpointing, CSV output
```

Uses the shared `SeleniumDriverManager` from `backend/school_info_scraper/selenium_driver.py` -- same Chrome stealth settings used by the Massey scraper.
