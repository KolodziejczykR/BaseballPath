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

    # Resolve position robustly: some legacy player payloads may omit
    # or mis-populate `primary_position` in get_player_info().
    resolved_primary_position = _resolve_primary_position(player, player_info)

    # Initialize with common stats
    stats = PlayerStats(
        exit_velo=player_info.get('exit_velo_max'),  # Note: field name differs
        sixty_time=player_info.get('sixty_time'),
        height=player_info.get('height'),
        weight=player_info.get('weight'),
        primary_position=resolved_primary_position,
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
    division_group = _normalize_division_group(
        school_data.get('division_group')
        or school_data.get('baseball_division_group')
    )
    division = _parse_division_number(
        division_group,
        school_data.get('division') or school_data.get('baseball_division')
    )
    is_power_4 = division_group in ('P4', 'Power 4 D1')

    # Get conference info
    conference = school_data.get('conference')

    # Get division percentile if available (default to 50th)
    division_percentile = _coerce_percentile(
        school_data.get('division_percentile')
        or school_data.get('baseball_division_percentile')
    )

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
        current_season = baseball_strength.get('current_season', {}) or {}
        weighted = baseball_strength.get('weighted_averages', {}) or {}

        school_context.offensive_rating = (
            baseball_strength.get('offensive_rating')
            or weighted.get('weighted_offensive_rating')
            or current_season.get('offensive_rating')
        )
        school_context.defensive_rating = (
            baseball_strength.get('defensive_rating')
            or weighted.get('weighted_defensive_rating')
            or current_season.get('defensive_rating')
        )

        # Extract trend data
        trend_analysis = baseball_strength.get('trend_analysis', {})
        trend = trend_analysis.get('trend', 'stable')
        school_context.trend = trend.lower() if trend else 'stable'
        school_context.trend_change = (
            trend_analysis.get('rating_change')
            if trend_analysis.get('rating_change') is not None
            else trend_analysis.get('change')
        )
        school_context.trend_years = trend_analysis.get('years_span')

        # Use percentile from rankings if available and school_data doesn't have it
        if division_percentile == 50.0:
            rankings_percentile = _coerce_percentile(
                baseball_strength.get('division_percentile')
                or baseball_strength.get('percentile')
                or current_season.get('division_percentile')
            )
            school_context.division_percentile = rankings_percentile
    else:
        # Fallback to enrichment fields from school_data when full strength profile isn't present.
        school_context.offensive_rating = school_data.get('baseball_offensive_rating')
        school_context.defensive_rating = school_data.get('baseball_defensive_rating')
        school_context.trend = str(
            school_data.get('baseball_program_trend')
            or school_data.get('trend')
            or 'stable'
        ).lower()
        school_context.trend_change = school_data.get('baseball_trend_change')
        school_context.trend_years = school_data.get('baseball_trend_years')

    return school_context


def _parse_division_number(division_group: str, fallback: Optional[Any] = None) -> int:
    """
    Parse division number from division_group string.

    Args:
        division_group: String like "P4", "Non-P4 D1", "D2", "D3"
        fallback: Optional fallback division number

    Returns:
        int: Division number (1, 2, or 3)
    """
    parsed_fallback = _coerce_division_number(fallback)
    if parsed_fallback is not None:
        return parsed_fallback

    division_group_upper = division_group.upper()

    if 'NON-D1' in division_group_upper or 'NON D1' in division_group_upper:
        # Non-D1 can include D2 and D3. Default to D2 benchmark when unknown.
        return 2

    if 'D3' in division_group_upper or division_group_upper == '3':
        return 3
    elif 'D2' in division_group_upper or division_group_upper == '2':
        return 2
    else:
        # Default to D1 (includes P4, Non-P4 D1, D1)
        return 1


def _normalize_division_group(value: Optional[Any]) -> str:
    """Normalize division labels to the calculator's expected vocabulary."""
    if value is None:
        return "Non-D1"
    text = str(value).strip()
    lowered = text.lower()

    if lowered in {"p4", "power 4 d1", "power4 d1", "power 4"}:
        return "Power 4 D1"
    if lowered in {"non-p4 d1", "non p4 d1", "d1", "division 1", "division i"}:
        return "Non-P4 D1"
    if lowered in {"non-d1", "non d1"}:
        return "Non-D1"

    if "power" in lowered and "4" in lowered:
        return "Power 4 D1"
    if "non-p4" in lowered or "non p4" in lowered:
        return "Non-P4 D1"
    if "non-d1" in lowered or "non d1" in lowered:
        return "Non-D1"

    return text


def _coerce_division_number(value: Optional[Any]) -> Optional[int]:
    """Coerce division value to 1/2/3 where possible."""
    if value is None:
        return None

    try:
        as_int = int(value)
        if as_int in (1, 2, 3):
            return as_int
    except (TypeError, ValueError):
        pass

    text = str(value).strip().lower()
    if not text:
        return None

    if any(token in text for token in ("d1", "division 1", "division i", "ncaa i")):
        return 1
    if any(token in text for token in ("d2", "division 2", "division ii", "ncaa ii")):
        return 2
    if any(token in text for token in ("d3", "division 3", "division iii", "ncaa iii")):
        return 3

    return None


def _coerce_percentile(value: Optional[Any]) -> float:
    """Convert a percentile-like value into [0, 100], defaulting to 50."""
    if value is None:
        return 50.0

    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return 50.0

    if as_float < 0:
        return 0.0
    if as_float > 100:
        return 100.0
    return as_float


def _resolve_primary_position(player: PlayerType, player_info: Dict[str, Any]) -> str:
    """
    Determine a reliable primary position for playing-time calculations.
    """
    candidate = player_info.get("primary_position") or getattr(player, "primary_position", None)
    if isinstance(candidate, str):
        normalized = candidate.strip().upper()
        # Guard against legacy bad values where region was accidentally stored.
        if normalized and normalized not in {"WEST", "SOUTH", "NORTHEAST", "MIDWEST"}:
            return normalized

    if isinstance(player, PlayerOutfielder):
        return "OF"
    if isinstance(player, PlayerCatcher):
        return "C"
    if isinstance(player, PlayerPitcher):
        throwing = str(player_info.get("throwing_hand") or getattr(player, "throwing_hand", "R")).upper()
        return "LHP" if throwing == "L" else "RHP"
    if isinstance(player, PlayerInfielder):
        return "SS"

    return "SS"


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
