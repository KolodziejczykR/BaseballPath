"""
Playing Time Calculator Constants

This file contains all configurable constants, thresholds, and benchmark data
for the playing time calculation algorithm. All "magic numbers" are documented
with their rationale for easy future adjustment.

IMPORTANT: When updating these values, update the corresponding documentation
in README.md to keep everything in sync.
"""

from typing import Dict, Any


# =============================================================================
# STAT WEIGHTS
# =============================================================================
# These weights determine how much each component contributes to the final z-score.
# Total: 30 + 25 + 20 + 15 + 10 = 100%
#
# Rationale:
# - Stats are dynamically ranked (best/mid/worst), so a player's strength
#   is always weighted highest regardless of which stat it is
# - Height/weight provides physical profile context
# - ML is a sanity check, not a primary driver (10% keeps it modest)

STAT_WEIGHT_BEST = 0.30      # Weight for player's best stat (highest z-score)
STAT_WEIGHT_MID = 0.25       # Weight for player's middle stat
STAT_WEIGHT_WORST = 0.20     # Weight for player's weakest stat
STAT_WEIGHT_PHYSICAL = 0.15  # Weight for height/weight combined
STAT_WEIGHT_ML = 0.10        # Weight for ML prediction alignment

# Verify weights sum to 1.0
_TOTAL_WEIGHT = (
    STAT_WEIGHT_BEST + STAT_WEIGHT_MID + STAT_WEIGHT_WORST +
    STAT_WEIGHT_PHYSICAL + STAT_WEIGHT_ML
)
assert abs(_TOTAL_WEIGHT - 1.0) < 0.001, f"Stat weights must sum to 1.0, got {_TOTAL_WEIGHT}"


# =============================================================================
# CATCHER DEFENSIVE WEIGHTS
# =============================================================================
# Catchers have two defensive stats (c_velo and pop_time).
# We use a 60/40 weighted average favoring the higher z-score.
#
# Rationale:
# - Rewards catchers who excel in one area (arm strength OR quick release)
# - Still penalizes major weaknesses (40% weight on lower stat)
# - Reflects that elite catchers often have one standout defensive tool

CATCHER_HIGHER_STAT_WEIGHT = 0.60  # Weight for catcher's better defensive stat
CATCHER_LOWER_STAT_WEIGHT = 0.40   # Weight for catcher's weaker defensive stat


# =============================================================================
# ML COMPONENT SCALING
# =============================================================================
# The ML component compares predicted_level (0-100) vs school_level (0-100).
# We scale the gap to contribute approximately ±0.2 to the final z-score.
#
# Formula: ml_component = (ml_gap / ML_GAP_DIVISOR) * STAT_WEIGHT_ML
#
# With ML_GAP_DIVISOR = 50:
# - Maximum gap of 100 → 100/50 = 2.0 → 2.0 * 0.10 = ±0.20
# - Typical gap of 25 → 25/50 = 0.5 → 0.5 * 0.10 = ±0.05
#
# NOTE: Due to ML model probability concentration (typically 0.35-0.70 range),
# the practical contribution is smaller (~±0.05). This is acceptable as
# stats (75% weight) provide primary differentiation. See README for details.

ML_GAP_DIVISOR = 50  # Normalizes 0-100 gap to ~±2 range before weight applied


# =============================================================================
# TEAM NEEDS ALIGNMENT BONUS
# =============================================================================
# When a player's strength aligns with a team's weakness, they receive a bonus.
# The bonus scales linearly based on how strong the player's aligned stat is.
#
# Formula: bonus = MIN_ALIGNMENT_BONUS + (best_z - MIN_Z_FOR_BONUS) * ALIGNMENT_SCALE
#
# Example scaling:
# - z = 0.5 (minimum) → 0.05 + (0.5 - 0.5) * 0.10 = 0.05
# - z = 1.0           → 0.05 + (1.0 - 0.5) * 0.10 = 0.10
# - z = 1.5           → 0.05 + (1.5 - 0.5) * 0.10 = 0.15
# - z = 2.0+          → 0.05 + (2.0 - 0.5) * 0.10 = 0.20 (capped)
#
# Rationale:
# - A barely-above-average player (z=0.5) in what the team needs gets a small nudge
# - An elite player (z=2.0) in exactly what the team needs gets significant boost
# - Capped at 0.20 to prevent team fit from overshadowing actual ability

MIN_Z_FOR_ALIGNMENT_BONUS = 0.5  # Minimum z-score to qualify for alignment bonus
MIN_ALIGNMENT_BONUS = 0.05       # Bonus at z = 0.5
MAX_ALIGNMENT_BONUS = 0.20       # Maximum bonus (cap)
ALIGNMENT_BONUS_SCALE = 0.10     # How much bonus increases per 1.0 z-score above minimum


# =============================================================================
# TEAM NEEDS DETECTION THRESHOLD
# =============================================================================
# We determine team needs by comparing offensive_rating vs defensive_rating.
# In Massey ratings, LOWER = BETTER.
#
# If offensive_rating > defensive_rating + threshold → offense is WEAKER
# If defensive_rating > offensive_rating + threshold → defense is WEAKER
#
# Threshold prevents marking balanced teams as having a "need"

TEAM_NEEDS_RATING_THRESHOLD = 3.0  # Minimum gap to declare a team need


# =============================================================================
# TREND BONUSES
# =============================================================================
# Program trend (improving/stable/declining) affects roster opportunity.
#
# Declining programs:
# - Players transfer out, top recruits avoid the program
# - More roster spots become available
# - Positive bonus for playing time opportunity
#
# Improving programs:
# - Better players coming in, program gaining prestige
# - More competition for roster spots
# - Negative adjustment (harder to earn playing time)

TREND_BONUS_DECLINING = 0.12    # Bonus for declining programs (more opportunity)
TREND_BONUS_IMPROVING = -0.08   # Penalty for improving programs (more competition)
TREND_BONUS_STABLE = 0.0        # No adjustment for stable programs


# =============================================================================
# PLAYER LEVEL MAPPING (ML Predictions → 0-100 Scale)
# =============================================================================
# Maps ML prediction outputs to a universal 0-100 "player level" scale.
# This allows comparison across divisions.
#
# Scale design:
# - Elite P4 players: 88-100
# - Standard P4 players: 70-90
# - High Non-P4 D1: 55-75
# - Mid Non-P4 D1: 45-62
# - Low D1 / High D2: 32-48
# - D2 Level: 18-35
# - D3 Level: 5-22
#
# Note: Ranges overlap intentionally to model reality (top D2 > bottom D1)

PLAYER_LEVEL_ELITE_P4_BASE = 88
PLAYER_LEVEL_ELITE_P4_RANGE = 12      # 88 + (p4_prob * 12) = 88-100

PLAYER_LEVEL_P4_BASE = 70
PLAYER_LEVEL_P4_RANGE = 20            # 70 + (p4_prob * 20) = 70-90

PLAYER_LEVEL_HIGH_D1_BASE = 55
PLAYER_LEVEL_HIGH_D1_RANGE = 20       # 55 + (d1_prob * 20) = 55-75

PLAYER_LEVEL_MID_D1_BASE = 45
PLAYER_LEVEL_MID_D1_RANGE = 17        # 45 + (d1_prob * 17) = 45-62

PLAYER_LEVEL_LOW_D1_BASE = 32
PLAYER_LEVEL_LOW_D1_RANGE = 16        # 32 + (d1_prob * 16) = 32-48

PLAYER_LEVEL_D2_SCALE = 50            # d1_prob * 50 = 0-50 for sub-D1 players


# =============================================================================
# SCHOOL LEVEL MAPPING (Division + Percentile → 0-100 Scale)
# =============================================================================
# Maps school's division and within-division percentile to a universal 0-100 scale.
# This allows cross-division comparisons.
#
# Scale design (bands overlap to model reality):
# - P4: 70-100 (30-point band)
# - Non-P4 D1: 45-75 (30-point band)
# - D2: 25-55 (30-point band)
# - D3: 10-40 (30-point band)
# - NAIA: 0-25 (25-point band)
#
# Formula: school_level = BAND_FLOOR + (percentile/100) * BAND_WIDTH

SCHOOL_LEVEL_BANDS: Dict[str, Dict[str, float]] = {
    "P4": {
        "floor": 70.0,
        "width": 30.0,  # 70 + (percentile * 0.30) = 70-100
    },
    "Non-P4 D1": {
        "floor": 45.0,
        "width": 30.0,  # 45 + (percentile * 0.30) = 45-75
    },
    "D2": {
        "floor": 25.0,
        "width": 30.0,  # 25 + (percentile * 0.30) = 25-55
    },
    "D3": {
        "floor": 10.0,
        "width": 30.0,  # 10 + (percentile * 0.30) = 10-40
    },
    "NAIA": {
        "floor": 0.0,
        "width": 25.0,  # 0 + (percentile * 0.25) = 0-25
    },
    "JUCO": {
        "floor": 0.0,
        "width": 25.0,  # Same as NAIA
    },
}


# =============================================================================
# PLAYING TIME BUCKETS
# =============================================================================
# Maps final z-score to human-readable playing time likelihood categories.
# These thresholds can be adjusted based on empirical results.
#
# Z-score interpretation (standard normal distribution):
# - z >= 1.5 → top ~7% of recruits for this level
# - z >= 1.0 → top ~16%
# - z >= 0.5 → top ~31%
# - z >= 0.0 → top ~50%
# - z >= -0.5 → top ~69%
# - z < -0.5 → bottom ~31%

PLAYING_TIME_BUCKETS = [
    # (min_z, bucket_name, description)
    (1.5, "Likely Starter", "Top 7% - would stand out immediately"),
    (1.0, "Compete for Time", "Top 16% - strong chance to earn spot"),
    (0.5, "Developmental", "Top 31% - will need to improve to earn time"),
    (0.0, "Roster Fit", "Average fit - could make team, limited PT"),
    (-0.5, "Stretch", "Below average - would need significant development"),
    (float('-inf'), "Reach", "Bottom 31% - significant gap to close"),
]


# =============================================================================
# DIVISION BENCHMARKS (PLACEHOLDER)
# =============================================================================
# These benchmark values (mean and std for each stat per division) should be
# calculated from your actual player data. The values below are PLACEHOLDERS.
#
# TODO: Replace with actual calculated benchmarks from your dataset.
#
# Structure:
# DIVISION_BENCHMARKS[division_group][stat_name] = {"mean": float, "std": float}
#
# Stats tracked:
# - exit_velo: Exit velocity (mph) - higher is better
# - sixty_time: 60-yard dash time (seconds) - lower is better
# - inf_velo: Infielder throw velocity (mph) - higher is better
# - of_velo: Outfielder throw velocity (mph) - higher is better
# - c_velo: Catcher throw velocity (mph) - higher is better
# - pop_time: Catcher pop time (seconds) - lower is better
# - height: Height (inches) - context dependent
# - weight: Weight (lbs) - context dependent

DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 96.0, "std": 4.0},
        "sixty_time": {"mean": 6.75, "std": 0.18},
        "inf_velo": {"mean": 87.0, "std": 3.5},
        "of_velo": {"mean": 90.0, "std": 3.5},
        "c_velo": {"mean": 83.0, "std": 3.0},
        "pop_time": {"mean": 1.95, "std": 0.07},
        "height": {"mean": 73.0, "std": 2.5},
        "weight": {"mean": 195.0, "std": 18.0},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 92.0, "std": 4.5},
        "sixty_time": {"mean": 7.0, "std": 0.20},
        "inf_velo": {"mean": 83.0, "std": 3.5},
        "of_velo": {"mean": 86.0, "std": 3.5},
        "c_velo": {"mean": 80.0, "std": 3.0},
        "pop_time": {"mean": 2.02, "std": 0.08},
        "height": {"mean": 72.0, "std": 2.5},
        "weight": {"mean": 185.0, "std": 17.0},
    },
    "D2": {
        "exit_velo": {"mean": 88.0, "std": 5.0},
        "sixty_time": {"mean": 7.15, "std": 0.22},
        "inf_velo": {"mean": 80.0, "std": 3.5},
        "of_velo": {"mean": 83.0, "std": 3.5},
        "c_velo": {"mean": 77.0, "std": 3.0},
        "pop_time": {"mean": 2.08, "std": 0.09},
        "height": {"mean": 71.5, "std": 2.5},
        "weight": {"mean": 180.0, "std": 16.0},
    },
    "D3": {
        "exit_velo": {"mean": 84.0, "std": 5.5},
        "sixty_time": {"mean": 7.30, "std": 0.25},
        "inf_velo": {"mean": 77.0, "std": 3.5},
        "of_velo": {"mean": 80.0, "std": 3.5},
        "c_velo": {"mean": 74.0, "std": 3.0},
        "pop_time": {"mean": 2.15, "std": 0.10},
        "height": {"mean": 71.0, "std": 2.5},
        "weight": {"mean": 175.0, "std": 15.0},
    },
    "NAIA": {
        "exit_velo": {"mean": 82.0, "std": 6.0},
        "sixty_time": {"mean": 7.40, "std": 0.28},
        "inf_velo": {"mean": 75.0, "std": 3.5},
        "of_velo": {"mean": 78.0, "std": 3.5},
        "c_velo": {"mean": 72.0, "std": 3.0},
        "pop_time": {"mean": 2.20, "std": 0.11},
        "height": {"mean": 70.5, "std": 2.5},
        "weight": {"mean": 172.0, "std": 15.0},
    },
    "JUCO": {
        "exit_velo": {"mean": 82.0, "std": 6.0},
        "sixty_time": {"mean": 7.40, "std": 0.28},
        "inf_velo": {"mean": 75.0, "std": 3.5},
        "of_velo": {"mean": 78.0, "std": 3.5},
        "c_velo": {"mean": 72.0, "std": 3.0},
        "pop_time": {"mean": 2.20, "std": 0.11},
        "height": {"mean": 70.5, "std": 2.5},
        "weight": {"mean": 172.0, "std": 15.0},
    },
}


# =============================================================================
# STAT CLASSIFICATION
# =============================================================================
# Maps stat names to their category (offensive, defensive, speed).
# Used for determining player strength and team needs alignment.

OFFENSIVE_STATS = ["exit_velo"]
DEFENSIVE_STATS = ["inf_velo", "of_velo", "c_velo", "pop_time"]
SPEED_STATS = ["sixty_time"]

# Map stat name to player strength category
STAT_TO_STRENGTH: Dict[str, str] = {
    "exit_velo": "offensive",
    "sixty_time": "speed",
    "inf_velo": "defensive",
    "of_velo": "defensive",
    "c_velo": "defensive",
    "pop_time": "defensive",
}


# =============================================================================
# INVERTED STATS
# =============================================================================
# Some stats are "lower is better" and need their z-scores inverted.
# - sixty_time: Lower time = faster = better
# - pop_time: Lower time = quicker release = better

INVERTED_STATS = ["sixty_time", "pop_time"]
