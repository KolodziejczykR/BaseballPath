# Roster Data Acquisition — Research & Integration Plan

*Last updated: 2026-03-03*

## Why Roster Data Matters

Most recruiting platforms wait for coaches to self-report what positions they need. Not all coaches do this, and not on every platform. By analyzing the actual roster — graduating seniors, position depth, class year distribution — BaseballPath can compute which positions a team genuinely needs. This is a significantly more reliable signal and a major differentiator.

---

## Research: Data Source Evaluation

### 1. baseballr R Package (`ncaa_roster()`)

**Status: BROKEN**

- The `ncaa_roster()` function scrapes `stats.ncaa.org`, which now uses **Akamai Bot Manager**
- All programmatic HTTP requests receive a JavaScript interstitial challenge instead of roster data
- GitHub issue [#379](https://github.com/BillPetti/baseballr/issues/379) (filed July 2025, open, zero maintainer responses) confirms NCAA functions are broken
- The related `bigballR` package (basketball) migrated to `chromote` (headless Chrome) to handle the same issue
- `rvest` now offers `read_html_live()` as a workaround for JS-rendered pages, but this doesn't solve Akamai bot detection
- **Verdict: Do not rely on baseballr for roster data. stats.ncaa.org is not a viable source.**

### 2. stats.ncaa.org Direct Scraping

**Status: OPERATIONAL BUT BOT-PROTECTED**

- The site still exists and serves roster data at `https://stats.ncaa.org/teams/{team_id}/roster`
- Protected by Akamai Bot Manager — JavaScript interstitial challenges for programmatic requests
- Even headless browsers (Selenium, Playwright) may be detected by Akamai's fingerprinting
- The site has moved to dynamically loading content via JavaScript, requiring a full browser engine
- **Verdict: Not viable as a primary source. Too fragile.**

### 3. School Athletics Websites (SIDEARM Sports, etc.)

**Status: MOST VIABLE FREE SOURCE**

Most NCAA athletics websites are powered by a handful of CMS platforms:

| Platform | Estimated D1 Share | URL Pattern | Scraping Difficulty |
|----------|-------------------|-------------|-------------------|
| SIDEARM Sports | ~60% | `/sports/baseball/roster` | Low — standardized HTML |
| PrestoSports | ~15% | Varies | Moderate — different table structure |
| WMT Digital | ~5% | Varies | Moderate |
| Custom / Other | ~20% | Unpredictable | High — needs per-site handling |

**SIDEARM Sports** uses a standardized URL structure:
- Roster page: `https://{school-athletics-domain}/sports/baseball/roster`
- Season-specific: `https://{school-athletics-domain}/sports/baseball/roster/{year}`
- Player profile: `https://{school-athletics-domain}/sports/baseball/roster/{player-name}/{id}`
- Old URLs (`roster.aspx?rp_id=14132`) auto-redirect to new format

**Validation at scale:** Derek Willis' [Sports Roster Data project](https://github.com/Sports-Roster-Data/womens-college-basketball) scraped 900+ women's basketball team websites. He documented "slight but substantive variations in how colleges presented roster information" even among SIDEARM sites.

**Key considerations:**
- School websites are the **authoritative source** — updated by the schools themselves
- Generally do NOT have Akamai-level bot protection (unlike stats.ncaa.org)
- Data fields vary: some schools label all players the same position or leave fields blank
- Requires maintaining a school-to-URL mapping table
- BaseballPath already has Selenium + BeautifulSoup infrastructure for similar scraping tasks

**Verdict: Primary recommended approach. Build platform-specific parsers starting with SIDEARM.**

### 4. 6-4-3 Charts API (Paid)

**Status: BEST COMMERCIAL OPTION**

- Website: [643charts.com](https://643charts.com/)
- Purpose-built for college baseball analytics
- D1 data from 2017+, updated daily
- Player ID mapping across TrackMan, Synergy, Prep Baseball Report, Nextiles
- Custom API endpoints with trial tokens available on request
- Used by 650+ college programs and 4 MLB organizations
- **Pricing:** Contact for pricing (not publicly listed)
- **Verdict: Excellent fallback for D1 schools where scraping fails. Request trial to evaluate.**

### 5. Other Free Sources

| Source | URL | Coverage | Notes |
|--------|-----|----------|-------|
| Baseball Reference College | `baseball-reference.com/register/college-baseball-stats.shtml` | D1-D3 | Well-structured; asks for respectful scraping |
| The Baseball Cube | `thebaseballcube.com/content/college/` | NCAA, NAIA, JUCO | Stats, rosters, standings |
| D1Baseball.com | `d1baseball.com` | D1 only | No public API; requires scraping |
| Conference stats pages | Varies by conference | Conference-specific | Each conference has different format |
| Highlightly API | `highlightly.net` (via RapidAPI) | Limited | Roster data embedded in match/lineup endpoints; free tier available |
| ncaa-api (henrygd) | `github.com/henrygd/ncaa-api` | Scores/standings only | No explicit roster endpoint |

### 6. NCAA Official API

**The NCAA does NOT provide an official public API for roster or statistical data.**

What exists:
- `stats.ncaa.org` — Web portal (not a REST API), now bot-protected
- `ncaa.com` — Internal APIs that some projects reverse-engineer (unreliable)
- `dwillis/NCAA-API` on GitHub — Unofficial community project using Django + BeautifulSoup
- NCAA roster submission is an input mechanism for SIDs, not an output API

---

## Recommended Strategy: Tiered Approach

### Tier 1 — School Athletics Website Scraping (Primary)
- Build platform-specific scrapers: SIDEARM (covers ~60% of D1), PrestoSports (~15%), generic fallback
- Use existing Selenium + BeautifulSoup infrastructure
- Maintain a `roster_scrape_config` database table mapping each school to its roster URL and platform

### Tier 2 — 6-4-3 Charts API (Fallback for D1)
- Request trial API access
- Use for D1 schools where direct scraping fails or is unreliable
- Can also validate scraped data

### Tier 3 — Manual Seeding + Community Data (Edge Cases)
- Conference websites for smaller programs
- Derek Willis' Sports Roster Data CSVs for bootstrapping
- Manual curation for non-standard sites

---

## Integration Plan

### New Database Tables

**`roster_players`** — Core table, one row per player per team per season
```
school_name, team_name, season, division,
player_name, jersey_number, position, secondary_position,
class_year, normalized_class_year, is_redshirt,
height_inches, weight_lbs, hometown, high_school, previous_school,
bats, throws,
source_url, scrape_platform, scraped_at, is_active
UNIQUE(school_name, season, player_name, position)
```

**`roster_scrape_config`** — School URL registry and scraping health tracker
```
school_name (UNIQUE), team_name, division,
athletics_url, roster_url, platform,
is_scrapable, requires_selenium,
last_scrape_at, last_scrape_status, last_scrape_player_count,
consecutive_failures
```

**`roster_position_needs`** — Computed position needs per school per season
```
school_name, team_name, season, division,
total_roster_size, pitcher_count, catcher_count, infielder_count, outfielder_count,
seniors_count, juniors_count, sophomores_count, freshmen_count,
need_pitcher, need_catcher, need_infielder, need_outfielder,
need_first_base, need_second_base, need_shortstop, need_third_base,
need_left_field, need_center_field, need_right_field, need_designated_hitter,
graduating_starters_estimate, roster_turnover_rate, depth_score,
computed_at, data_quality
UNIQUE(school_name, season)
```

### New Backend Module: `backend/roster_scraper/`

```
roster_scraper/
├── __init__.py
├── base_scraper.py              # Abstract base class for platform scrapers
├── sidearm_scraper.py           # SIDEARM Sports parser (primary, covers ~60%)
├── prestosports_scraper.py      # PrestoSports parser
├── generic_scraper.py           # Fallback heuristic-based parser
├── platform_detector.py         # Detects which CMS platform a school uses
├── roster_parser.py             # Shared utilities: height parsing, class year normalization, position mapping
├── scrape_orchestrator.py       # Manages full scrape pipeline across all schools
├── url_discovery.py             # Discovers and validates roster URLs for schools
├── config_builder.py            # Populates roster_scrape_config from school_data_general
├── needs_calculator.py          # Computes position needs from roster data
└── db_builder/
    ├── roster_builder_d1.py     # D1 scrape runner
    ├── roster_builder_d2.py     # D2 scrape runner
    └── roster_builder_d3.py     # D3 scrape runner
```

### Position Needs Algorithm

Need score per position (0.0 = no need, 1.0 = critical need):

```
need_score = (departure_factor × 0.50) + (depth_factor × 0.30) + (youth_factor × 0.20)
```

- **Departure factor (50%):** What % of players at this position are seniors/grad students?
- **Depth factor (30%):** How does current headcount compare to ideal roster composition?
- **Youth factor (20%):** Weighted class year average (freshmen = 1.0, sophomores = 0.75, juniors = 0.50, seniors = 0.0)

Ideal roster composition baseline (~35 roster spots):
- 14 pitchers, 3 catchers, 2 each infield position, 2 each outfield position, 1 DH, 3 utility

Position normalization: RHP/LHP → P, IF → partial credit to 1B/2B/SS/3B, OF → partial to LF/CF/RF

### Integration with Existing Systems

**1. Playing Time Calculator** (`backend/playing_time/playing_time_calculator.py`)
- Extend `SchoolData` dataclass with `position_need_score`, `roster_size`, `graduating_at_position`, `has_roster_data`
- Update `_calculate_team_fit_bonus`: high need (≥0.7) → +0.15, moderate (0.4–0.7) → +0.05, low (<0.4) → −0.05
- Update mapper to wire roster needs data into calculator

**2. School Filtering Pipeline** (`backend/school_filtering/database/async_queries.py`)
- Load `roster_position_needs` into school enrichment cache alongside baseball rankings
- Add "position need alignment" as a nice-to-have scoring factor

**3. LLM Reasoning** (`backend/llm/recommendation_reasoning.py`)
- Include roster composition in reasoning context:
  - "University of Florida has 3 graduating senior outfielders and only 1 underclassman outfielder, suggesting strong outfield recruiting need."

**4. Future: API Endpoints** (`backend/api/routers/roster.py`)
- `GET /roster/{school_name}` — Current roster
- `GET /roster/{school_name}/needs` — Computed position needs

### Phased Rollout

| Phase | Focus | Expected Coverage |
|-------|-------|------------------|
| 1 | Database tables + SIDEARM scraper + D1 | 200–250 of ~300 D1 programs |
| 2 | Wire into playing time calculator + school filtering | Full pipeline integration |
| 3 | PrestoSports + generic scraper + D2/D3 | 800+ total programs |
| 4 | API endpoints + 6-4-3 Charts fallback + LLM context | Full feature set |

---

## Anticipated Challenges

1. **URL Discovery:** Not all schools have predictable roster URLs. Some use subdomains (`gocardinals.com`), some use university domains (`athletics.school.edu`). Config builder needs automated discovery + manual curation.

2. **SIDEARM Variation:** Even within SIDEARM, schools customize table layouts. Parser must handle missing columns, reordered columns, inconsistent labeling.

3. **Rate Limiting:** 300+ D1 schools at 3–5 seconds each = 15–25 minute full scrape. Must handle partial completion and resume gracefully.

4. **Position Ambiguity:** "IF" could be any of four positions. Needs calculator should treat ambiguous positions as partial contributors (0.25 credit each).

5. **Stale Data:** Rosters change mid-season (transfers, injuries). Track scrape timestamps, flag schools with data > 14 days old during season.

6. **D2/D3 Website Quality:** Smaller programs have less standardized websites. Generic scraper and manual curation become more important.
