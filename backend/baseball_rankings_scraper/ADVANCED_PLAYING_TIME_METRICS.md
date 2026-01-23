# 🎯 Advanced Playing Time Opportunity Metrics

## Overview

This document outlines sophisticated methods to calculate playing time opportunity WITHOUT roster data, using:
- **Player Stats**: exit_velo, sixty_time, position velocity, physical attributes
- **ML Predictions**: D1/P4 probabilities, confidence levels, elite flags
- **School Rankings**: team strength, offensive/defensive ratings, trends

---

## 📊 Available Data

### Player Data (from ML Pipeline)
```python
# Common to all positions:
- height, weight
- exit_velo_max (hitting power)
- sixty_time (speed/athleticism)
- primary_position
- hitting_handedness, throwing_hand
- region

# Position-specific:
- inf_velo (infielders) - defensive arm strength
- of_velo (outfielders) - defensive arm strength
- c_velo (catchers) - defensive arm strength
- pop_time (catchers) - catching skill
```

### ML Prediction Data
```python
- d1_probability (0.0 to 1.0)
- p4_probability (0.0 to 1.0, if D1)
- d1_prediction (True/False)
- p4_prediction (True/False)
- confidence ("High", "Medium", "Low")
- is_elite (True/False for P4 players)
- final_prediction ("Power 4 D1", "Non-P4 D1", "Non-D1")
```

### School Rankings Data
```python
- overall_rating (Massey rating - LOWER IS BETTER, e.g., 1.0 = #1 team, 300.0 = #300 team)
- division_percentile (0-100, within division - HIGHER IS BETTER, calculated from rating)
- offensive_rating, defensive_rating (LOWER IS BETTER)
- win_percentage (0.0-1.0, higher is better)
- trend ("improving", "stable", "declining")
- record (e.g., "42-15")
```

---

## 🚀 Method 1: Player-School Talent Fit Score (Recommended)

**Concept**: Compare player's predicted level against school's actual level

### Algorithm

```python
def calculate_talent_fit_score(player_predictions, school_strength):
    """
    Returns score from 0.5 (way overmatched) to 1.5 (way overqualified)
    1.0 = perfect fit
    """

    # Step 1: Quantify player's predicted level (0-100 scale)
    player_level = calculate_player_level(player_predictions)

    # Step 2: Quantify school's actual level (0-100 scale)
    school_level = school_strength['division_percentile']

    # Step 3: Calculate mismatch
    talent_gap = player_level - school_level

    # Step 4: Convert to playing time factor
    if talent_gap > 30:
        # Player WAY above school level - immediate starter
        return 1.5
    elif talent_gap > 15:
        # Player above school level - likely starter
        return 1.3
    elif talent_gap > -5:
        # Good fit - competitive for playing time
        return 1.0
    elif talent_gap > -20:
        # Player below school level - developmental
        return 0.8
    else:
        # Player way below school level - bench/redshirt
        return 0.5
```

### Player Level Calculation

```python
def calculate_player_level(predictions):
    """
    Convert ML predictions to 0-100 player level scale
    """
    d1_prob = predictions.d1_probability
    p4_prob = predictions.p4_probability if predictions.p4_results else 0
    is_elite = predictions.p4_results.is_elite if predictions.p4_results else False

    # Base level from D1 probability
    if is_elite:
        # Elite P4 players: 90-100
        base_level = 90 + (p4_prob * 10)
    elif p4_prob > 0:
        # P4 players: 75-90
        base_level = 75 + (p4_prob * 15)
    elif d1_prob > 0.5:
        # Non-P4 D1 players: 50-75
        base_level = 50 + (d1_prob * 25)
    else:
        # Non-D1 players: 0-50
        base_level = d1_prob * 50

    # Adjust for confidence
    confidence_adjustment = {
        "High": 1.0,
        "Medium": 0.95,
        "Low": 0.90
    }
    confidence = predictions.d1_results.confidence
    adjusted_level = base_level * confidence_adjustment.get(confidence, 1.0)

    return min(100, max(0, adjusted_level))
```

### Example Outputs

| Player Type | Player Level | School Percentile | Talent Gap | Score | Interpretation |
|-------------|--------------|-------------------|------------|-------|----------------|
| Elite P4 (95%) | 95 | 50 | +45 | 1.5 | Immediate impact starter |
| Borderline P4 (78%) | 78 | 85 | -7 | 0.95 | Competitive for playing time |
| Non-P4 D1 (65%) | 65 | 90 | -25 | 0.7 | Bench/developmental player |
| Non-D1 (35%) | 35 | 60 | -25 | 0.7 | Likely redshirt candidate |

---

## 🎯 Method 2: Stats-Based Performance Index

**Concept**: Compare player's physical tools against division benchmarks

### Algorithm

```python
def calculate_stats_based_factor(player_stats, school_division_group, position):
    """
    Compare player's raw stats to division benchmarks
    Returns multiplier: 0.6 (below average) to 1.4 (well above average)
    """

    # Division benchmarks (approximate)
    benchmarks = {
        "Power 4 D1": {
            "exit_velo_min": 95,
            "sixty_max": 6.9,
            "inf_velo_min": 85,
            "of_velo_min": 88
        },
        "Non-P4 D1": {
            "exit_velo_min": 90,
            "sixty_max": 7.1,
            "inf_velo_min": 82,
            "of_velo_min": 85
        },
        "Non-D1": {
            "exit_velo_min": 85,
            "sixty_max": 7.3,
            "inf_velo_min": 78,
            "of_velo_min": 82
        }
    }

    benchmark = benchmarks[school_division_group]
    scores = []

    # Score exit velocity (power)
    if player_stats['exit_velo_max'] >= benchmark['exit_velo_min'] + 5:
        scores.append(1.3)  # Well above
    elif player_stats['exit_velo_max'] >= benchmark['exit_velo_min']:
        scores.append(1.0)  # At benchmark
    else:
        scores.append(0.7)  # Below

    # Score speed (sixty time - lower is better)
    if player_stats['sixty_time'] <= benchmark['sixty_max'] - 0.2:
        scores.append(1.3)  # Much faster
    elif player_stats['sixty_time'] <= benchmark['sixty_max']:
        scores.append(1.0)  # At benchmark
    else:
        scores.append(0.7)  # Slower

    # Score position velocity
    velo_key = f"{position.lower()[0:2]}_velo"  # inf_velo, of_velo, c_velo
    if velo_key in player_stats:
        velo_benchmark = benchmark[f"{velo_key}_min"]
        if player_stats[velo_key] >= velo_benchmark + 3:
            scores.append(1.3)
        elif player_stats[velo_key] >= velo_benchmark:
            scores.append(1.0)
        else:
            scores.append(0.7)

    # Average all scores
    return sum(scores) / len(scores)
```

### Advantages
- ✅ Directly measures player tools vs division standards
- ✅ Independent of ML model predictions
- ✅ Easy to explain to users ("Your exit velo is 5 mph above P4 average")

### Disadvantages
- ❌ Benchmarks need manual calibration
- ❌ Doesn't account for intangibles (baseball IQ, work ethic)

---

## 📈 Method 3: Confidence-Weighted Opportunity Score

**Concept**: Use ML prediction confidence to adjust playing time estimates

### Algorithm

```python
def calculate_confidence_weighted_score(predictions, base_factor):
    """
    Adjust base playing time factor based on prediction confidence
    High confidence = more certainty in playing time
    Low confidence = more variability/opportunity
    """

    confidence = predictions.d1_results.confidence
    d1_prob = predictions.d1_probability

    # Base multipliers
    confidence_multipliers = {
        "High": {
            # High confidence predictions are more certain
            "above_threshold": 1.0,    # You belong here
            "below_threshold": 0.8     # You don't belong here
        },
        "Medium": {
            # Medium confidence = more opportunity to prove yourself
            "above_threshold": 1.1,    # Probably belong
            "below_threshold": 0.9     # Might work out
        },
        "Low": {
            # Low confidence = wide open competition
            "above_threshold": 1.2,    # Uncertainty creates opportunity
            "below_threshold": 1.0     # Uncertainty creates opportunity
        }
    }

    # Determine if player is above/below predicted level
    final_prediction = predictions.get_final_prediction()
    threshold_status = "above_threshold" if d1_prob > 0.6 else "below_threshold"

    multiplier = confidence_multipliers[confidence][threshold_status]

    return base_factor * multiplier
```

### Rationale
- **High confidence, high probability** → Player clearly belongs → Normal opportunity
- **Low confidence, borderline probability** → Uncertainty → More opportunity to prove yourself
- **High confidence, low probability** → Player doesn't fit → Limited opportunity

---

## 🔥 Method 4: Offensive vs Defensive Team Need (Advanced)

**Concept**: Schools with weak offense need hitters; schools with weak defense need defenders

### Algorithm

```python
def calculate_positional_need_factor(player_stats, school_rankings, position):
    """
    Adjust playing time based on team's offensive/defensive strength
    Returns multiplier: 0.9 to 1.3
    """

    offensive_rating = school_rankings['offensive_rating']
    defensive_rating = school_rankings['defensive_rating']

    # Determine if school is offense or defense-oriented
    # Note: LOWER rating = BETTER, so higher rating = weaker
    is_offense_weak = offensive_rating > defensive_rating + 2.0  # Higher = worse offense
    is_defense_weak = defensive_rating > offensive_rating + 2.0  # Higher = worse defense

    # Determine if player is offense or defense-oriented
    exit_velo = player_stats['exit_velo_max']
    position_velo = player_stats.get('inf_velo') or player_stats.get('of_velo') or 0

    is_power_hitter = exit_velo > 95  # Strong offensive player
    is_strong_defender = position_velo > 85  # Strong defensive player

    # Matching logic
    if is_offense_weak and is_power_hitter:
        return 1.3  # Team needs offense, you provide it
    elif is_defense_weak and is_strong_defender:
        return 1.2  # Team needs defense, you provide it
    elif is_offense_weak and not is_power_hitter:
        return 0.9  # Team needs offense, you don't provide it
    elif is_defense_weak and not is_strong_defender:
        return 0.9  # Team needs defense, you don't provide it
    else:
        return 1.0  # Balanced team, balanced player
```

### Example
- **Stanford**: Offensive rating = 12.5, Defensive rating = 18.2 → Offense is stronger (lower = better)
  - Defense is relatively weaker, so they need defensive help
- **Power hitter with 98 mph exit velo** → 1.0x multiplier (offense already strong)
- **Gold glove defender with 90 mph arm** → 1.2x multiplier (fills defensive need)

---

## 🎭 Method 5: Program Trajectory Adjustment

**Concept**: Improving programs create more opportunities; declining programs lose players

### Algorithm

```python
def calculate_trajectory_factor(school_strength):
    """
    Adjust playing time based on program trend
    Improving programs = roster turnover = opportunity
    Declining programs = talent exodus = opportunity
    """

    trend = school_strength['trend_analysis']['trend']
    change = school_strength['trend_analysis'].get('change', 0)
    # Note: change is (last_rating - first_rating)
    # Negative change = improving (rating decreased/got better)
    # Positive change = declining (rating increased/got worse)

    if trend == "improving" and change < -5.0:
        # Rapidly improving - large negative change (rating dropped a lot)
        return 1.2  # Coaching upgrade = more playing time competition
    elif trend == "improving":
        # Steady improvement - moderate negative change
        return 1.1  # Stable upward trajectory
    elif trend == "declining" and change > 5.0:
        # Rapidly declining - large positive change (rating increased a lot)
        return 1.3  # Lots of roster spots opening up
    elif trend == "declining":
        # Steady decline - moderate positive change
        return 1.2  # Some roster turnover
    else:
        # Stable program
        return 1.0  # Normal turnover
```

### Rationale
- **Improving programs**: Better coaching, better recruits → More competition
- **Declining programs**: Players transfer out → More open roster spots
- **Stable programs**: Normal roster turnover

---

## 🏆 Method 6: Composite Playing Time Index (RECOMMENDED)

**Concept**: Combine multiple methods for most accurate estimate

### Algorithm

```python
def calculate_composite_playing_time_index(
    player_predictions,
    player_stats,
    school_strength,
    position
):
    """
    Combine multiple methods with weighted average
    Returns final score: 0.5 (minimal opportunity) to 1.5 (maximum opportunity)
    """

    # Method 1: Talent Fit (40% weight) - Most important
    talent_fit = calculate_talent_fit_score(player_predictions, school_strength)

    # Method 2: Stats-Based (25% weight) - Objective measurement
    stats_factor = calculate_stats_based_factor(
        player_stats,
        school_strength['division_group'],
        position
    )

    # Method 3: Confidence-Weighted (15% weight) - Prediction uncertainty
    confidence_factor = calculate_confidence_weighted_score(
        player_predictions,
        1.0  # Base factor
    )

    # Method 4: Positional Need (10% weight) - Team weakness
    need_factor = calculate_positional_need_factor(
        player_stats,
        school_strength,
        position
    )

    # Method 5: Program Trajectory (10% weight) - Roster turnover
    trajectory_factor = calculate_trajectory_factor(school_strength)

    # Weighted average
    composite_score = (
        talent_fit * 0.40 +
        stats_factor * 0.25 +
        confidence_factor * 0.15 +
        need_factor * 0.10 +
        trajectory_factor * 0.10
    )

    # Ensure bounds
    return max(0.5, min(1.5, composite_score))
```

### Score Interpretation

| Score | Category | Playing Time Expectation |
|-------|----------|-------------------------|
| 1.4-1.5 | Elite Fit | Immediate starter, star player |
| 1.2-1.4 | Excellent Fit | Likely starter by sophomore year |
| 1.0-1.2 | Good Fit | Competitive for playing time |
| 0.8-1.0 | Average Fit | Depth player, special situations |
| 0.6-0.8 | Below Average | Bench/developmental player |
| 0.5-0.6 | Poor Fit | Limited opportunity, may transfer |

---

## 🎨 Method 7: Percentile-Based Playing Time Probability

**Concept**: Convert playing time factor to probability of significant playing time

### Algorithm

```python
def calculate_playing_time_probability(composite_score):
    """
    Convert composite score to probability of getting significant playing time
    Returns: {
        "starter_probability": 0.0-1.0,
        "rotation_player_probability": 0.0-1.0,
        "bench_probability": 0.0-1.0,
        "expected_role": str
    }
    """

    # Map composite score to probabilities using sigmoid-like curves
    if composite_score >= 1.3:
        return {
            "starter_probability": 0.85,
            "rotation_player_probability": 0.13,
            "bench_probability": 0.02,
            "expected_role": "Likely starter by sophomore year",
            "at_bats_per_season": "150-250+",
            "innings_per_game": "7+"
        }
    elif composite_score >= 1.1:
        return {
            "starter_probability": 0.60,
            "rotation_player_probability": 0.30,
            "bench_probability": 0.10,
            "expected_role": "Competitive for starting role",
            "at_bats_per_season": "100-200",
            "innings_per_game": "5-7"
        }
    elif composite_score >= 0.9:
        return {
            "starter_probability": 0.30,
            "rotation_player_probability": 0.50,
            "bench_probability": 0.20,
            "expected_role": "Rotation player, situational starter",
            "at_bats_per_season": "50-150",
            "innings_per_game": "3-5"
        }
    elif composite_score >= 0.7:
        return {
            "starter_probability": 0.10,
            "rotation_player_probability": 0.40,
            "bench_probability": 0.50,
            "expected_role": "Bench player, development focus",
            "at_bats_per_season": "20-75",
            "innings_per_game": "1-3"
        }
    else:
        return {
            "starter_probability": 0.02,
            "rotation_player_probability": 0.18,
            "bench_probability": 0.80,
            "expected_role": "Limited opportunity, may redshirt",
            "at_bats_per_season": "0-30",
            "innings_per_game": "0-1"
        }
```

---

## 📊 Comparison: Current vs Proposed Methods

| Method | Current | Talent Fit | Stats-Based | Composite |
|--------|---------|------------|-------------|-----------|
| Uses player stats | ❌ | ✅ | ✅ | ✅ |
| Uses ML predictions | ❌ | ✅ | ❌ | ✅ |
| Position-specific | ❌ | ❌ | ✅ | ✅ |
| Team needs | ❌ | ❌ | ❌ | ✅ |
| Program trajectory | ❌ | ❌ | ❌ | ✅ |
| Personalized | ❌ | ✅ | ✅ | ✅ |
| Explainable | ✅ | ✅ | ✅ | ⚠️ |
| Accuracy | Low | High | Medium | Very High |

---

## 🚀 Implementation Recommendation

### Phase 1: Quick Win (Week 1)
Implement **Method 1: Talent Fit Score**
- Easy to implement
- Uses existing data
- Highly explainable to users
- Big improvement over current method

### Phase 2: Enhanced (Week 2-3)
Add **Method 2: Stats-Based Performance Index**
- Validates ML predictions with hard stats
- Provides concrete feedback ("Your exit velo is above average")

### Phase 3: Production (Month 2)
Implement **Method 6: Composite Index**
- Combines all methods
- Most accurate predictions
- Production-ready

### Phase 4: User Experience (Month 3)
Add **Method 7: Probability Distribution**
- Convert to user-friendly probabilities
- Show expected role and playing time
- Great for frontend visualization

---

## 💡 Key Advantages Over Current Method

1. **Personalized**: Uses individual player stats and predictions
2. **Dynamic**: Adjusts based on player's predicted level vs school's actual level
3. **Multi-dimensional**: Considers talent, stats, confidence, team needs, trends
4. **Actionable**: Tells player "why" they have more/less opportunity
5. **Accurate**: Uses actual performance data, not just team strength

---

## 🎯 Example User Experience

**Current System**:
> "Stanford has a playing time factor of 0.7 (elite program, very competitive)"

**Proposed System**:
> "Based on your profile:
> - Your predicted level: 78 (Non-P4 D1)
> - Stanford's level: 92 (Elite P4)
> - **Playing time opportunity: 0.65** (Below average fit)
>
> **Analysis**:
> - Your exit velocity (91 mph) is below Stanford's average (96 mph)
> - Your sixty time (7.0) meets their standard
> - Stanford's roster is extremely competitive at your position
> - **Expected role**: Bench/developmental player (10% chance to start)
> - **Recommendation**: Consider schools in the 60-80 percentile range for better playing time"

Much more valuable than a simple number!
