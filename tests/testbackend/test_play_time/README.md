# Playing Time Calculator Test Suite

Comprehensive unit tests for the `backend.playing_time` module, covering normal data flow and edge cases that could break the calculator.

## Running Tests

```bash
cd code
python3 -m pytest tests/testbackend/test_play_time/ -v
```

## Test Structure

```
test_play_time/
├── conftest.py                      # 18 shared fixtures
├── test_playing_time_normal.py      # Happy path tests
├── test_playing_time_edge_cases.py  # Edge cases / breaking tests
└── README.md                        # This file
```

## Why This Suite is Extensive

This test suite validates the playing time calculator from multiple angles:

1. **Data Flow Coverage** - Tests each step of the algorithm (z-score calculation → ranking → weighting → bonuses → bucketing)
2. **Position-Specific Logic** - Validates different code paths for catchers, infielders, and outfielders
3. **Boundary Conditions** - Tests exact threshold values where behavior changes
4. **Failure Modes** - Ensures graceful handling of missing data, invalid inputs, and edge cases
5. **Component Isolation** - Verifies each weighted component (stats 75%, physical 15%, ML 10%) independently
6. **Mathematical Correctness** - Validates z-score to percentile conversion against known values

---

## Normal Data Flow Tests (`test_playing_time_normal.py`)

### TestNormalDataFlow

| # | Test Name | What It Validates |
|---|-----------|-------------------|
| 1 | `test_average_player_at_matching_school_produces_near_zero_z_score` | A player with stats at division mean should get z ≈ 0. Validates baseline behavior. |
| 2 | `test_elite_player_at_lower_division_produces_high_positive_z_score` | Elite P4 player at D2 school should dominate (z ≥ 1.0, "Likely Starter" or "Compete for Time"). |
| 3 | `test_below_average_player_at_higher_division_produces_negative_z_score` | D2-level player at P4 school should struggle (z < 0, "Stretch" or "Reach" bucket). |
| 4 | `test_catcher_uses_60_40_defensive_weighting` | Catchers combine c_velo and pop_time with 60% weight on higher z-score. |
| 5 | `test_outfielder_uses_of_velo_path` | Outfielders (OF, LF, CF, RF) use of_velo instead of inf_velo. |
| 6 | `test_team_needs_alignment_bonus_offense` | Offensive player (high exit_velo) gets bonus when school needs offense. |
| 7 | `test_team_needs_alignment_bonus_defense` | Defensive player (high inf_velo) gets bonus when school needs defense. |
| 8 | `test_declining_program_gives_trend_bonus` | Declining programs give +0.12 bonus (more roster opportunity). |
| 9 | `test_improving_program_gives_trend_penalty` | Improving programs give -0.08 penalty (more competition). |
| 10 | `test_output_structure_contains_all_required_fields` | PlayingTimeResult has all required fields and serializes to dict correctly. |

### TestComponentCalculations

| # | Test Name | What It Validates |
|---|-----------|-------------------|
| 11 | `test_stat_weights_sum_correctly` | Weights are 30% best + 25% mid + 20% worst = 75% stats component. |
| 12 | `test_physical_component_is_15_percent_of_average_z` | Physical = 15% × average(height_z, weight_z). |
| 13 | `test_ml_component_is_10_percent_of_scaled_gap` | ML = 10% × (player_level - school_level) / 50. |
| 14 | `test_z_to_percentile_conversion` | z=0→50%, z=1→84.13%, z=-1→15.87% (standard normal CDF). |

---

## Edge Case Tests (`test_playing_time_edge_cases.py`)

### TestEdgeCases

| # | Test Name | What It Breaks/Tests |
|---|-----------|----------------------|
| 1 | `test_all_stats_missing_produces_zero_z_scores` | All stats None → uses division average, z = 0 for each. No crash. |
| 2 | `test_partially_missing_stats_handled_correctly` | Mix of provided/missing stats. Missing stats get z = 0, provided stats calculated normally. |
| 3 | `test_extreme_stat_values_dont_cause_overflow` | Exit velo 120 mph, 60-time 5.0s → no NaN, no infinity, valid bucket assignment. |
| 4 | `test_invalid_division_group_falls_back_to_default` | Division = 99 → falls back to Non-P4 D1 benchmarks. |
| 5 | `test_missing_team_ratings_results_in_balanced_need` | Both offensive_rating and defensive_rating None → TeamNeed.BALANCED, no bonus. |
| 6 | `test_catcher_with_only_c_velo_no_pop_time` | Catcher with c_velo but no pop_time → 60/40 weighting still works (one z = 0). |
| 7 | `test_zero_std_benchmark_doesnt_cause_division_by_zero` | Custom benchmarks with std = 0 → z = 0 instead of division error. |
| 8 | `test_low_z_score_below_alignment_threshold_gets_no_bonus` | Best stat z < 0.5 → no alignment bonus even if strength matches team need. |
| 9 | `test_z_score_exactly_at_bucket_threshold` | z = 1.0 exactly → "Compete for Time" (tests >= boundary condition). |
| 10 | `test_unknown_position_defaults_to_infielder` | Position "DH" → defaults to inf_velo path. |

### TestMLEdgeCases

| # | Test Name | What It Breaks/Tests |
|---|-----------|----------------------|
| 11 | `test_ml_probability_at_boundaries` | d1_prob = 0.0 and 1.0 → valid player levels, no crash. |
| 12 | `test_p4_probability_none_handled` | p4_probability explicitly None → treated as 0, no crash. |

### TestSchoolLevelEdgeCases

| # | Test Name | What It Breaks/Tests |
|---|-----------|----------------------|
| 13 | `test_school_percentile_at_extremes` | Percentile 0% → floor (45 for Non-P4 D1), 100% → ceiling (75). |
| 14 | `test_trend_string_case_insensitive` | "DECLINING", "Improving" → case-insensitive matching. |

---

## Fixtures (`conftest.py`)

### Player Fixtures
- `average_infielder_stats` - Stats at Non-P4 D1 mean
- `elite_infielder_stats` - Stats 1-2σ above P4 mean
- `below_average_player` - Stats below D3 mean
- `elite_catcher_stats` - Excellent arm and pop time
- `outfielder_stats` - Solid OF with 90 mph arm

### ML Prediction Fixtures
- `high_d1_ml_predictions` - d1_prob=0.78, p4_prob=0.25
- `elite_p4_ml_predictions` - d1_prob=0.95, p4_prob=0.85, is_elite=True
- `low_d1_ml_predictions` - d1_prob=0.45 (borderline)
- `d2_level_ml_predictions` - d1_prob=0.25

### School Fixtures
- `non_p4_d1_school` - Mid-tier Non-P4 D1, balanced
- `p4_school` - Mid-tier P4
- `top_p4_school` - Elite P4 (95th percentile)
- `d2_school` - Mid-tier D2
- `d3_school` - Mid-tier D3
- `school_needs_offense` - High offensive rating (weak offense)
- `school_needs_defense` - High defensive rating (weak defense)
- `declining_program` - trend="declining"
- `improving_program` - trend="improving"

---

## Coverage Summary

| Category | Tests | Coverage |
|----------|-------|----------|
| Normal data flow | 10 | Core algorithm validation |
| Component calculations | 4 | Weight/formula verification |
| Missing data handling | 3 | None values, partial data |
| Boundary conditions | 3 | Exact thresholds, extremes |
| Position-specific logic | 3 | Catcher, OF, unknown position |
| Team needs/bonuses | 4 | Alignment, trends |
| ML component | 2 | Probability boundaries |
| School level | 2 | Percentile extremes, case handling |
| **Total** | **28** | |

All tests pass in < 0.3 seconds.
