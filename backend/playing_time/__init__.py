"""
Playing Time Calculator Module

Calculates playing time opportunity scores for baseball recruits based on
player stats, ML predictions, and school program data.

Usage:
    from backend.playing_time import (
        PlayingTimeCalculator,
        calculate_playing_time,
        PlayerStats,
        MLPredictions,
        SchoolData,
    )

    result = calculate_playing_time(player_stats, ml_predictions, school_data)
    print(result.final_z_score, result.bucket)
"""

# Main calculator
from .playing_time_calculator import (
    PlayingTimeCalculator,
    calculate_playing_time,
)

# Input types
from .types import (
    PlayerStats,
    MLPredictions,
    SchoolData,
)

# Output types
from .types import (
    PlayingTimeResult,
    StatsBreakdown,
    PhysicalBreakdown,
    MLBreakdown,
    TeamFitBreakdown,
    TrendBreakdown,
    StatZScore,
    RankedStat,
)

# Enums
from .types import (
    PlayerStrength,
    TeamNeed,
    ProgramTrend,
)

# Constants (for customization)
from .constants import (
    DIVISION_BENCHMARKS,
    PLAYING_TIME_BUCKETS,
    SCHOOL_LEVEL_BANDS,
)

# Mappers (for pipeline integration)
from .mappers import (
    player_type_to_stats,
    ml_results_to_predictions,
    school_data_to_context,
    create_playing_time_inputs,
)

__all__ = [
    # Calculator
    "PlayingTimeCalculator",
    "calculate_playing_time",
    # Input types
    "PlayerStats",
    "MLPredictions",
    "SchoolData",
    # Output types
    "PlayingTimeResult",
    "StatsBreakdown",
    "PhysicalBreakdown",
    "MLBreakdown",
    "TeamFitBreakdown",
    "TrendBreakdown",
    "StatZScore",
    "RankedStat",
    # Enums
    "PlayerStrength",
    "TeamNeed",
    "ProgramTrend",
    # Constants
    "DIVISION_BENCHMARKS",
    "PLAYING_TIME_BUCKETS",
    "SCHOOL_LEVEL_BANDS",
    # Mappers
    "player_type_to_stats",
    "ml_results_to_predictions",
    "school_data_to_context",
    "create_playing_time_inputs",
]
