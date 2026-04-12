"""
Playing Time Calculator Constants

This file contains all configurable constants, thresholds, and benchmark data
for the playing time calculation algorithm. All "magic numbers" are documented
with their rationale for easy future adjustment.

IMPORTANT: When updating these values, update the corresponding documentation
in README.md to keep everything in sync.
"""

from typing import Dict


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
    }
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
# DIVISION BENCHMARKS
# =============================================================================
# Calculated from all_hitter_data.csv with outlier filtering.
# See backend/data/division_benchmarks.ipynb for calculation methodology.
#
# Data sources:
# - P4: 2,603 players from Power 4 conferences
# - Non-P4 D1: 5,630 players from non-Power 4 D1 conferences
# - Mid-Major D1: 3,571 players from mapped mid-major conferences
# - Low-Major D1: 2,059 players from mapped low-major conferences
# - D2: 4,176 players from Division 2
# - D3: 7,103 players from Division 3
#
# Position-specific stats (inf_velo, of_velo, c_velo, pop_time) are calculated
# only from players whose primary_position matches that position type.
#
# Structure:
# DIVISION_BENCHMARKS[division_group][stat_name] = {"mean": float, "std": float}
#
# Stats tracked:
# - exit_velo: Exit velocity max (mph) - higher is better
# - sixty_time: 60-yard dash time (seconds) - lower is better
# - inf_velo: Infielder throw velocity (mph) - higher is better
# - of_velo: Outfielder throw velocity (mph) - higher is better
# - c_velo: Catcher throw velocity (mph) - higher is better
# - pop_time: Catcher pop time (seconds) - lower is better
# - height: Height (inches) - context dependent
# - weight: Weight (lbs) - context dependent

DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 95.4, "std": 5.97},
        "sixty_time": {"mean": 7.02, "std": 0.34},
        "inf_velo": {"mean": 84.66, "std": 5.29},
        "of_velo": {"mean": 86.94, "std": 5.57},
        "c_velo": {"mean": 79.02, "std": 3.9},
        "pop_time": {"mean": 1.99, "std": 0.1},
        "height": {"mean": 72.65, "std": 2.25},
        "weight": {"mean": 187.32, "std": 19.04},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 93.4, "std": 5.58},
        "sixty_time": {"mean": 7.1, "std": 0.34},
        "inf_velo": {"mean": 82.94, "std": 5.01},
        "of_velo": {"mean": 85.53, "std": 4.94},
        "c_velo": {"mean": 77.54, "std": 3.87},
        "pop_time": {"mean": 2.0, "std": 0.1},
        "height": {"mean": 72.11, "std": 2.22},
        "weight": {"mean": 182.71, "std": 18.66},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 93.72, "std": 5.65},
        "sixty_time": {"mean": 7.1, "std": 0.34},
        "inf_velo": {"mean": 83.16, "std": 5.02},
        "of_velo": {"mean": 86.03, "std": 4.72},
        "c_velo": {"mean": 77.78, "std": 3.94},
        "pop_time": {"mean": 2.0, "std": 0.1},
        "height": {"mean": 72.24, "std": 2.19},
        "weight": {"mean": 183.27, "std": 18.48},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 92.89, "std": 5.44},
        "sixty_time": {"mean": 7.11, "std": 0.35},
        "inf_velo": {"mean": 82.59, "std": 4.98},
        "of_velo": {"mean": 84.7, "std": 5.18},
        "c_velo": {"mean": 77.15, "std": 3.74},
        "pop_time": {"mean": 2.01, "std": 0.1},
        "height": {"mean": 71.88, "std": 2.26},
        "weight": {"mean": 181.72, "std": 18.93},
    },
    "D2": {
        "exit_velo": {"mean": 91.0, "std": 5.44},
        "sixty_time": {"mean": 7.25, "std": 0.35},
        "inf_velo": {"mean": 80.07, "std": 5.08},
        "of_velo": {"mean": 82.83, "std": 4.97},
        "c_velo": {"mean": 75.44, "std": 3.58},
        "pop_time": {"mean": 2.06, "std": 0.11},
        "height": {"mean": 71.52, "std": 2.3},
        "weight": {"mean": 179.35, "std": 19.98},
    },
    "D3": {
        "exit_velo": {"mean": 88.65, "std": 5.77},
        "sixty_time": {"mean": 7.35, "std": 0.39},
        "inf_velo": {"mean": 77.67, "std": 5.19},
        "of_velo": {"mean": 80.56, "std": 5.2},
        "c_velo": {"mean": 73.72, "std": 3.74},
        "pop_time": {"mean": 2.11, "std": 0.12},
        "height": {"mean": 71.12, "std": 2.33},
        "weight": {"mean": 175.38, "std": 20.56},
    },
}

PITCHER_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "height": {"mean": 74.40, "std": 2.19},
        "weight": {"mean": 192.69, "std": 19.50},
        "FastballVelo Range": {"mean": 88.39, "std": 3.62},
        "FastballVelocity (max)": {"mean": 90.47, "std": 3.63},
        "FastballSpin Rate (avg)": {"mean": 2187.07, "std": 194.27},
        "Changeup Velo Range": {"mean": 79.49, "std": 4.27},
        "Changeup Spin Rate (avg)": {"mean": 1764.20, "std": 265.67},
        "Curveball Velo Range": {"mean": 74.22, "std": 4.14},
        "Curveball Spin Rate (avg)": {"mean": 2221.73, "std": 307.94},
        "Slider Velo Range": {"mean": 77.27, "std": 4.17},
        "Slider Spin Rate (avg)": {"mean": 2267.83, "std": 295.67},
    },
    "Non-P4 D1": {
        "height": {"mean": 73.69, "std": 2.24},
        "weight": {"mean": 187.89, "std": 19.33},
        "FastballVelo Range": {"mean": 85.92, "std": 3.40},
        "FastballVelocity (max)": {"mean": 87.88, "std": 3.39},
        "FastballSpin Rate (avg)": {"mean": 2137.07, "std": 177.43},
        "Changeup Velo Range": {"mean": 77.55, "std": 4.08},
        "Changeup Spin Rate (avg)": {"mean": 1710.87, "std": 262.72},
        "Curveball Velo Range": {"mean": 72.56, "std": 3.84},
        "Curveball Spin Rate (avg)": {"mean": 2149.25, "std": 281.01},
        "Slider Velo Range": {"mean": 75.09, "std": 4.00},
        "Slider Spin Rate (avg)": {"mean": 2191.69, "std": 277.93},
    },
    "Mid-Major D1": {
        "height": {"mean": 73.79, "std": 2.23},
        "weight": {"mean": 188.5, "std": 19.35},
        "FastballVelo Range": {"mean": 86.34, "std": 3.3},
        "FastballVelocity (max)": {"mean": 88.33, "std": 3.3},
        "FastballSpin Rate (avg)": {"mean": 2149.38, "std": 175.14},
        "Changeup Velo Range": {"mean": 77.88, "std": 4.02},
        "Changeup Spin Rate (avg)": {"mean": 1719.38, "std": 262.73},
        "Curveball Velo Range": {"mean": 72.89, "std": 3.77},
        "Curveball Spin Rate (avg)": {"mean": 2162.2, "std": 279.78},
        "Slider Velo Range": {"mean": 75.51, "std": 3.92},
        "Slider Spin Rate (avg)": {"mean": 2198.7, "std": 274.8},
    },
    "Low-Major D1": {
        "height": {"mean": 73.47, "std": 2.26},
        "weight": {"mean": 186.7, "std": 19.25},
        "FastballVelo Range": {"mean": 85.12, "std": 3.45},
        "FastballVelocity (max)": {"mean": 87.03, "std": 3.4},
        "FastballSpin Rate (avg)": {"mean": 2115.77, "std": 179.43},
        "Changeup Velo Range": {"mean": 76.92, "std": 4.13},
        "Changeup Spin Rate (avg)": {"mean": 1695.58, "std": 262.18},
        "Curveball Velo Range": {"mean": 71.94, "std": 3.88},
        "Curveball Spin Rate (avg)": {"mean": 2127.93, "std": 281.91},
        "Slider Velo Range": {"mean": 74.27, "std": 4.02},
        "Slider Spin Rate (avg)": {"mean": 2179.15, "std": 283.25},
    },
    "D2": {
        "height": {"mean": 73.10, "std": 2.33},
        "weight": {"mean": 183.80, "std": 20.86},
        "FastballVelo Range": {"mean": 82.72, "std": 3.70},
        "FastballVelocity (max)": {"mean": 84.53, "std": 3.75},
        "FastballSpin Rate (avg)": {"mean": 2048.72, "std": 188.77},
        "Changeup Velo Range": {"mean": 74.95, "std": 4.07},
        "Changeup Spin Rate (avg)": {"mean": 1650.76, "std": 257.34},
        "Curveball Velo Range": {"mean": 70.40, "std": 3.95},
        "Curveball Spin Rate (avg)": {"mean": 2061.99, "std": 278.57},
        "Slider Velo Range": {"mean": 72.58, "std": 3.89},
        "Slider Spin Rate (avg)": {"mean": 2112.39, "std": 260.86},
    },
    "D3": {
        "height": {"mean": 72.47, "std": 2.35},
        "weight": {"mean": 179.20, "std": 21.22},
        "FastballVelo Range": {"mean": 80.20, "std": 3.86},
        "FastballVelocity (max)": {"mean": 81.87, "std": 3.83},
        "FastballSpin Rate (avg)": {"mean": 1988.63, "std": 188.67},
        "Changeup Velo Range": {"mean": 72.99, "std": 4.00},
        "Changeup Spin Rate (avg)": {"mean": 1600.67, "std": 249.39},
        "Curveball Velo Range": {"mean": 68.44, "std": 4.04},
        "Curveball Spin Rate (avg)": {"mean": 1999.35, "std": 266.94},
        "Slider Velo Range": {"mean": 70.59, "std": 3.83},
        "Slider Spin Rate (avg)": {"mean": 2036.34, "std": 254.21},
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
    # Pitcher stats map to defensive strength
    "FastballVelo Range": "defensive",
    "FastballVelocity (max)": "defensive",
    "FastballSpin Rate (avg)": "defensive",
    "Changeup Velo Range": "defensive",
    "Changeup Spin Rate (avg)": "defensive",
    "Curveball Velo Range": "defensive",
    "Curveball Spin Rate (avg)": "defensive",
    "Slider Velo Range": "defensive",
    "Slider Spin Rate (avg)": "defensive",
}

# =============================================================================
# INVERTED STATS
# =============================================================================
# Some stats are "lower is better" and need their z-scores inverted.
# - sixty_time: Lower time = faster = better
# - pop_time: Lower time = quicker release = better

INVERTED_STATS = ["sixty_time", "pop_time"]


# =============================================================================
# POSITION-SPECIFIC DIVISION BENCHMARKS
# =============================================================================
# Calculated from all_hitter_data.csv filtered by position group.
# See backend/data/division_benchmarks.ipynb for calculation methodology.
#
# Position groups:
# - OF: OF, CF, RF, LF
# - MIF: SS, 2B, MIF (middle infielders)
# - CIF: 3B, 1B (corner infielders)
# - C: C (catchers)
#
# These provide more accurate benchmarks since physical profiles differ
# significantly by position (e.g., OF run faster 60s, CIF are bigger/stronger).

OF_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 96.06, "std": 5.90},
        "sixty_time": {"mean": 6.84, "std": 0.30},
        "height": {"mean": 72.70, "std": 2.25},
        "weight": {"mean": 186.34, "std": 17.79},
        "of_velo": {"mean": 86.94, "std": 5.57},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 93.76, "std": 5.58},
        "sixty_time": {"mean": 6.92, "std": 0.29},
        "height": {"mean": 72.17, "std": 2.23},
        "weight": {"mean": 180.94, "std": 16.62},
        "of_velo": {"mean": 85.53, "std": 4.94},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 94.00, "std": 5.77},
        "sixty_time": {"mean": 6.93, "std": 0.30},
        "height": {"mean": 72.32, "std": 2.18},
        "weight": {"mean": 181.74, "std": 16.53},
        "of_velo": {"mean": 86.03, "std": 4.72},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 93.36, "std": 5.23},
        "sixty_time": {"mean": 6.90, "std": 0.28},
        "height": {"mean": 71.90, "std": 2.30},
        "weight": {"mean": 179.53, "std": 16.69},
        "of_velo": {"mean": 84.70, "std": 5.18},
    },
    "D2": {
        "exit_velo": {"mean": 91.43, "std": 5.35},
        "sixty_time": {"mean": 7.06, "std": 0.31},
        "height": {"mean": 71.55, "std": 2.26},
        "weight": {"mean": 175.96, "std": 16.81},
        "of_velo": {"mean": 82.83, "std": 4.97},
    },
    "D3": {
        "exit_velo": {"mean": 89.24, "std": 5.51},
        "sixty_time": {"mean": 7.15, "std": 0.32},
        "height": {"mean": 71.13, "std": 2.23},
        "weight": {"mean": 171.70, "std": 16.86},
        "of_velo": {"mean": 80.56, "std": 5.20},
    },
}

MIF_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 94.20, "std": 6.00},
        "sixty_time": {"mean": 6.97, "std": 0.28},
        "height": {"mean": 72.16, "std": 2.13},
        "weight": {"mean": 178.67, "std": 15.37},
        "inf_velo": {"mean": 85.24, "std": 5.10},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 91.91, "std": 5.30},
        "sixty_time": {"mean": 7.05, "std": 0.29},
        "height": {"mean": 71.49, "std": 2.10},
        "weight": {"mean": 173.45, "std": 14.58},
        "inf_velo": {"mean": 83.45, "std": 4.86},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 92.30, "std": 5.33},
        "sixty_time": {"mean": 7.04, "std": 0.27},
        "height": {"mean": 71.61, "std": 2.11},
        "weight": {"mean": 173.83, "std": 14.65},
        "inf_velo": {"mean": 83.65, "std": 4.90},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 91.29, "std": 5.19},
        "sixty_time": {"mean": 7.07, "std": 0.30},
        "height": {"mean": 71.30, "std": 2.07},
        "weight": {"mean": 172.80, "std": 14.45},
        "inf_velo": {"mean": 83.14, "std": 4.77},
    },
    "D2": {
        "exit_velo": {"mean": 89.37, "std": 5.41},
        "sixty_time": {"mean": 7.16, "std": 0.30},
        "height": {"mean": 70.74, "std": 2.15},
        "weight": {"mean": 167.93, "std": 14.67},
        "inf_velo": {"mean": 80.54, "std": 5.00},
    },
    "D3": {
        "exit_velo": {"mean": 86.87, "std": 5.63},
        "sixty_time": {"mean": 7.29, "std": 0.34},
        "height": {"mean": 70.24, "std": 2.18},
        "weight": {"mean": 163.99, "std": 15.37},
        "inf_velo": {"mean": 78.20, "std": 5.16},
    },
}

CIF_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 96.95, "std": 6.02},
        "sixty_time": {"mean": 7.21, "std": 0.36},
        "height": {"mean": 74.08, "std": 1.93},
        "weight": {"mean": 203.22, "std": 19.48},
        "inf_velo": {"mean": 83.34, "std": 5.48},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 95.44, "std": 5.63},
        "sixty_time": {"mean": 7.30, "std": 0.33},
        "height": {"mean": 73.50, "std": 2.05},
        "weight": {"mean": 197.91, "std": 18.60},
        "inf_velo": {"mean": 81.83, "std": 5.17},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 95.59, "std": 5.82},
        "sixty_time": {"mean": 7.28, "std": 0.33},
        "height": {"mean": 73.64, "std": 2.00},
        "weight": {"mean": 197.60, "std": 18.07},
        "inf_velo": {"mean": 82.11, "std": 5.11},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 95.19, "std": 5.30},
        "sixty_time": {"mean": 7.32, "std": 0.33},
        "height": {"mean": 73.25, "std": 2.12},
        "weight": {"mean": 198.46, "std": 19.52},
        "inf_velo": {"mean": 81.38, "std": 5.23},
    },
    "D2": {
        "exit_velo": {"mean": 92.63, "std": 5.30},
        "sixty_time": {"mean": 7.42, "std": 0.34},
        "height": {"mean": 72.71, "std": 2.25},
        "weight": {"mean": 194.05, "std": 21.14},
        "inf_velo": {"mean": 79.41, "std": 5.13},
    },
    "D3": {
        "exit_velo": {"mean": 90.33, "std": 5.88},
        "sixty_time": {"mean": 7.54, "std": 0.39},
        "height": {"mean": 72.53, "std": 2.19},
        "weight": {"mean": 191.90, "std": 21.89},
        "inf_velo": {"mean": 76.91, "std": 5.13},
    },
}

C_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 95.45, "std": 5.46},
        "sixty_time": {"mean": 7.20, "std": 0.33},
        "height": {"mean": 72.24, "std": 2.14},
        "weight": {"mean": 192.15, "std": 16.35},
        "c_velo": {"mean": 79.02, "std": 3.90},
        "pop_time": {"mean": 1.99, "std": 0.10},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 93.75, "std": 5.37},
        "sixty_time": {"mean": 7.28, "std": 0.33},
        "height": {"mean": 71.96, "std": 2.04},
        "weight": {"mean": 188.85, "std": 17.49},
        "c_velo": {"mean": 77.54, "std": 3.87},
        "pop_time": {"mean": 2.00, "std": 0.10},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 94.14, "std": 5.28},
        "sixty_time": {"mean": 7.27, "std": 0.33},
        "height": {"mean": 72.09, "std": 1.95},
        "weight": {"mean": 190.17, "std": 17.22},
        "c_velo": {"mean": 77.78, "std": 3.94},
        "pop_time": {"mean": 2.00, "std": 0.10},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 93.11, "std": 5.46},
        "sixty_time": {"mean": 7.30, "std": 0.32},
        "height": {"mean": 71.74, "std": 2.16},
        "weight": {"mean": 186.66, "std": 17.72},
        "c_velo": {"mean": 77.15, "std": 3.74},
        "pop_time": {"mean": 2.01, "std": 0.10},
    },
    "D2": {
        "exit_velo": {"mean": 91.11, "std": 5.18},
        "sixty_time": {"mean": 7.40, "std": 0.34},
        "height": {"mean": 71.37, "std": 2.06},
        "weight": {"mean": 184.60, "std": 17.68},
        "c_velo": {"mean": 75.44, "std": 3.58},
        "pop_time": {"mean": 2.06, "std": 0.11},
    },
    "D3": {
        "exit_velo": {"mean": 88.75, "std": 5.52},
        "sixty_time": {"mean": 7.50, "std": 0.37},
        "height": {"mean": 70.99, "std": 2.15},
        "weight": {"mean": 179.91, "std": 18.12},
        "c_velo": {"mean": 73.72, "std": 3.74},
        "pop_time": {"mean": 2.11, "std": 0.12},
    },
}


# =============================================================================
# POSITION-SPECIFIC BENCHMARK LOOKUP
# =============================================================================
# Maps a player's primary position to the correct position-specific benchmarks.

_POSITION_TO_BENCHMARK: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}

# OF positions
for _pos in ("OF", "CF", "RF", "LF", "OUTFIELDER"):
    _POSITION_TO_BENCHMARK[_pos] = OF_DIVISION_BENCHMARKS

# MIF positions
for _pos in ("SS", "2B", "MIF"):
    _POSITION_TO_BENCHMARK[_pos] = MIF_DIVISION_BENCHMARKS

# CIF positions
for _pos in ("3B", "1B"):
    _POSITION_TO_BENCHMARK[_pos] = CIF_DIVISION_BENCHMARKS

# Catcher positions
for _pos in ("C", "CATCHER"):
    _POSITION_TO_BENCHMARK[_pos] = C_DIVISION_BENCHMARKS


def get_position_benchmarks(
    position: str,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Return the position-specific benchmark dict for the given primary position.

    Falls back to the general DIVISION_BENCHMARKS for unknown positions or
    generic infielder positions (IF, UTILITY, DH).
    """
    pos = position.strip().upper() if position else ""
    return _POSITION_TO_BENCHMARK.get(pos, DIVISION_BENCHMARKS)
