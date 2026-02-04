"""
Playing Time Data Mappers

This module provides conversion functions to map between the pipeline's data structures
and the playing time calculator's input types. This keeps the playing time module
decoupled from the rest of the system while enabling integration.

Mappings:
- PlayerType (PlayerInfielder/PlayerOutfielder/PlayerCatcher) -> PlayerStats
- MLPipelineResults -> MLPredictions
- school_data dict + baseball_strength -> SchoolData
"""

from typing import Dict, Any, Optional, Union

from backend.playing_time.types import PlayerStats, MLPredictions, SchoolData
from backend.utils.player_types import (
    PlayerType,
    PlayerInfielder,
    PlayerOutfielder,
    PlayerCatcher,
    PlayerPitcher,
)
from backend.utils.prediction_types import MLPipelineResults


def player_type_to_stats(player: PlayerType) -> PlayerStats:
    """
    Convert a PlayerType object to PlayerStats for playing time calculation.

    Handles PlayerInfielder, PlayerOutfielder, and PlayerCatcher by extracting
    the relevant position-specific velocity stat.

    Args:
        player: A PlayerType subclass instance

    Returns:
        PlayerStats: Standardized stats structure for the calculator
    """
    # Get base stats common to all player types
    player_info = player.get_player_info()

    # Initialize with common stats
    stats = PlayerStats(
        exit_velo=player_info.get('exit_velo_max'),  # Note: field name differs
        sixty_time=player_info.get('sixty_time'),
        height=player_info.get('height'),
        weight=player_info.get('weight'),
        primary_position=player_info.get('primary_position'),
    )

    # Add position-specific velocity
    if isinstance(player, PlayerCatcher):
        stats.c_velo = player_info.get('c_velo')
        stats.pop_time = player_info.get('pop_time')
    elif isinstance(player, PlayerOutfielder):
        stats.of_velo = player_info.get('of_velo')
    elif isinstance(player, PlayerInfielder):
        stats.inf_velo = player_info.get('inf_velo')
    elif isinstance(player, PlayerPitcher):
        # Map pitcher metrics if present
        stats.fb_velo_range = (
            player_info.get('FastballVelo Range')
            or player_info.get('FastballVelo (avg)')
            or player_info.get('fastball_velo_range')
        )
        stats.fb_velo_max = player_info.get('FastballVelocity (max)') or player_info.get('fastball_velo_max')
        stats.fb_spin = player_info.get('FastballSpin Rate (avg)') or player_info.get('fastball_spin')

        stats.ch_velo = player_info.get('Changeup Velo Range') or player_info.get('changeup_velo')
        stats.ch_spin = player_info.get('Changeup Spin Rate (avg)') or player_info.get('changeup_spin')
        stats.cb_velo = player_info.get('Curveball Velo Range') or player_info.get('curveball_velo')
        stats.cb_spin = player_info.get('Curveball Spin Rate (avg)') or player_info.get('curveball_spin')
        stats.sl_velo = player_info.get('Slider Velo Range') or player_info.get('slider_velo')
        stats.sl_spin = player_info.get('Slider Spin Rate (avg)') or player_info.get('slider_spin')

    return stats


def ml_results_to_predictions(ml_results: MLPipelineResults) -> MLPredictions:
    """
    Convert MLPipelineResults to MLPredictions for playing time calculation.

    Extracts D1 probability, P4 probability, and elite status from the
    ML pipeline output.

    Args:
        ml_results: Output from the ML prediction pipeline

    Returns:
        MLPredictions: Standardized ML predictions for the calculator
    """
    d1_results = ml_results.d1_results
    p4_results = ml_results.p4_results

    return MLPredictions(
        d1_probability=d1_results.d1_probability,
        p4_probability=p4_results.p4_probability if p4_results else None,
        is_elite=p4_results.is_elite if p4_results else False,
        d1_prediction=d1_results.d1_prediction,
        p4_prediction=p4_results.p4_prediction if p4_results else False,
        confidence=d1_results.confidence,
    )


def school_data_to_context(
    school_data: Dict[str, Any],
    baseball_strength: Optional[Dict[str, Any]] = None
) -> SchoolData:
    """
    Convert school_data dictionary and optional baseball_strength to SchoolData.

    This maps the database school record and baseball rankings data into the
    format expected by the playing time calculator.

    Args:
        school_data: School record from the database with fields like:
            - school_name, division, division_group, conference, etc.
        baseball_strength: Optional output from BaseballRankingsIntegration with:
            - offensive_rating, defensive_rating, trend_analysis, etc.

    Returns:
        SchoolData: Standardized school context for the calculator
    """
    # Determine division number from division_group string
    division_group = school_data.get('division_group', 'Non-P4 D1')
    division = _parse_division_number(division_group, school_data.get('division'))
    is_power_4 = division_group == 'P4' or division_group == 'Power 4 D1'

    # Get conference info
    conference = school_data.get('conference')

    # Get division percentile if available (default to 50th)
    division_percentile = school_data.get('division_percentile', 50.0)

    # Initialize with school data
    school_context = SchoolData(
        school_name=school_data.get('school_name', 'Unknown'),
        division=division,
        conference=conference,
        is_power_4=is_power_4,
        division_percentile=division_percentile,
    )

    # Add baseball rankings data if available
    if baseball_strength and baseball_strength.get('has_data'):
        school_context.offensive_rating = baseball_strength.get('offensive_rating')
        school_context.defensive_rating = baseball_strength.get('defensive_rating')

        # Extract trend data
        trend_analysis = baseball_strength.get('trend_analysis', {})
        trend = trend_analysis.get('trend', 'stable')
        school_context.trend = trend.lower() if trend else 'stable'
        school_context.trend_change = trend_analysis.get('rating_change')
        school_context.trend_years = trend_analysis.get('years_span')

        # Use percentile from rankings if available and school_data doesn't have it
        if 'percentile' in baseball_strength and division_percentile == 50.0:
            school_context.division_percentile = baseball_strength.get('percentile', 50.0)

    return school_context


def _parse_division_number(division_group: str, fallback: Optional[int] = None) -> int:
    """
    Parse division number from division_group string.

    Args:
        division_group: String like "P4", "Non-P4 D1", "D2", "D3"
        fallback: Optional fallback division number

    Returns:
        int: Division number (1, 2, or 3)
    """
    if fallback is not None:
        return fallback

    division_group_upper = division_group.upper()

    if 'D3' in division_group_upper or division_group_upper == '3':
        return 3
    elif 'D2' in division_group_upper or division_group_upper == '2':
        return 2
    else:
        # Default to D1 (includes P4, Non-P4 D1, D1)
        return 1


def create_playing_time_inputs(
    player: PlayerType,
    ml_results: MLPipelineResults,
    school_data: Dict[str, Any],
    baseball_strength: Optional[Dict[str, Any]] = None
) -> tuple:
    """
    Convenience function to create all playing time calculator inputs at once.

    This is the main entry point for the pipeline integration, converting all
    the pipeline's data structures into the format expected by the calculator.

    Args:
        player: PlayerType object from the pipeline
        ml_results: ML prediction results
        school_data: School database record
        baseball_strength: Optional baseball rankings data

    Returns:
        tuple: (PlayerStats, MLPredictions, SchoolData) ready for calculator
    """
    return (
        player_type_to_stats(player),
        ml_results_to_predictions(ml_results),
        school_data_to_context(school_data, baseball_strength),
    )
