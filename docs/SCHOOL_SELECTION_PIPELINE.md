# BaseballPath — School Selection Pipeline (End-to-End)

This document is a full-stack walkthrough of how BaseballPath turns a raw user
evaluation request into a ranked list of college baseball matches. It covers
every deterministic score, every weight, every threshold, every filter, and
every LLM-enhanced reranking step. Use it as the source-of-truth input for
deeper research and calibration work.

File anchors are referenced inline so you can jump straight to the code.

> **Heads up on playing time**: BaseballPath used to have a standalone
> `PlayingTimeCalculator` that produced a z-score and a bucket label
> ("Likely Starter", "Compete for Time", …). **That module is no longer
> wired into the live pipeline.** It has been replaced by the per-school
> deep roster + stats research described in Sections 6–9. The legacy
> formulas are still documented in Section 10 for historical reference
> only — see that section for full context.

---

## 0. Pipeline Overview

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  USER INPUT                                                                   │
│  ─ Baseball metrics (physicals + tools)                                       │
│  ─ ML prediction (D1 prob, P4 prob, final tier)                               │
│  ─ Academic input (GPA, SAT/ACT, AP)                                          │
│  ─ Preferences (regions, budget, ranking_priority)                            │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — Academic scoring           → academic composite + athlete boost     │
│  STEP 2 — Player PCI computation     → ML-PCI + Benchmark-PCI → blended PCI   │
│  STEP 3 — Load schools + enrich      → SCI (per school), trend bonus, tier   │
│  STEP 4 — Match & rank (baseline)    → delta = PCI − SCI → fit label          │
│           + academic fit delta                                                │
│           + region + budget filters                                           │
│           + mismatch exclusions                                               │
│           → 50-school "consideration pool" OR 15-school baseline              │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │
                (Finalize step — enqueued as a Celery background job)
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│  STEP 5 — Deep school research (per school, deterministic)                    │
│           • Scrape official roster + stats pages                              │
│           • Parse players, cross-ref with jersey+name                         │
│           • Project departures forward by years_until_enrollment              │
│           • Compute evidence (openings, competition, opportunity)             │
│  STEP 6 — LLM reviewer (fit refinement, up to ±1 level)                       │
│  STEP 7 — Deterministic ranking_adjustment (up to ±14 points)                 │
│  STEP 8 — Cross-school composite reranking                                    │
│           • Priority-weighted fit family + opportunity + academic penalty     │
│  STEP 9 — Category-capped trim to final_limit (default 15)                    │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                          Final 15 schools → user
```

Two flows exist in the router (`backend/api/routers/evaluate.py`):
- **Preview** (`/evaluate/preview`): Steps 1–4 only, `consideration_pool=False`, `limit=15`. No LLM. Stored as `pending_evaluations`.
- **Finalize** (`/evaluate/finalize`) / legacy `/evaluate/run`: Reruns Steps 1–4 with `consideration_pool=True`, `school_limit=50`, then enqueues the deep-research job that executes Steps 5–9 and writes results back to `prediction_runs`.

---

## 1. User Inputs

Defined in `backend/api/routers/evaluate.py` as Pydantic models:

### 1.1 `BaseballMetrics`
- `height` (60–84 in), `weight` (120–320 lb)
- `primary_position` (IF/OF/C/P family; see `backend/utils/position_tracks.py`)
- `throwing_hand`, `hitting_handedness`, `player_region`, `graduation_year`
- **Hitter fields**: `exit_velo_max`, `sixty_time`, `inf_velo` | `of_velo` | `c_velo` + `pop_time`
- **Pitcher fields**: `fastball_velo_max`, `fastball_velo_range`, `fastball_spin`, `changeup_velo/spin`, `curveball_velo/spin`, `slider_velo/spin`

### 1.2 `MLPrediction` (produced upstream by the ML router)
- `final_prediction`: normalized into `"Power 4 D1"`, `"Non-P4 D1"`, or `"Non-D1"`
- `d1_probability` (0–1), `p4_probability` (0–1, optional)
- `confidence`, model detail blobs

### 1.3 `AcademicInput`
- `gpa` (0.0–4.0)
- `sat_score` (400–1600, optional)
- `act_score` (1–36, optional)
- `ap_courses` (≥ 0)
- **At least one of SAT or ACT is required** (422 otherwise).

### 1.4 `PreferencesInput`
- `regions`: list of Northeast / Southeast / Midwest / Southwest / West, or `None` for all
- `max_budget`: one of `under_20k`, `20k_35k`, `35k_50k`, `50k_65k`, `65k_plus`, `no_preference`
- `ranking_priority`: one of `playing_time` / `baseball_fit` / `academics` / `None` (balanced)

Region → state mapping in `REGION_STATES` (`school_matching.py:47`).
Budget ranges in `BUDGET_RANGES` (`school_matching.py:58`).

---

## 2. Academic Scoring

File: `backend/evaluation/academic_scoring.py`

Composite academic score in the range **1.0 – 10.0**, then a **+0.5 athlete boost** to produce the "effective" score used for matching.

### 2.1 Component ratings (1–10)

**GPA brackets** (`_GPA_BRACKETS`):
| GPA floor | Rating |
|-----------|--------|
| ≥ 3.95    | 10 |
| ≥ 3.85    | 9  |
| ≥ 3.70    | 8  |
| ≥ 3.50    | 7  |
| ≥ 3.30    | 6  |
| ≥ 3.00    | 5  |
| ≥ 2.70    | 4  |
| ≥ 2.40    | 3  |
| ≥ 2.00    | 2  |
| < 2.00    | 1  |

**ACT brackets** (`_ACT_BRACKETS`):
| ACT floor | Rating |
|-----------|--------|
| ≥ 35 | 10 |
| 34   | 9  |
| 33   | 8  |
| 30–32 | 7 |
| 27–29 | 6 |
| 24–26 | 5 |
| 21–23 | 4 |
| 18–20 | 3 |
| 15–17 | 2 |
| ≤ 14  | 1 |

**SAT brackets** (`_SAT_BRACKETS`):
| SAT floor | Rating |
|-----------|--------|
| ≥ 1550 | 10 |
| 1500   | 9  |
| 1440   | 8  |
| 1370   | 7  |
| 1290   | 6  |
| 1200   | 5  |
| 1100   | 4  |
| 1000   | 3  |
|  900   | 2  |
|   0    | 1  |

When BOTH SAT and ACT are provided, the **higher** of the two ratings is used.

**AP course brackets** (`_AP_BRACKETS`, **floor of 3**):
| AP courses | Rating |
|------------|--------|
| ≥ 7 | 10 |
| 6   | 9  |
| 5   | 8  |
| 4   | 7  |
| 3   | 6  |
| 2   | 5  |
| 1   | 4  |
| 0   | 3  |

### 2.2 Composite formula
```
composite = (gpa_rating × 0.40) + (test_rating × 0.40) + (ap_rating × 0.20)
effective = composite + 0.5   # ATHLETE_BOOST
```

- GPA is 40%, test score 40%, AP 20%.
- Every prospect gets a flat **+0.5 athlete boost** because all users are prospective recruits; this shifts them up vs. the general-admission academic selectivity score of each school.
- `effective` is the value compared against `school.academic_selectivity_score` during matching.

The result dict also surfaces `gpa_rating`, `test_rating`, `ap_rating` for transparency and UI.

---

## 3. Player Competitiveness Index (PCI)

File: `backend/evaluation/competitiveness.py` (called by `school_matching.compute_player_pci`)

PCI lives on a **0–100 national competitiveness scale** so it can be compared directly against School SCI (same scale). PCI is the tier-aware `ml_based_pci` — a within-tier percentile mapped into the tier's PCI band, with a cross-tier nudge from the ML `d1_probability` / `p4_probability`.

### 3.1 Tier PCI bands (`TIER_PCI_BANDS`)
| Predicted tier | PCI band |
|----------------|----------|
| Power 4 D1     | 69.0 – 100.0 |
| Non-P4 D1      | 35.0 – 88.0  |
| Non-D1         |  0.0 – 45.0  |

Bands are calibrated to the empirical School SCI distribution (per-group p5/p95) and intentionally **overlap** to model reality (top Non-P4 > bottom P4).

### 3.2 Within-tier percentile (0–100)
`school_matching.compute_within_tier_percentile` computes an average z-score of the player's metrics against the **predicted tier's benchmarks**, then maps it through the standard-normal CDF.

- **Hitter stats used**: `exit_velo_max`, `sixty_time` (sign-flipped — lower is better), and ONE positional: `inf_velo` / `of_velo` / `c_velo` (+ `pop_time` for catchers).
- **Pitcher stats used**: fastball max + range + spin, changeup velo + spin, curveball velo + spin, slider velo + spin.
- Missing stats are skipped; if none are available the percentile defaults to 50.
- Percentile is clamped to [0, 100].

### 3.3 ML-based PCI (`ml_based_pci`)
```
base = band_low + (within_tier_percentile / 100) × (band_high − band_low)
```
Then a **ML-probability nudge** is added:
- Power 4 tier: `base += (p4_prob − 0.65) × 8.0`
- Non-P4 D1 tier: `base += (d1_prob − 0.65) × 6.0`
- Non-D1 tier: `base += (d1_prob − 0.15) × 25.0`

The Non-D1 slope is intentionally large: within a single tier the ML `d1_probability` is the primary cross-tier signal for how close a player is to the D1 line. A high-d1_prob Non-D1 player reaches top-D3 SCI territory; a low-d1_prob Non-D1 player does not.

Clamped to [0, 100].

### 3.4 Final PCI (`final_pci`)
```
player_pci = ml_pci
```
`final_pci` is a thin pass-through of `ml_pci`, clamped to [0, 100]. There is no tier-agnostic benchmark blend — all cross-tier awareness lives in the `ml_based_pci` d1/p4 nudge.

> **Why no benchmark blend?** A prior implementation blended `ml_pci` 60/40 with a tier-agnostic `benchmark_pci` derived from metric-level interpolation against per-tier benchmark anchors. That blend was hijackable: a single elite metric (for example a 6.97 60-time sitting at the P4 anchor mean) could pull a 53rd-percentile Non-D1 player to a `player_pci` around 38, matching them to top-15 D3 schools as "Fit". Pushing cross-tier awareness into `d1_probability` inside `ml_based_pci` — and retuning `TIER_PCI_BANDS` against the real SCI distribution — solves the same problem without the single-metric hijack path.

The per-school metric comparison table (`_build_metric_comparisons` in `school_matching.py`) is unrelated and still uses `DIVISION_BENCHMARKS` / `get_position_benchmarks` directly for the "player vs school group averages" UI panel.

---

## 4. School Competitiveness Index (SCI)

File: `backend/evaluation/competitiveness.py` → `compute_school_sci_from_rankings`
Storage: precomputed and cached in `backend/school_filtering/database/async_queries.py` under `baseball_sci_hitter` / `baseball_sci_pitcher` per school.

### 4.1 Data sources
- **`baseball_rankings_data`** (Massey-style ratings): `overall_rating`, `offensive_rating`, `defensive_rating`, `power_rating`, by `year` and `division`, joined to `school_data_general` via `school_baseball_ranking_name_mapping` (team_name bridge).
- Years loaded: **2023 / 2024 / 2025**.
- Per-year `division` max ranks build `DEFAULT_DIVISION_MAX_RANKS`:
  - D1: 305
  - D2: 253
  - D3: 388
  (Overridable by live max-per-year-per-metric from the DB.)

### 4.2 Rank → percentile → national scale
1. `rank_to_percentile(rank, max_rank)` = `(1 − (rank−1)/(max_rank−1)) × 100`, clamped [0, 100].
2. `to_national_scale(percentile, division)` maps into `NATIONAL_BANDS`:
   - D1 → 40.0 – 100.0
   - D2 → 10.0 – 43.0
   - D3 →  0.0 – 38.0

### 4.3 Recency weighting (`YEAR_WEIGHTS`)
- 2025: **0.50**
- 2024: **0.30**
- 2023: **0.20**

Each rating metric is independently recency-weighted, only over the years that actually have data.

### 4.4 Hitter vs Pitcher SCI blends
**Hitter SCI base**:
```
0.50 × overall_weighted
0.35 × offensive_weighted
0.15 × power_weighted
```

**Pitcher SCI base**:
```
0.50 × overall_weighted
0.30 × power_weighted
0.20 × defensive_weighted
```

### 4.5 Trend bonus (`compute_trend_bonus`)
Only uses overall_rating.
```
trend_1yr = sci_2025 − sci_2024
trend_2yr = sci_2025 − sci_2023
raw = 0.6 × trend_1yr + 0.4 × trend_2yr
trend_bonus = clamp(raw × 0.15, -5, +5)
```
- Programs rising nationally → positive bonus (harder to get into).
- Programs declining → negative bonus (easier).
- Added onto both `sci_hitter` and `sci_pitcher` after clamp [0, 100].

### 4.6 SCI fallback ladder (`school_matching._resolve_school_sci`)
When a school has no precomputed SCI:
1. Use `baseball_division_percentile` + `baseball_division` → national scale.
2. Use raw `baseball_overall_rating` + `DEFAULT_DIVISION_MAX_RANKS`.
3. Tier constants (`FALLBACK_SCI_BY_TIER`): P4=78, Non-P4 D1=54, Non-D1=24.

---

## 5. Baseline School Matching (`match_and_rank_schools`)

File: `backend/evaluation/school_matching.py` (line 372+)

This is the **deterministic first pass** that runs in both preview and finalize flows.

### 5.1 Pre-filters (hard cuts)
Order matters:

1. **Region filter**: if `selected_regions` is set, `school.school_state` must be in the union of `REGION_STATES[region]`.
2. **Budget filter**: if `max_budget` is set and `user_state` known, compare the correct tuition column:
   - In-state → `school.in_state_tuition`
   - Out-of-state → `school.out_of_state_tuition`
   - (If `user_state` unknown, assume out-of-state.)
   - Cut if `tuition > max_budget`.
3. **SCI availability**: drop schools where no SCI can be resolved (even with fallback ladder).

### 5.2 Baseball fit delta + label
```
delta = player_pci − school_sci
```

**Fit labels** (`classify_fit`):
| Delta range       | Label          |
|-------------------|----------------|
| delta > 8         | Strong Safety  |
| 4 < delta ≤ 8     | Safety         |
| −4 ≤ delta ≤ 4    | Fit            |
| −8 ≤ delta < −4   | Reach          |
| delta < −8        | Strong Reach   |

Legacy label (`to_legacy_fit_label`) collapses to `fit`/`safety`/`reach` for frontend display.

**Extreme-mismatch cutoffs** (hard drop before scoring):
- Baseline mode: `delta > 25` OR `delta < −20`.
- Consideration-pool mode: `delta > 20` OR `delta < −18` (tighter, to keep research costs focused).

### 5.3 Academic fit delta + label
```
academic_delta = effective_academic_score − school.academic_selectivity_score
```
If no school score available, default `school_acad_numeric = 2.0` (very permissive).

**Academic fit labels** (`_academic_fit_label`):
| Delta range         | Label         |
|---------------------|---------------|
| delta > 2.4         | Strong Safety |
| 0.9 < delta ≤ 2.4   | Safety        |
| −0.9 ≤ delta ≤ 0.9  | Fit           |
| −1.8 ≤ delta < −0.9 | Reach         |
| −2.4 ≤ delta < −1.8 | Strong Reach  |
| delta < −2.4        | **Excluded**  |

### 5.4 Mismatch exclusions
- **Baseline**: drop schools that are `Strong Safety` baseball **AND** `Strong Safety` academic — both extreme-too-easy.
- **Consideration pool**: drop schools with baseball `Safety`/`Strong Safety` **AND** academic `Strong Safety` (settling too much on both axes).

### 5.5 Selection / balancing logic
Metric comparison table is built per candidate for UI explainability (`_build_metric_comparisons` — player vs division average in key tools, using `_resolve_metric_benchmark_key`; Non-D1 splits into D2/D3 when available).

**Consideration pool path** (`consideration_pool=True`, `limit=50`):
1. Sort by `abs(delta) + ACAD_DISTANCE[academic_fit] × 1.5`, where `ACAD_DISTANCE`:
   - Fit: 0.0, Safety: 1.0, Reach: 1.5, Strong Safety: 3.0, Strong Reach: 3.5.
2. Reserve **up to 12 slots** for academically-appropriate schools (`Fit` / `Reach` / `Safety`) as `MIN_ACAD_DIVERSE = 12`.
3. Backfill remaining slots from the sorted pool.
4. Trim to `limit` (50).

**Baseline path** (`consideration_pool=False`, `limit=15`):
1. Filter out `Strong Safety` / `Strong Reach` (keep only regular `Safety` / `Fit` / `Reach`). If the regular set is empty, fall back to the full candidate set.
2. Sort by `abs(delta)` ascending (closest matches first).
3. Bucket targets:
   - **Fits**: up to `min(8, limit)` = **8 fits**.
   - **Safeties**: up to 4.
   - **Reaches**: fill remaining.
4. If still under limit, backfill from everything unused, sorted by `(abs_delta, −delta)` (prefer reaches over safeties on ties).
5. Resort final selection by `delta` descending (safeties first, reaches last in list order — UI decides display).

Every school gets a `rank` = 1..N assigned post-sort.

---

## 6. Deep School Research (per-school, deterministic)

File: `backend/llm/deep_school_insights.py` — `DeepSchoolInsightService._gather_evidence`.

Triggered **only in the finalize flow** via a Celery job (`backend/llm/tasks.py → generate_deep_school_research`) on the 50-school consideration pool.

### 6.1 What's fetched
- `school.roster_url` (from `school_data_general.baseball_roster_url`, attached in `_attach_roster_urls`).
- Stats URL derived by replacing `/roster` → `/stats` on the same path.
- Fetched concurrently via `httpx` with a real User-Agent and 20s timeout; stats get a 1-retry with 10s backoff for JS-heavy sites.

### 6.2 Roster parsing
Uses `SidearmRosterScraper` layouts (card → table → generic) and picks the highest-quality parse (`_parsed_roster_quality`). Each `ParsedPlayer` is normalized with:
- `position_raw` / `position_normalized` / `position_family` (P / C / OF / INF)
- `normalized_class_year` via `normalize_class_year` (0..4, and `is_redshirt`)
- `previous_school` classified via `_looks_like_college` regex (university/college/CC/JC/JUCO/institute keywords)

### 6.3 Stats parsing
`_parse_stats_records` reads every `<table>`, identifies batting vs pitching from headers (`AVG/AB` vs `ERA/IP/WHIP/W-L/APP/APP-GS/SV`), and pulls `GP/GS` (handling combined formats like `30-25`). Produces `ParsedStatLine` rows.

### 6.4 Player × stats match
`_match_players_to_stats` cross-references:
1. Jersey number + last name match.
2. Fallback: last name + first initial match.

Returns `MatchedPlayer` objects with attached batting/pitching stats.

### 6.5 Deterministic evidence computation (`_compute_evidence`)
Keyed on the player's **position family** (P/C/OF/INF) from their `primary_position`, and exact normalized position where possible.

**Enrollment projection**
```
years_out = min(3, max(0, graduation_year − current_year))
```
A player entering in 2027 from 2026 gets `years_out=1`.

**Departure projection** (`_will_depart`)
```
effective_year = normalized_class_year − (1 if redshirt else 0)
will_depart = (effective_year + years_out) >= 4
```
So by the time the recruit arrives, players whose projected class year is senior+ will be gone.

**Counts computed**
- `same_family_count`: current roster size at position family
- `same_exact_position_count`: exact positional matches
- `likely_departures_same_family`: projected forward
- `likely_departures_exact_position`
- `same_family_upperclassmen` (projected class ≥ 3 after years_out)
- `same_family_underclassmen` (projected class 1–2)
- `returning_high_usage_same_family`: non-departing players with GS ≥ 10 (`HIGH_USAGE_GS_THRESHOLD`)
- `returning_high_usage_exact_position`
- `incoming_same_family_transfers`: any matching-family player whose `previous_school` is a college

**Position data quality** (`position_data_quality`):
- `exact`: all parsed rows have normalized positions
- `mixed`: mix of exact + family-only
- `family_only`: everyone only has IF/OF/P broad category
- `unknown`: parsing failed

### 6.6 Starter opening estimate
`_estimate_openings(departures, total, returning_high_usage)`:

With stats available:
- ≥ 3 departures and ≤ 2 returning high-usage → **high**
- ≥ 2 departures and ≤ 3 high-usage → **medium**
- ≤ 1 departure and ≥ 4 high-usage → **low**

Without stats, by departure ratio:
- ≥ 0.30 → high, ≥ 0.15 → medium, else low.

### 6.7 Opportunity level
`_estimate_opportunity(departures, total, returning_starters)`:
- ≥ 3 departures → **high**
- ≤ 1 returning_starters AND ≥ 2 departures → **high**
- ≥ 2 departures → **medium**
- else **low**

### 6.8 Competition level
`_estimate_competition(total, returning_starters, underclassmen)`:
- With stats: returning ≥ 5 → high, ≥ 3 → medium, else low.
- Without stats: total ≥ 8 AND underclassmen ≥ 4 → high, total ≥ 5 → medium, else low.

### 6.9 When evidence is "meaningful"
`_has_meaningful_evidence` — any of: non-unknown position quality, non-zero same-family counts, departures > 0, opportunity/competition non-unknown, or any incoming transfer/recruit signal.

If NOT meaningful → skip the LLM reviewer entirely and return `research_status = insufficient_evidence` with `ranking_adjustment = 0`.

---

## 7. LLM Reviewer (Fit Refinement)

File: `backend/llm/deep_school_insights.py` — `_review_school` / `_review_instructions` / `_review_input`.

- Model: `OPENAI_REVIEW_MODEL` env, default `gpt-5.4-nano`.
- Uses `client.responses.parse(...)` with `text_format=DeepSchoolReview` (strict pydantic schema).
- Temperature: 0. Max output: 2500 tokens. Timeout: `OPENAI_RESEARCH_TIMEOUT_S` default 90s.

### 7.1 Input packet
A JSON-serialized dict with:
- `player`: primary_position, position_family, archetype, height/weight, exit_velo_max/sixty_time, enrollment_year, years_until_enrollment, AND only the **position-relevant** defensive metric (of_velo / inf_velo / c_velo + pop_time).
- `baseball_assessment`: predicted_tier, percentiles, PCIs, probabilities.
- `academic_score`: composite + effective + subratings.
- `athletic_match`: fit_label, academic_fit, delta, school_sci, metric_comparisons.
- `program_trend`: trend_bonus, conference.
- `evidence`: full `GatheredEvidence.model_dump()`.

### 7.2 What the reviewer returns (`DeepSchoolReview`)
- `base_athletic_fit`, `opportunity_fit`, `final_school_view`
- `adjustment_from_base`: one of `none` / `up_one` / `down_one` — **this is the only handle the LLM has over ranking**. It can push the fit up or down by one level (e.g. Reach → Fit) and no more.
- `confidence`: `high` / `medium` / `low` — multiplies the deterministic adjustment.
- Summaries: `fit_summary`, `program_summary`, `roster_summary`, `opportunity_summary`, `trend_summary`
- `reasons_for_fit` (2–4 bullets), `risks` (1–3 bullets), `data_gaps`.

### 7.3 Confidence multipliers
| confidence | multiplier |
|------------|------------|
| high       | 1.0        |
| medium     | 0.7        |
| low        | 0.35       |

---

## 8. Ranking Adjustment (Deterministic, per-school)

Function: `compute_ranking_adjustment(evidence, review)`.

Signed points summed from discrete buckets, then multiplied by the reviewer's confidence multiplier, then clamped to ±`MAX_RERANK_ADJUSTMENT = 14`.

### 8.1 Point tables

**Opportunity level** (`LEVEL_POINTS`):
| level | points |
|-------|--------|
| high     | +8.0 |
| medium   | +3.0 |
| low      | −5.0 |
| unknown  |  0.0 |

**Competition level** (`COMPETITION_POINTS`):
| level | points |
|-------|--------|
| low      | +5.0 |
| medium   | +1.0 |
| high     | −5.0 |
| unknown  |  0.0 |

**Starter opening estimate — same family** (`OPENING_POINTS`):
| level | points |
|-------|--------|
| high   | +4.0 |
| medium | +2.0 |
| low    | −2.0 |

**Starter opening estimate — exact position**: same table × 0.75.

**Position data quality** (`POSITION_DATA_POINTS`):
| quality | points |
|---------|--------|
| exact       | +2.0 |
| mixed       | +1.0 |
| family_only |  0.0 |
| unknown     |  0.0 |

**Reviewer adjustment** (`ADJUSTMENT_POINTS`):
| adjustment | points |
|------------|--------|
| up_one   | +6.0 |
| none     |  0.0 |
| down_one | −6.0 |

**Roster delta**:
```
raw += min(likely_departures_same_family, 4)
raw -= min(impact_additions_same_family × 1.5, 5.0)
raw -= min(incoming_same_family_transfers × 1.0, 3.0)
```

### 8.2 Final formula
```
raw_total = sum of all the above
scaled = raw_total × confidence_multiplier
ranking_adjustment = clamp(scaled, −14, +14)

# Quality bonus — added AFTER clamp but re-clamped:
if _has_meaningful_evidence(evidence):
    ranking_adjustment += RESEARCH_QUALITY_BONUS (1.5)   # completed path
    # OR
    ranking_adjustment += 0.5 × 1.5 = 0.75                # partial/reviewer-failed path
ranking_adjustment = min(ranking_adjustment, 14)
```

Schools where evidence gathering failed get `ranking_adjustment = 0` and `research_status = insufficient_evidence` or `failed`.

### 8.3 Per-school ranking score (`compute_ranking_score`)
```
if delta >= 0:
    fit_distance = delta × 1.0         # safeties penalized at full rate
else:
    fit_distance = abs(delta) × 0.85   # reaches slightly preferred (aspirational)
ranking_score = −fit_distance + ranking_adjustment
```

### 8.4 Roster label (display)
`compute_roster_label` → `"open"` / `"competitive"` / `"crowded"` / `"unknown"` using a smaller coefficient set:

| signal | high | medium | low |
|--------|------|--------|-----|
| opportunity_level              | +3 | +1 | −2 |
| competition_level (low=good)   | +2 |  0 | −2 |
| starter_opening_same_family    | +3 | +1 | −1 |

Plus `min(departures, 3) × 1.0`, `−min(transfers, 3) × 1.0`, `−min(impact_additions, 3) × 1.5`.

Thresholds: score ≥ 4 → "open", score < −2 → "crowded", else "competitive".

---

## 9. Cross-School Composite Reranking

Function: `_apply_cross_school_reranking` — runs **after every school has been reviewed**. This is the step where user `ranking_priority` actually changes the ordering.

### 9.1 Relative opportunity z-score
Over the pool of researched schools, compute per school:
```
raw_signal = compute_raw_opportunity_signal(school)   # same bucket points as 8.1
mean, std = stats(raw_signals)
z = clamp((raw − mean) / max(std, 1.0), −2.5, +2.5)    # CROSS_SCHOOL_Z_CLAMP
relative_opportunity_bonus = z × 2.5                   # CROSS_SCHOOL_OPPORTUNITY_WEIGHT
```

### 9.2 Fit family base (`FIT_FAMILY_BASE`)
| fit_label      | base |
|----------------|------|
| Fit            | 100  |
| Safety         |  50  |
| Strong Safety  |  30  |
| Reach          |  20  |
| Strong Reach   |   0  |

### 9.3 Academic penalty — continuous (`_academic_penalty`)
Uses the raw `academic_delta` when available (preferred over labels):
```
if |delta| ≤ 0.9:              penalty = 0
elif delta > 0.9 (safety dir): penalty = −((delta − 0.9)^1.5) × 1.5
else (reach dir):              penalty = −((|delta| − 0.9)^1.5) × 1.2
```
If `academic_delta` is missing, fallback to `ACADEMIC_FIT_PENALTY_MAP`:
| academic_fit    | penalty |
|-----------------|---------|
| strong safety   | −4.0 |
| safety          | −1.5 |
| fit             |  0.0 |
| reach           | −1.75 |
| strong reach    | −5.0 |

### 9.4 Priority weights (`PRIORITY_WEIGHTS`)
Four canonical profiles:

| priority        | fit_family_base | ranking_score | opportunity_bonus | academic_penalty |
|-----------------|----------------:|--------------:|------------------:|-----------------:|
| `None` (balanced) | 1.0 | 1.0 | 1.0 | 1.0 |
| `playing_time`  | 0.8 | 1.0 | **2.0** | 0.6 |
| `baseball_fit`  | **1.3** | **1.2** | 0.5 | 0.8 |
| `academics`     | 0.9 | 0.8 | 0.5 | **2.0** |

### 9.5 Composite formula
```
composite = w.fit_family_base × FIT_FAMILY_BASE[fit_label]
          + w.ranking_score   × ranking_score
          + w.opportunity_bonus × relative_opportunity_bonus
          + w.academic_penalty × academic_fit_penalty
```
Schools are then sorted by `(composite, ranking_score, delta)` descending.

### 9.6 Category caps on final list (`final_limit=15`)
Once sorted by composite:

- **MAX_STRONG_SAFETY = 2** strong-safety schools
- **MAX_STRONG_REACH = 2** strong-reach schools
- **MAX_ACAD_STRONG_SAFETY**: 5 normally, **2 when `ranking_priority == "academics"`**

These prevent extreme labels from dominating the top 15. Non-strong labels are kept first, then up to the cap from each strong bucket, then re-sorted.

### 9.7 Selection-from-research-pool behavior
- The research pool starts at 50 schools (from `match_and_rank_schools(..., consideration_pool=True, school_limit=50)`).
- All are reviewed in sequential batches (`OPENAI_RESEARCH_BATCH_SIZE`, default 1 → then 1).
- Between batches, the pool is re-sorted by current `ranking_score` so the most promising schools get researched first. This is a **research-first selection**: roster evidence can promote a low-ranked delta school over a closer delta school that has no openings.

Output: `final_limit = 15` schools, each with `rank` assigned 1..15.

---

## 10. Playing Time Calculator (DEPRECATED — NOT IN USE)

File: `backend/playing_time/playing_time_calculator.py`

> ⚠️ **IMPORTANT: This module is currently NOT used in the live school-selection pipeline.**
>
> It was the v1-era playing-time estimator and has been **effectively replaced** by the far more extensive per-school deep roster + stats evaluation documented in Sections 6–9 (`backend/llm/deep_school_insights.py`). The evaluate router (`backend/api/routers/evaluate.py`) does **not** call `PlayingTimeCalculator` anywhere in the `preview → finalize` flow.
>
> **Why it was subbed out**: the old calculator relied purely on z-score aggregation against division benchmarks plus coarse team-needs signals inferred from Massey offensive/defensive ratings. The new path actually scrapes the target school's official roster and stats pages, projects departures forward to the player's enrollment year, computes real positional openings/competition/opportunity, and has an LLM reviewer refine fit — producing a much more grounded playing-time signal per school.
>
> The `playing_time` module is kept in the repo for two reasons:
> 1. Its benchmark dictionaries (`DIVISION_BENCHMARKS`, `PITCHER_DIVISION_BENCHMARKS`, `get_position_benchmarks`) are re-exported via `backend/constants.py` and are the source of truth used by both within-tier percentile (`school_matching.compute_within_tier_percentile`) and the per-school metric comparison table (`school_matching._build_metric_comparisons`).
> 2. Historical reference while the new research-based approach stabilizes.
>
> The formulas below are **documentation-only** — they describe the legacy algorithm. Do not treat them as current behavior when planning new work; any "playing time" signal surfaced to the user today comes from `roster_label` + `opportunity_fit` in Section 8/9, not from this calculator.

### 10.1 Final formula
```
z_total = stats_component + physical_component + ml_component
        + team_fit_bonus + trend_bonus
```

### 10.2 Weights
| Component | Weight |
|-----------|--------|
| Best stat z-score (dynamic rank) | 0.30 |
| Middle stat z-score              | 0.25 |
| Worst stat z-score               | 0.20 |
| Height + weight (avg z)          | 0.15 |
| ML alignment (player level vs school level) | 0.10 |

Catcher defensive stat combines `c_velo` and `pop_time` with 60/40 weighting favoring the higher z-score.

### 10.3 ML alignment
```
player_level (0-100)  — see PLAYER_LEVEL_* bands below
school_level (0-100)  — see SCHOOL_LEVEL_BANDS
gap = player_level − school_level
component = (gap / 50) × 0.10              # ~±0.20 max practical
```

**Player level bands**:
| Profile | Base | Range |
|---------|------|-------|
| Elite P4       | 88 | +12  |
| Standard P4    | 70 | +20  |
| High Non-P4 D1 | 55 | +20  |
| Mid Non-P4 D1  | 45 | +17  |
| Low D1         | 32 | +16  |
| Sub-D1 (D2/D3) |  0 | ×50  |

**School level bands** (`SCHOOL_LEVEL_BANDS`):
| Tier        | Floor | Width |
|-------------|-------|-------|
| P4          | 70    | 30    |
| Non-P4 D1   | 45    | 30    |
| D2          | 25    | 30    |
| D3          | 10    | 30    |

### 10.4 Team-needs alignment bonus
Trigger: player's best stat category matches the team's inferred weakness (`offensive_rating` vs `defensive_rating` in Massey, lower = better; `TEAM_NEEDS_RATING_THRESHOLD = 3.0`).

```
if aligned AND best_stat_z ≥ 0.5:
    bonus = 0.05 + (best_stat_z − 0.5) × 0.10
    bonus = min(bonus, 0.20)
```

Speed players (`STAT_TO_STRENGTH["sixty_time"] = "speed"`) get partial credit for either need.

### 10.5 Trend bonus
| trend     | bonus |
|-----------|-------|
| declining | +0.12 |
| stable    |   0  |
| improving | −0.08 |

### 10.6 Bucket thresholds (`PLAYING_TIME_BUCKETS`)
| z floor | bucket              |
|---------|---------------------|
| ≥ 1.5   | Likely Starter      |
| ≥ 1.0   | Compete for Time    |
| ≥ 0.5   | Developmental       |
| ≥ 0.0   | Roster Fit          |
| ≥ −0.5  | Stretch             |
| < −0.5  | Reach               |

Percentile is converted via standard normal CDF (`erf`).

---

## 11. Division Benchmarks (Data Source)

File: `backend/playing_time/constants.py`. Used by **both** evaluation and playing-time code paths via `backend/constants.py` re-exports.

### 11.1 Dataset sizes
- P4: 2,603 players
- Non-P4 D1: 5,630 players
- Mid-Major D1: 3,571 players
- Low-Major D1: 2,059 players
- D2: 4,176 players
- D3: 7,103 players

Calculated from `all_hitter_data.csv` with outlier filtering — see `backend/data/division_benchmarks.ipynb`.

### 11.2 Hitter benchmark example (P4)
| Stat        | Mean  | Std  |
|-------------|-------|------|
| exit_velo   | 95.4  | 5.97 |
| sixty_time  | 7.02  | 0.34 |
| inf_velo    | 84.66 | 5.29 |
| of_velo     | 86.94 | 5.57 |
| c_velo      | 79.02 | 3.90 |
| pop_time    | 1.99  | 0.10 |
| height (in) | 72.65 | 2.25 |
| weight (lb) | 187.32 | 19.04 |

### 11.3 Pitcher benchmark example (P4)
| Stat                     | Mean   | Std    |
|--------------------------|--------|--------|
| fastball max             | 90.47  | 3.63   |
| fastball spin avg        | 2187.07| 194.27 |
| curveball velo range     | 74.22  | 4.14   |
| slider velo range        | 77.27  | 4.17   |
| changeup spin            | 1764.20| 265.67 |

### 11.4 Position-specific benchmarks
`get_position_benchmarks(primary_position)` maps to one of:
- `OF_DIVISION_BENCHMARKS`
- `MIF_DIVISION_BENCHMARKS`
- `CIF_DIVISION_BENCHMARKS`
- `C_DIVISION_BENCHMARKS`
- generic `DIVISION_BENCHMARKS` (fallback)

Position-specific benchmarks only include stats that vary by position (e.g. OF runs faster 60s, CIF are bigger).

---

## 12. Data Sources (Supabase)

Ingestion → matching (`backend/school_filtering/database/async_queries.py::get_all_schools`):
1. `school_data_general` — base table (`school_name`, `display_school_name`, `school_state`, tuitions, `academic_selectivity_score`, logo, roster URL, conference, divisions, niche grades).
2. `school_baseball_ranking_name_mapping` — school_name ↔ baseball team_name bridge (`verified` column — only non-false rows are loaded).
3. `baseball_rankings_data` — year/division-keyed Massey ratings (2023/2024/2025 pulled).
4. On first load, an in-memory cache is built per school containing: `division_group`, `baseball_division`, `baseball_overall_rating`, `baseball_offensive/defensive/power_rating`, `baseball_strength_of_schedule`, `baseball_division_percentile`, `baseball_sci_hitter`, `baseball_sci_pitcher`, `baseball_trend_bonus`, yearly overall national snapshot.

`_derive_division_group` canonicalizes into the three tier constants:
- `POWER_4_D1` if division_group says so OR division=1 with a Power 4 conference (ACC / SEC / Big Ten / Big 12 / Pac-12 token matching)
- `NON_P4_D1` if D1 and not Power 4
- `NON_D1` for D2/D3 or unknown

---

## 13. Persistence & Flow Artifacts

All numbers travel through the API as JSON. Key tables in `prediction_runs`:

- `identity_input` — `{name, state, graduating_class}`
- `stats_input` — full player metric dict
- `preferences_input` — `{regions, max_budget, academic_input}`
- `prediction_response` — ML inputs
- `preferences_response.schools` — final ranked schools
- `preferences_response.academic_score` — `{composite, effective, gpa_rating, test_rating, ap_rating}`
- `preferences_response.baseball_assessment` — `{predicted_tier, within_tier_percentile, player_competitiveness_index, ml_pci, d1_probability, p4_probability}`
- `llm_reasoning_status` — `queued | processing | completed | partial | insufficient_evidence | failed | skipped | unavailable`
- `llm_job_id`

Per-school, the stored record includes:
- baseline: `delta`, `sci`, `fit_label`, `baseball_fit`, `academic_fit`, `academic_delta`, `trend`, `trend_bonus`, `metric_comparisons`, `niche_academic_grade`, `estimated_annual_cost`, `division_label`, `location`
- after research: `ranking_adjustment`, `ranking_score`, `research_confidence`, `roster_label`, `overall_school_view`, `review_adjustment_from_base`, `fit_summary`, `program_summary`, `roster_summary`, `opportunity_summary`, `trend_summary`, `research_reasons`, `research_risks`, `research_data_gaps`, `research_sources`, `research_packet`
- after cross-school: `raw_opportunity_signal`, `relative_opportunity_zscore`, `relative_opportunity_bonus`, `academic_fit_penalty`, `cross_school_composite`, `rank`

---

## 14. Summary Cheat Sheet

| Concept | Value / formula | File |
|---|---|---|
| Academic composite | `0.4·gpa_r + 0.4·test_r + 0.2·ap_r` | `academic_scoring.py` |
| Athlete boost | `+0.5` | `academic_scoring.py` |
| PCI final | `ml_pci` (tier band + d1/p4_prob nudge) | `competitiveness.py` |
| SCI hitter | `0.50·overall + 0.35·offensive + 0.15·power` | `competitiveness.py` |
| SCI pitcher | `0.50·overall + 0.30·power + 0.20·defensive` | `competitiveness.py` |
| Recency weights | 2025:0.50 / 2024:0.30 / 2023:0.20 | `competitiveness.py` |
| Trend bonus | `clamp((0.6·Δ1y + 0.4·Δ2y)·0.15, −5, +5)` | `competitiveness.py` |
| Fit delta label | `>8 SS, >4 S, ±4 F, −8 R, <−8 SR` | `competitiveness.py` |
| Academic delta label | `>2.4 SS, >0.9 S, ±0.9 F, ≥−1.8 R, ≥−2.4 SR` | `school_matching.py` |
| Baseline selection | 8 fits / 4 safeties / fill reaches → 15 | `school_matching.py` |
| Consideration pool | ≥12 acad-good reserved, sort = `abs(delta) + 1.5·acad_distance` | `school_matching.py` |
| Research adjustment cap | `±14 × confidence_mult` | `deep_school_insights.py` |
| Confidence mult | high 1.0 / med 0.7 / low 0.35 | `deep_school_insights.py` |
| Quality bonus (completed) | `+1.5` to adjustment | `deep_school_insights.py` |
| Relative opportunity bonus | `clamp(z, ±2.5) × 2.5` | `deep_school_insights.py` |
| Composite | `Σ w_i × component_i` with priority weights | `deep_school_insights.py` |
| Strong-label cap (final 15) | 2 strong safety / 2 strong reach / ≤5 acad SS (≤2 when acad priority) | `deep_school_insights.py` |
| Priority profiles | balanced / playing_time (opp×2) / baseball_fit (fit×1.3, rank×1.2) / academics (penalty×2) | `deep_school_insights.py` |

---

## 15. Open Questions / Suggested Deep Research Angles

These are the tuning surfaces most likely to need empirical validation:

1. **Band calibration** — the 0–100 PCI/SCI scale is built from national anchors and Massey-rank percentiles. Ground-truth calibration via "what players actually committed where" is the highest-leverage experiment.
2. **PCI blend weight (60/40)** — the ratio of ML to benchmark PCI. Stress-test on edge cases (elite metrics + low ML confidence; weak metrics + high ML probability).
3. **Trend bonus magnitude (±5)** — currently narrow; whether program trajectory is actually this small an effect vs. base rank.
4. **Fit delta thresholds** (±4 for Fit, ±8 for Reach/Safety) — are these the right buckets for recruiting reality, or is the fit window wider at certain tiers?
5. **Academic delta thresholds** — 0.9 / 1.8 / 2.4 on a 1–10 effective scale. Worth validating vs actual admissions-rate differentials.
6. **Ranking adjustment cap of ±14** — is 14 points enough to move a "strong reach" into the "reach" territory? Given typical delta spread, this governs whether roster research can ever really beat raw metrics.
7. **Priority profile weights** — the four profiles (balanced / playing_time / baseball_fit / academics) are hand-tuned. Real user behavior should drive these.
8. **Strong-category caps (2/2/5/2)** — the hard caps on strong safeties/reaches in the final 15. Too restrictive or too loose?
9. **Playing-time bucket thresholds** — **note**: the standalone `PlayingTimeCalculator` (Section 10) is no longer used in the live flow; today's playing-time signal comes from the deep roster research's `opportunity_level` / `competition_level` / `roster_label`. Tuning work should target those rules, not the legacy z-score cutoffs.
10. **Consideration pool academic reservation (12 slots)** — how much academic diversity to preserve for research vs baseball closeness.
11. **LLM confidence multipliers (1.0/0.7/0.35)** — whether low-confidence reviews should be allowed to move the adjustment at all.
12. **Research-first reranking** — currently researches 50, reranks, caps at 15. Worth measuring how often research actually changes the top 15 vs. the pure-delta baseline.

---

*Last updated from source on 2026-04-12.*
