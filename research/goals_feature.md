# Feature Spec: Goals Tracking & Improvement System

## Overview

Goals Tracking is an ML-driven improvement system that shows players which stats have the most leverage on their D1/P4 probability, how they compare to target-level ranges, and what to work on next. It uses sensitivity analysis (re-running the existing ML pipeline with perturbed inputs) and gap-to-range percentile comparisons computed from training data.

## User Stories

1. **As a player**, I want to know which stat improvement would most increase my D1 probability so I can focus my training.
2. **As a player**, I want to see how my stats compare to D1-level players at my position so I know where I stand.
3. **As a player**, I want to log progress on my stats over time and see how my predicted probability changes.
4. **As a player**, I want to set a target level (D1 or Power 4 D1) and get personalized improvement recommendations.
5. **As a player**, I want to create goals directly from an evaluation run so I don't have to re-enter my stats.

## Access Control

- **Pro and Elite tiers**: Full access to goals, sensitivity analysis, and gap-to-range.
- **Starter tier**: Show a preview/teaser with upgrade CTA.
- Future tier differentiation (not built yet):
  - **Elite**: Proactive AI-driven goal setting (AI identifies what to work on)
  - **Pro**: Suggestions shown, user manually logs updates; ML model verifies probability boost

## Statistical Viability

### Training Data Sizes (Verified)
| Position | D1 Dataset | P4 Dataset |
|----------|-----------|-----------|
| Infielders | 12,446 | 3,393 |
| Outfielders | 8,568 | 2,321 |
| Catchers | 5,270 | 1,257 |
| Pitchers | 18,343 | — |

### Methodology Assessment
| Method | Verdict |
|--------|---------|
| **Model sensitivity** (perturb inputs, re-run model) | Use this — requires 0 additional data |
| **Gap-to-range percentiles** (25th/75th per level) | Use this — 1,257-18,343 per group is sufficient |
| **Hard causal claims** ("+4 mph = +11% D1") | Too risky — defer to future version |

### Chosen Approach: Hybrid with Responsible Framing
- **Always show**: Model sensitivity + Gap-to-range comparisons
- **Frame as**: "Based on our model..." and "Players at this level typically..." — NOT "If you improve X, you WILL..."
- **Defer**: Hard +/- claims only after model calibration validation in a future version

## How Sensitivity Analysis Works

For each player, the system:

1. Takes current stats → runs `pipeline.predict()` → records base D1 probability and P4 probability (if applicable)
2. For each modifiable stat:
   - Increments by small steps (direction-aware: higher-is-better goes up, lower-is-better goes down)
   - Re-runs `pipeline.predict()` for each perturbed input
   - Records probability delta at each step
3. Ranks stats by marginal impact per unit change
4. Returns the ranked list with deltas

### Performance
- Each `pipeline.predict()` call: ~10-50ms (in-memory model inference, no I/O)
- Full sensitivity scan: 3-9 stats x 4 steps = 12-36 calls
- Total time: ~120ms-1.8s
- Results cached in JSONB; recomputed on stat update

### Infrastructure Reuse
The sensitivity service directly reuses:
- `InfielderPredictionPipeline.predict()` from `backend/ml/pipeline/infielder_pipeline.py`
- `OutfielderPredictionPipeline.predict()` from `backend/ml/pipeline/outfielder_pipeline.py`
- `CatcherPredictionPipeline.predict()` from `backend/ml/pipeline/catcher_pipeline.py`
- `PitcherPredictionPipeline.predict()` from `backend/ml/pipeline/pitcher_pipeline.py`
- `PlayerInfielder`, `PlayerOutfielder`, `PlayerCatcher`, `PlayerPitcher` from `backend/utils/player_types.py`
- `MLPipelineResults` from `backend/utils/prediction_types.py`

No model changes needed — pure re-inference with modified inputs.

## Perturbable Stats Configuration

### Infielder
| Stat | Display Name | Unit | Direction | Steps |
|------|-------------|------|-----------|-------|
| exit_velo_max | Exit Velocity | mph | +1 (higher better) | [1, 2, 3, 5] |
| inf_velo | Infield Velocity | mph | +1 | [1, 2, 3, 5] |
| sixty_time | 60-Yard Dash | sec | -1 (lower better) | [0.05, 0.1, 0.2, 0.3] |

### Outfielder
| Stat | Display Name | Unit | Direction | Steps |
|------|-------------|------|-----------|-------|
| exit_velo_max | Exit Velocity | mph | +1 | [1, 2, 3, 5] |
| of_velo | Outfield Velocity | mph | +1 | [1, 2, 3, 5] |
| sixty_time | 60-Yard Dash | sec | -1 | [0.05, 0.1, 0.2, 0.3] |

### Catcher
| Stat | Display Name | Unit | Direction | Steps |
|------|-------------|------|-----------|-------|
| exit_velo_max | Exit Velocity | mph | +1 | [1, 2, 3, 5] |
| c_velo | Catcher Velocity | mph | +1 | [1, 2, 3, 5] |
| pop_time | Pop Time | sec | -1 | [0.02, 0.05, 0.1, 0.15] |
| sixty_time | 60-Yard Dash | sec | -1 | [0.05, 0.1, 0.2, 0.3] |

### Pitcher
| Stat | Display Name | Unit | Direction | Steps |
|------|-------------|------|-----------|-------|
| fastball_velo_max | Fastball Max | mph | +1 | [1, 2, 3, 5] |
| fastball_velo_range | Fastball Avg | mph | +1 | [1, 2, 3, 5] |
| fastball_spin | Fastball Spin | rpm | +1 | [50, 100, 150, 200] |
| changeup_velo | Changeup Velo | mph | +1 | [1, 2, 3] |
| curveball_velo | Curveball Velo | mph | +1 | [1, 2, 3] |
| slider_velo | Slider Velo | mph | +1 | [1, 2, 3] |

## Gap-to-Range Comparison

### Data Source
Computed from training CSVs:
- `backend/data/hitters/inf_feat_eng.csv` (12,446 rows)
- `backend/data/hitters/of_feat_eng_d1_or_not.csv` (8,568 rows)
- `backend/data/hitters/c_d1_or_not_data.csv` (5,270 rows)
- `backend/data/pitchers/pitchers_data_clean.csv` (18,343 rows)

### Computed Percentiles
For each (position, level, stat) combination:
- p10, p25, median, p75, p90
- mean, std_dev, sample_count

### Levels
- "D1", "Non-D1" (from D1 classifier labels)
- "Power 4 D1", "Non-P4 D1" (from P4 classifier labels, hitters only)

### Visualization
Horizontal bar per stat showing:
- Shaded band: 25th-75th percentile range for target level
- Whisker lines: 10th and 90th percentile
- Player marker: current stat value positioned on the scale
- Color coding: green if within/above 25th-75th, orange if below

## UX Copy & Framing

### Leverage Rankings
> "Based on our model's analysis of {sample_count} verified {position} players, improving your {stat_name} is your highest-leverage opportunity."
>
> "{stat_name}: {current} → {target} ({direction} {delta} {unit})"
> "Model probability: {base_prob}% → {new_prob}% ({change})"

### Gap-to-Range
> "D1 {position}s in our dataset typically have {stat_name} between {p25} and {p75} {unit}. You are at {current} {unit}."

### Disclaimer (shown on EVERY sensitivity/goals view)
> "Model estimates are based on patterns in historical player data. They reflect statistical tendencies, not guarantees. Many factors beyond metrics — including academics, character, coaching relationships, and timing — affect recruiting outcomes. Use these insights as one tool in your development plan."

## Database Schema

### Table: `player_goals`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → profiles(id) | CASCADE delete |
| position_track | TEXT NOT NULL | "pitcher", "infielder", "outfielder", "catcher" |
| target_level | TEXT DEFAULT 'D1' | "D1" or "Power 4 D1" |
| current_stats | JSONB NOT NULL | Stats snapshot when goals created |
| target_stats | JSONB | User-adjustable targets (or auto from ranges) |
| sensitivity_results | JSONB | Cached sensitivity analysis output |
| sensitivity_computed_at | TIMESTAMPTZ | When cache was last computed |
| is_active | BOOLEAN DEFAULT true | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | Auto via trigger |

### Table: `stat_progress_entries`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| goal_id | UUID FK → player_goals(id) | CASCADE delete |
| user_id | UUID FK → profiles(id) | CASCADE delete |
| stat_name | TEXT NOT NULL | e.g., "exit_velo_max" |
| stat_value | FLOAT NOT NULL | |
| source | TEXT DEFAULT 'manual' | "manual", "evaluation", "verified" |
| evaluation_run_id | UUID FK → prediction_runs(id) | SET NULL on delete |
| recorded_at | TIMESTAMPTZ | |

### Table: `position_stat_ranges` (Reference Data)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| position_track | TEXT NOT NULL | |
| level | TEXT NOT NULL | "D1", "Non-D1", "Power 4 D1", "Non-P4 D1" |
| stat_name | TEXT NOT NULL | |
| p10 | FLOAT | |
| p25 | FLOAT | |
| median | FLOAT | |
| p75 | FLOAT | |
| p90 | FLOAT | |
| mean | FLOAT | |
| std_dev | FLOAT | |
| sample_count | INT | |
| data_version | TEXT | Version tag for recomputation |
| computed_at | TIMESTAMPTZ | |
| UNIQUE | | (position_track, level, stat_name, data_version) |

### RLS Policies
- Users manage own `player_goals` and `stat_progress_entries` (SELECT/INSERT/UPDATE/DELETE where `auth.uid() = user_id`)
- All authenticated users can SELECT from `position_stat_ranges` (read-only reference data)

## API Endpoints

### Goals CRUD (`/goals`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/goals` | Create goal set (from eval or manual stats) |
| GET | `/goals` | List active goals for the user |
| GET | `/goals/{goal_id}` | Full goal detail + sensitivity + gap-to-range |
| PATCH | `/goals/{goal_id}` | Update target level, target stats |
| POST | `/goals/{goal_id}/progress` | Log new stat value |
| GET | `/goals/{goal_id}/sensitivity` | Get/refresh sensitivity analysis (cached 24h) |
| GET | `/goals/{goal_id}/gap-to-range` | Compare stats to target level ranges |
| GET | `/goals/ranges/{position}/{level}` | Get percentile ranges for position/level |

### Sensitivity Service

**File**: `backend/api/services/sensitivity_service.py`

Core function signature:
```python
def compute_sensitivity(
    position_track: str,      # "infielder", "outfielder", "catcher", "pitcher"
    current_stats: dict,      # Player's current stats
    target_level: str,        # "D1" or "Power 4 D1"
    identity_fields: dict,    # height, weight, position, region, handedness
) -> dict:
    # Returns ranked list of stats with probability deltas at each step
```

Cache invalidation: any stat update on the goal clears `sensitivity_results` and `sensitivity_computed_at`.

### Stat Ranges Script

**File**: `backend/scripts/compute_stat_ranges.py`

One-time (re-runnable) script that:
1. Reads training CSVs
2. Groups by (position, level)
3. Computes p10/p25/median/p75/p90/mean/std for each stat
4. Upserts into `position_stat_ranges` table with a `data_version` tag

## Frontend Pages

### `/goals` — Goals Overview (Authenticated)
- List of active goal sets as summary cards
- Each card: position, target level, current D1 probability, top leverage stat, last updated
- CTA: "Set Up Goals" (if none) or "Add New Goal Set"

### `/goals/[goalId]` — Goal Detail (Authenticated)
Three tab/section layout:
1. **Leverage Rankings**: Ordered list of stats by impact (biggest delta first)
2. **Gap-to-Range**: Visual comparison per stat with percentile bands
3. **Progress**: Timeline of stat updates + probability trajectory chart

### `/goals/create` — New Goal Set (Authenticated)
- Step 1: Select position (or auto-detect from profile)
- Step 2: Enter current stats OR import from latest evaluation
- Step 3: Select target level (D1 or Power 4 D1)
- Step 4: Preview initial sensitivity analysis
- Step 5: Confirm and save

## Frontend Components

| Component | File | Purpose |
|-----------|------|---------|
| LeverageRankCard | `leverage-rank-card.tsx` | Stat card with name, current value, probability delta bar, color-coded by impact |
| GapToRangeChart | `gap-to-range-chart.tsx` | Horizontal bar per stat with 25th-75th band, user marker, 10th/90th whiskers |
| SensitivitySummary | `sensitivity-summary.tsx` | Top-3 biggest levers with headline framing |
| ProgressTimeline | `progress-timeline.tsx` | Line chart of probability over time as stats update |
| StatUpdateForm | `stat-update-form.tsx` | Form to log new stat values (per-stat inputs) |
| UpdateNudgeCards | `update-nudge-cards.tsx` | "What to update next" suggestions |
| DisclaimerBanner | `disclaimer-banner.tsx` | Standard disclaimer shown on all sensitivity views |

## Nav Integration

Add to `navItems` array in `frontend/src/components/ui/authenticated-topbar.tsx`:
```typescript
{ href: "/goals", label: "Goals" },
```

Add "Goals & Improvement" section on dashboard with top leverage stat preview.

## Cross-Feature: Dashboard Integration

Update `frontend/src/app/dashboard/page.tsx` to add:

1. **Player Card Preview**: Small card thumbnail + "Share Your Card" CTA (or "Create Card" if none)
2. **Goals Snapshot**: Top leverage stat + current probability + "View Goals" CTA (or "Set Goals" if none)

## Evaluation Detail Integration

Add to `frontend/src/app/evaluations/[runId]/page.tsx`:
- "Create Card from This Evaluation" button
- "Set Goals from This Evaluation" button

These buttons pre-populate the respective creation flows with data from the evaluation run.
