# Playing Time Calculator

A sophisticated algorithm for calculating playing time opportunity scores for baseball recruits. This system combines player statistics, ML predictions, and school program data to produce a z-score-based assessment of how likely a player is to earn playing time at a specific school.

## Overview

The Playing Time Calculator answers the question: **"How likely is this player to earn playing time at this school?"**

Unlike simple division-based factors (e.g., "P4 programs are competitive"), this algorithm:
- Compares player stats to **division-specific benchmarks**
- Considers **player strengths** (dynamically weighted)
- Factors in **team needs** (offense vs defense)
- Accounts for **program trajectory** (improving vs declining)
- Uses **ML predictions** as a cross-division sanity check

## Quick Start

```python
from backend.playing_time import (
    PlayingTimeCalculator,
    PlayerStats,
    MLPredictions,
    SchoolData,
)

# Create input objects
player = PlayerStats(
    exit_velo=94.0,
    sixty_time=6.85,
    inf_velo=86.0,
    height=72,
    weight=185,
    primary_position="SS"
)

ml = MLPredictions(
    d1_probability=0.78,
    p4_probability=0.35,
    is_elite=False
)

school = SchoolData(
    school_name="Example University",
    division=1,
    is_power_4=False,
    division_percentile=55.0,
    offensive_rating=45.0,
    defensive_rating=52.0,  # Higher = weaker, so defense is weaker
    trend="stable"
)

# Calculate
calculator = PlayingTimeCalculator()
result = calculator.calculate(player, ml, school)

# Access results
print(f"Z-Score: {result.final_z_score:.2f}")
print(f"Percentile: {result.percentile:.1f}%")
print(f"Bucket: {result.bucket}")
print(f"Interpretation: {result.interpretation}")

# Get full breakdown
print(result.to_dict())
```

## Algorithm Overview

### Step-by-Step Process

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Calculate Stat Z-Scores                                 │
│   • exit_velo, sixty_time, position_velo                        │
│   • Compare to school's division benchmarks                      │
│   • Catchers: 60/40 weighted average of c_velo and pop_time     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Rank and Weight Stats                                   │
│   • Sort by z-score (best → mid → worst)                        │
│   • Apply weights: 30% best, 25% mid, 20% worst                 │
│   • Identify player's primary strength                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Height/Weight Component (15%)                           │
│   • Average of height and weight z-scores                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: ML Component (10%)                                      │
│   • Map player's ML prediction to 0-100 level                   │
│   • Map school to 0-100 level                                   │
│   • Calculate gap, scale to ~±0.2 contribution                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Team Needs Bonus (0 to +0.20)                           │
│   • Determine team weakness (offense/defense)                   │
│   • Check if player strength aligns                             │
│   • Scale bonus based on player's z-score in that area          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Trend Bonus                                             │
│   • Declining: +0.12 (more roster opportunity)                  │
│   • Improving: -0.08 (more competition)                         │
│   • Stable: 0                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Final Z-Score                                           │
│   = stats_component + physical_component + ml_component         │
│     + team_needs_bonus + trend_bonus                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Bucket Assignment                                       │
│   • Convert z-score to percentile                               │
│   • Assign to playing time category                             │
└─────────────────────────────────────────────────────────────────┘
```

### Component Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Best Stat | 30% | Player's strongest tool (highest z-score) |
| Mid Stat | 25% | Player's second-best tool |
| Worst Stat | 20% | Player's weakest tool (floor) |
| Physical | 15% | Height/weight profile |
| ML Prediction | 10% | Cross-division sanity check |

**Total: 100%**

Plus additive bonuses:
- Team Needs Alignment: +0.05 to +0.20
- Program Trend: -0.08 to +0.12

## Playing Time Buckets

| Z-Score | Bucket | Percentile | Interpretation |
|---------|--------|------------|----------------|
| ≥ 1.5 | Likely Starter | Top 7% | Would stand out immediately |
| ≥ 1.0 | Compete for Time | Top 16% | Strong chance to earn spot |
| ≥ 0.5 | Developmental | Top 31% | Will need to improve |
| ≥ 0.0 | Roster Fit | Top 50% | Could make team, limited PT |
| ≥ -0.5 | Stretch | Top 69% | Would need significant development |
| < -0.5 | Reach | Bottom 31% | Significant gap to close |

## Key Design Decisions

### 1. Dynamic Stat Weighting

Instead of fixed weights per stat (e.g., "exit_velo is always 40%"), we rank the player's stats and weight by rank:

- **Best stat gets 30%** — Rewards player's primary strength
- **Mid stat gets 25%** — Values versatility
- **Worst stat gets 20%** — Ensures floor matters

This means a power hitter's exit_velo gets 30% weight, while a speedster's sixty_time gets 30% weight.

### 2. Catcher Defensive Calculation

Catchers have two defensive metrics: `c_velo` (arm strength) and `pop_time` (quick release).

We use a **60/40 weighted average** favoring the higher z-score:

```python
z_pos = (0.60 × max(z_c_velo, z_pop_time)) + (0.40 × min(z_c_velo, z_pop_time))
```

This rewards catchers who excel in one area while still penalizing major weaknesses.

### 3. Scaled Team Needs Bonus

The alignment bonus isn't flat — it scales with how good the player is at what the team needs:

```
z = 0.5 (minimum) → bonus = 0.05
z = 1.0           → bonus = 0.10
z = 1.5           → bonus = 0.15
z = 2.0+          → bonus = 0.20 (capped)
```

A barely-above-average player gets a small nudge. An elite player in exactly what the team needs gets a significant boost.

### 4. ML as Sanity Check (10%)

The ML component serves as a cross-division normalizer, not a primary driver. Due to ML model probability concentration (typically 0.35-0.70 range), the practical contribution is ~±0.05.

This is intentional — stats (75% weight) should drive differentiation, with ML providing context.

### 5. Z-Score Output

The final output is a **true z-score**, not an arbitrary scale. This enables:
- Statistical interpretation (percentiles)
- Cross-school comparison
- Future probabilistic modeling
- Easy bucket assignment

## Configuration

All "magic numbers" are defined in `constants.py` with full documentation:

```python
# Stat weights
STAT_WEIGHT_BEST = 0.30
STAT_WEIGHT_MID = 0.25
STAT_WEIGHT_WORST = 0.20
STAT_WEIGHT_PHYSICAL = 0.15
STAT_WEIGHT_ML = 0.10

# Alignment bonus scaling
MIN_Z_FOR_ALIGNMENT_BONUS = 0.5
MIN_ALIGNMENT_BONUS = 0.05
MAX_ALIGNMENT_BONUS = 0.20
ALIGNMENT_BONUS_SCALE = 0.10

# Trend bonuses
TREND_BONUS_DECLINING = 0.12
TREND_BONUS_IMPROVING = -0.08
```

### Division Benchmarks

The benchmark values in `constants.py` are calculated from real player data (19,512 players across divisions):

| Division | Players | Exit Velo Mean | 60-Time Mean | Inf Velo Mean |
|----------|---------|----------------|--------------|---------------|
| P4 | 2,603 | 95.4 mph | 7.02s | 84.7 mph |
| Non-P4 D1 | 5,630 | 93.4 mph | 7.10s | 82.9 mph |
| D2 | 4,176 | 91.0 mph | 7.25s | 80.1 mph |
| D3 | 7,103 | 88.7 mph | 7.35s | 77.7 mph |

Benchmarks include outlier filtering (reasonable bounds) to prevent data entry errors from skewing calculations. See `backend/data/division_benchmarks.ipynb` for the full calculation methodology.

## Output Structure

### Full Result

```python
{
    "final_z_score": 1.18,
    "percentile": 88.1,
    "bucket": "Compete for Time",
    "bucket_description": "Top 16% - strong chance to earn spot",
    "breakdown": {
        "stats": {
            "best": {"stat_name": "inf_velo", "z_score": 1.80, "weight": 0.30},
            "mid": {"stat_name": "sixty_time", "z_score": 1.10, "weight": 0.25},
            "worst": {"stat_name": "exit_velo", "z_score": 0.60, "weight": 0.20},
            "component_total": 1.075,
            "player_strength": "defensive"
        },
        "physical": {
            "height_z": 0.5,
            "weight_z": 0.3,
            "component_total": 0.06
        },
        "ml": {
            "predicted_level": 62,
            "school_level": 55,
            "gap": 7,
            "component_total": 0.014
        },
        "team_fit": {
            "team_needs": "defense",
            "player_strength": "defensive",
            "alignment": true,
            "bonus": 0.15
        },
        "trend": {
            "trend": "declining",
            "bonus": 0.12
        }
    },
    "context": {
        "school_name": "Example University",
        "school_division": "Non-P4 D1",
        "player_position": "SS"
    },
    "interpretation": "Your stats put you in the top 12% for Non-P4 D1. Your Inf Velo is a standout tool (top 7%). This team needs defensive help, and that's your strength. The program is in a rebuilding phase, creating more roster opportunity. Assessment: Compete for Time."
}
```

### Summary Result

```python
result.to_summary_dict()
# {
#     "final_z_score": 1.18,
#     "percentile": 88.1,
#     "bucket": "Compete for Time",
#     "interpretation": "Your stats put you in the top 12%..."
# }
```

## Integration

The playing time calculator is fully integrated with the school filtering pipeline and API.

### Data Mappers

The `mappers.py` module provides conversion functions between pipeline types and playing time types:

```python
from backend.playing_time import create_playing_time_inputs

# Convert pipeline data to playing time calculator inputs
player_stats, ml_predictions, school_context = create_playing_time_inputs(
    player=ml_results.player,        # PlayerInfielder/PlayerOutfielder/PlayerCatcher
    ml_results=ml_results,           # MLPipelineResults
    school_data=school_data,         # Dict from database
    baseball_strength=baseball_strength,  # Optional Dict from rankings
)

# Calculate playing time
result = calculator.calculate(player_stats, ml_predictions, school_context)
```

Available mapper functions:
- `player_type_to_stats()` - Converts PlayerType to PlayerStats
- `ml_results_to_predictions()` - Converts MLPipelineResults to MLPredictions
- `school_data_to_context()` - Converts school dict + baseball rankings to SchoolData
- `create_playing_time_inputs()` - All-in-one convenience function

### Pipeline Integration

Playing time is automatically calculated in `async_two_tier_pipeline.py`:

```python
# In AsyncTwoTierFilteringPipeline._create_school_match()
async def _create_school_match(self, school_data, preferences, ml_results):
    school_match = SchoolMatch(...)

    # Score preferences
    await self._score_nice_to_haves(school_match, preferences)

    # Enrich with baseball rankings
    await self._enrich_with_baseball_rankings(school_match)

    # Calculate playing time
    await self._calculate_playing_time(school_match, ml_results)

    return school_match
```

### API Response

The `/preferences/filter` endpoint includes playing time in each school's response:

```json
{
    "school_name": "Example University",
    "playing_time": {
        "available": true,
        "z_score": 1.18,
        "percentile": 88.1,
        "bucket": "Compete for Time",
        "bucket_description": "Top 16% - strong chance to earn spot",
        "interpretation": "Your stats put you in the top 12%...",
        "breakdown": {
            "stats_component": 1.075,
            "physical_component": 0.06,
            "ml_component": 0.014,
            "team_fit_bonus": 0.15,
            "trend_bonus": 0.12
        },
        "player_strength": "defensive",
        "team_needs": "defense",
        "program_trend": "declining"
    }
}
```

The API requires `player_info` in the request for playing time calculation. See `GET /preferences/example` for the full request format.

## File Structure

```
backend/playing_time/
├── __init__.py                 # Clean exports
├── README.md                   # This documentation
├── constants.py                # All configurable values with rationale
├── types.py                    # Input/output data structures
├── playing_time_calculator.py  # Main algorithm implementation
└── mappers.py                  # Data conversion for pipeline integration
```

## Future Enhancements

### TODO: Position-Specific Height/Weight Z-Scores

Currently, height/weight uses division-wide benchmarks. A future enhancement could use position-specific benchmarks (e.g., 1B vs SS have different ideal heights).

### TODO: Roster Depth Integration

If roster data becomes available, factor in:
- Graduating seniors at player's position
- Existing recruits at player's position
- Transfer portal activity

### TODO: Conference-Specific Benchmarks

Some conferences within the same division have different talent levels. Could add conference-level benchmarks for finer differentiation.

## Troubleshooting

### Z-scores seem too high/low

The benchmarks in `constants.py` are calculated from real data with outlier filtering. If your sample players consistently produce extreme z-scores, check that:
- Player stats are in expected ranges (exit_velo in mph, sixty_time in seconds)
- The correct division group is being passed (P4, Non-P4 D1, D2, D3)

### Missing stats cause issues

Missing stats are handled gracefully — they use the division average (z-score = 0), resulting in no positive or negative impact.

### Team needs always "balanced"

Ensure `offensive_rating` and `defensive_rating` are being passed from the baseball rankings data. If both are `None`, the calculator defaults to balanced. Check that the school has baseball rankings data available.

### Playing time not appearing in API response

Ensure `player_info` is included in the API request. The playing time calculation requires player stats. Check the logs for any calculation errors.

## References

- [Z-Score Wikipedia](https://en.wikipedia.org/wiki/Standard_score)
- [Normal Distribution CDF](https://en.wikipedia.org/wiki/Normal_distribution#Cumulative_distribution_function)
- Massey Ratings interpretation: Lower rating = better team
