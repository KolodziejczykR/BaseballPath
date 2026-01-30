"""
Playing Time Calculator

Main algorithm for calculating playing time opportunity scores.
Combines player stats, ML predictions, and school data to produce
a z-score-based playing time likelihood assessment.

Algorithm Overview:
1. Calculate z-scores for player stats vs school's division benchmarks
2. Rank stats and apply dynamic weights (30% best, 25% mid, 20% worst)
3. Calculate height/weight component (15%)
4. Calculate ML alignment component (10%)
5. Apply team needs bonus (scaled 0.05-0.20 based on alignment)
6. Apply trend bonus (+0.12 declining, -0.08 improving)
7. Combine into final z-score
8. Assign to playing time bucket

See README.md for full algorithm documentation.
See constants.py for all configurable values and their rationale.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

from .constants import (
    # Stat weights
    STAT_WEIGHT_BEST,
    STAT_WEIGHT_MID,
    STAT_WEIGHT_WORST,
    STAT_WEIGHT_PHYSICAL,
    STAT_WEIGHT_ML,

    # Catcher weights
    CATCHER_HIGHER_STAT_WEIGHT,
    CATCHER_LOWER_STAT_WEIGHT,

    # ML scaling
    ML_GAP_DIVISOR,

    # Alignment bonus
    MIN_Z_FOR_ALIGNMENT_BONUS,
    MIN_ALIGNMENT_BONUS,
    MAX_ALIGNMENT_BONUS,
    ALIGNMENT_BONUS_SCALE,

    # Team needs
    TEAM_NEEDS_RATING_THRESHOLD,

    # Trend bonuses
    TREND_BONUS_DECLINING,
    TREND_BONUS_IMPROVING,
    TREND_BONUS_STABLE,

    # Level mappings
    PLAYER_LEVEL_ELITE_P4_BASE,
    PLAYER_LEVEL_ELITE_P4_RANGE,
    PLAYER_LEVEL_P4_BASE,
    PLAYER_LEVEL_P4_RANGE,
    PLAYER_LEVEL_HIGH_D1_BASE,
    PLAYER_LEVEL_HIGH_D1_RANGE,
    PLAYER_LEVEL_MID_D1_BASE,
    PLAYER_LEVEL_MID_D1_RANGE,
    PLAYER_LEVEL_LOW_D1_BASE,
    PLAYER_LEVEL_LOW_D1_RANGE,
    PLAYER_LEVEL_D2_SCALE,
    SCHOOL_LEVEL_BANDS,

    # Buckets and benchmarks
    PLAYING_TIME_BUCKETS,
    DIVISION_BENCHMARKS,

    # Stat classification
    STAT_TO_STRENGTH,
)

from .types import (
    PlayerStrength,
    TeamNeed,
    ProgramTrend,
    StatZScore,
    RankedStat,
    StatsBreakdown,
    PhysicalBreakdown,
    MLBreakdown,
    TeamFitBreakdown,
    TrendBreakdown,
    PlayingTimeResult,
    PlayerStats,
    MLPredictions,
    SchoolData,
)


logger = logging.getLogger(__name__)


class PlayingTimeCalculator:
    """
    Calculator for playing time opportunity scores.

    This class implements the complete playing time algorithm, producing
    a z-score-based assessment of how likely a player is to earn playing
    time at a specific school.

    Usage:
        calculator = PlayingTimeCalculator()
        result = calculator.calculate(player_stats, ml_predictions, school_data)
        print(result.to_dict())
    """

    def __init__(self, benchmarks: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None):
        """
        Initialize the calculator.

        Args:
            benchmarks: Optional custom benchmarks dict. If not provided,
                       uses DIVISION_BENCHMARKS from constants.py.
                       Structure: {division_group: {stat_name: {"mean": float, "std": float}}}
        """
        self.benchmarks = benchmarks or DIVISION_BENCHMARKS

    def calculate(
        self,
        player_stats: PlayerStats,
        ml_predictions: MLPredictions,
        school_data: SchoolData
    ) -> PlayingTimeResult:
        """
        Calculate playing time opportunity score for a player at a school.

        Args:
            player_stats: Player's physical and performance statistics
            ml_predictions: ML model predictions for the player
            school_data: School/program information

        Returns:
            PlayingTimeResult with z-score, bucket, and detailed breakdown
        """
        division_group = school_data.get_division_group()

        logger.debug(f"Calculating playing time for {school_data.school_name} ({division_group})")

        # Step 1: Calculate stat z-scores
        stat_z_scores = self._calculate_stat_z_scores(player_stats, division_group)

        # Step 2: Rank stats and calculate component
        stats_breakdown = self._rank_and_weight_stats(stat_z_scores, player_stats)

        # Step 3: Calculate physical component
        physical_breakdown = self._calculate_physical_component(player_stats, division_group)

        # Step 4: Calculate ML component
        ml_breakdown = self._calculate_ml_component(ml_predictions, school_data)

        # Step 5: Calculate team needs bonus
        team_fit_breakdown = self._calculate_team_fit_bonus(
            school_data,
            stats_breakdown.player_strength,
            stats_breakdown.best.z_score
        )

        # Step 6: Calculate trend bonus
        trend_breakdown = self._calculate_trend_bonus(school_data)

        # Step 7: Combine into final z-score
        final_z_score = (
            stats_breakdown.component_total +
            physical_breakdown.component_total +
            ml_breakdown.component_total +
            team_fit_breakdown.bonus +
            trend_breakdown.bonus
        )

        # Step 8: Calculate percentile and assign bucket
        percentile = self._z_to_percentile(final_z_score)
        bucket, bucket_description = self._assign_bucket(final_z_score)

        # Generate interpretation
        interpretation = self._generate_interpretation(
            final_z_score,
            bucket,
            stats_breakdown,
            team_fit_breakdown,
            trend_breakdown,
            division_group
        )

        return PlayingTimeResult(
            final_z_score=final_z_score,
            percentile=percentile,
            bucket=bucket,
            bucket_description=bucket_description,
            stats_breakdown=stats_breakdown,
            physical_breakdown=physical_breakdown,
            ml_breakdown=ml_breakdown,
            team_fit_breakdown=team_fit_breakdown,
            trend_breakdown=trend_breakdown,
            school_name=school_data.school_name,
            school_division=division_group,
            player_position=player_stats.primary_position,
            interpretation=interpretation,
        )

    def _calculate_stat_z_scores(
        self,
        player_stats: PlayerStats,
        division_group: str
    ) -> List[StatZScore]:
        """
        Calculate z-scores for all relevant stats against division benchmarks.

        For catchers, combines c_velo and pop_time with 60/40 weighting.
        Missing stats use division average (z-score = 0).
        """
        benchmarks = self.benchmarks.get(division_group, self.benchmarks.get("Non-P4 D1"))
        z_scores = []

        # Exit velocity
        z_exit = self._calc_single_z_score(
            player_stats.exit_velo,
            "exit_velo",
            benchmarks
        )
        z_scores.append(z_exit)

        # Sixty time (inverted - lower is better)
        z_sixty = self._calc_single_z_score(
            player_stats.sixty_time,
            "sixty_time",
            benchmarks,
            invert=True
        )
        z_scores.append(z_sixty)

        # Position-specific defensive stat
        if player_stats.is_catcher():
            z_pos = self._calculate_catcher_defensive_z(player_stats, benchmarks)
        else:
            pos_velo = player_stats.get_position_velo()
            pos_type = "of_velo" if player_stats.primary_position.upper() in ["OF", "LF", "CF", "RF"] else "inf_velo"
            z_pos = self._calc_single_z_score(pos_velo, pos_type, benchmarks)

        z_scores.append(z_pos)

        return z_scores

    def _calc_single_z_score(
        self,
        value: Optional[float],
        stat_name: str,
        benchmarks: Dict[str, Dict[str, float]],
        invert: bool = False
    ) -> StatZScore:
        """
        Calculate z-score for a single stat.

        Args:
            value: The stat value (None if missing)
            stat_name: Name of the stat for benchmark lookup
            benchmarks: Division benchmarks dict
            invert: If True, invert the z-score (for stats where lower is better)

        Returns:
            StatZScore with calculated z-score (0 if value is None/missing)
        """
        stat_benchmarks = benchmarks.get(stat_name, {"mean": 0, "std": 1})
        mean = stat_benchmarks["mean"]
        std = stat_benchmarks["std"]

        # Handle missing values - use division average for no impact
        if value is None:
            return StatZScore(
                stat_name=stat_name,
                raw_value=mean,  # Use mean as placeholder
                z_score=0.0,     # No impact on score
                division_mean=mean,
                division_std=std,
                is_inverted=invert,
            )

        # Calculate z-score
        if std > 0:
            z_score = (value - mean) / std
        else:
            z_score = 0.0

        # Invert if needed (for stats where lower is better)
        if invert:
            z_score = -z_score

        return StatZScore(
            stat_name=stat_name,
            raw_value=value,
            z_score=z_score,
            division_mean=mean,
            division_std=std,
            is_inverted=invert,
        )

    def _calculate_catcher_defensive_z(
        self,
        player_stats: PlayerStats,
        benchmarks: Dict[str, Dict[str, float]]
    ) -> StatZScore:
        """
        Calculate combined defensive z-score for catchers.

        Uses 60/40 weighted average favoring the higher z-score.
        This rewards catchers who excel in one area while still
        considering both c_velo and pop_time.
        """
        z_c_velo = self._calc_single_z_score(
            player_stats.c_velo,
            "c_velo",
            benchmarks
        )

        z_pop_time = self._calc_single_z_score(
            player_stats.pop_time,
            "pop_time",
            benchmarks,
            invert=True  # Lower pop time is better
        )

        # 60/40 weighted average favoring higher z-score
        higher_z = max(z_c_velo.z_score, z_pop_time.z_score)
        lower_z = min(z_c_velo.z_score, z_pop_time.z_score)

        combined_z = (CATCHER_HIGHER_STAT_WEIGHT * higher_z) + (CATCHER_LOWER_STAT_WEIGHT * lower_z)

        # Return as a combined "c_defense" stat
        return StatZScore(
            stat_name="c_defense",
            raw_value=0,  # Not applicable for combined stat
            z_score=combined_z,
            division_mean=0,
            division_std=1,
            is_inverted=False,
        )

    def _rank_and_weight_stats(
        self,
        z_scores: List[StatZScore],
        _player_stats: PlayerStats
    ) -> StatsBreakdown:
        """
        Rank stats by z-score and apply weights (30% best, 25% mid, 20% worst).
        Also determines player's primary strength category.
        """
        # Sort by z-score descending
        sorted_stats = sorted(z_scores, key=lambda x: x.z_score, reverse=True)

        # Create ranked stats
        best = RankedStat(
            stat_name=sorted_stats[0].stat_name,
            z_score=sorted_stats[0].z_score,
            weight=STAT_WEIGHT_BEST,
            rank="best"
        )
        mid = RankedStat(
            stat_name=sorted_stats[1].stat_name,
            z_score=sorted_stats[1].z_score,
            weight=STAT_WEIGHT_MID,
            rank="mid"
        )
        worst = RankedStat(
            stat_name=sorted_stats[2].stat_name,
            z_score=sorted_stats[2].z_score,
            weight=STAT_WEIGHT_WORST,
            rank="worst"
        )

        # Calculate component total
        component_total = (
            best.weighted_contribution +
            mid.weighted_contribution +
            worst.weighted_contribution
        )

        # Determine player strength from best stat
        strength_category = STAT_TO_STRENGTH.get(best.stat_name, "offensive")
        player_strength = PlayerStrength(strength_category)

        return StatsBreakdown(
            best=best,
            mid=mid,
            worst=worst,
            component_total=component_total,
            player_strength=player_strength,
            all_z_scores=z_scores,
        )

    def _calculate_physical_component(
        self,
        player_stats: PlayerStats,
        division_group: str
    ) -> PhysicalBreakdown:
        """
        Calculate the height/weight component (15% of total).
        Uses simple average of height and weight z-scores.
        """
        benchmarks = self.benchmarks.get(division_group, self.benchmarks.get("Non-P4 D1"))

        z_height = self._calc_single_z_score(
            player_stats.height,
            "height",
            benchmarks
        )
        z_weight = self._calc_single_z_score(
            player_stats.weight,
            "weight",
            benchmarks
        )

        average_z = (z_height.z_score + z_weight.z_score) / 2
        component_total = average_z * STAT_WEIGHT_PHYSICAL

        return PhysicalBreakdown(
            height_z=z_height.z_score,
            weight_z=z_weight.z_score,
            average_z=average_z,
            component_total=component_total,
            height_inches=player_stats.height or z_height.division_mean,
            weight_lbs=player_stats.weight or z_weight.division_mean,
            division_height_mean=z_height.division_mean,
            division_weight_mean=z_weight.division_mean,
        )

    def _calculate_ml_component(
        self,
        ml_predictions: MLPredictions,
        school_data: SchoolData
    ) -> MLBreakdown:
        """
        Calculate the ML prediction alignment component (10% of total).

        Compares player's predicted level (0-100) to school's level (0-100).
        The gap is scaled by ML_GAP_DIVISOR then multiplied by STAT_WEIGHT_ML.

        Note: Due to ML model probability concentration (typically 0.35-0.70),
        the practical contribution is ~±0.05. This is acceptable as stats
        provide primary differentiation.
        """
        # Calculate player's predicted level (0-100 scale)
        predicted_level = self._calculate_player_level(ml_predictions)

        # Calculate school's level (0-100 scale)
        school_level = self._calculate_school_level(school_data)

        # Calculate gap and component
        gap = predicted_level - school_level
        component_total = (gap / ML_GAP_DIVISOR) * STAT_WEIGHT_ML

        return MLBreakdown(
            predicted_level=predicted_level,
            school_level=school_level,
            gap=gap,
            component_total=component_total,
            d1_probability=ml_predictions.d1_probability,
            p4_probability=ml_predictions.p4_probability,
            is_elite=ml_predictions.is_elite,
        )

    def _calculate_player_level(self, ml_predictions: MLPredictions) -> float:
        """
        Map ML predictions to a 0-100 player level scale.

        Scale:
        - Elite P4: 88-100
        - Standard P4: 70-90
        - High Non-P4 D1: 55-75
        - Mid Non-P4 D1: 45-62
        - Low D1: 32-48
        - Sub-D1: 0-50
        """
        d1_prob = ml_predictions.d1_probability
        p4_prob = ml_predictions.p4_probability or 0

        if ml_predictions.is_elite:
            # Elite P4 players: 88-100
            return PLAYER_LEVEL_ELITE_P4_BASE + (p4_prob * PLAYER_LEVEL_ELITE_P4_RANGE)

        elif ml_predictions.p4_prediction or p4_prob > 0.5:
            # Standard P4 players: 70-90
            return PLAYER_LEVEL_P4_BASE + (p4_prob * PLAYER_LEVEL_P4_RANGE)

        elif d1_prob > 0.7:
            # High Non-P4 D1: 55-75
            return PLAYER_LEVEL_HIGH_D1_BASE + (d1_prob * PLAYER_LEVEL_HIGH_D1_RANGE)

        elif d1_prob > 0.5:
            # Mid Non-P4 D1: 45-62
            return PLAYER_LEVEL_MID_D1_BASE + (d1_prob * PLAYER_LEVEL_MID_D1_RANGE)

        elif d1_prob > 0.3:
            # Low D1 / High D2: 32-48
            return PLAYER_LEVEL_LOW_D1_BASE + (d1_prob * PLAYER_LEVEL_LOW_D1_RANGE)

        else:
            # D2/D3 level: 0-50
            return d1_prob * PLAYER_LEVEL_D2_SCALE

    def _calculate_school_level(self, school_data: SchoolData) -> float:
        """
        Map school's division and percentile to a 0-100 level scale.

        Uses SCHOOL_LEVEL_BANDS for floor and width per division group.
        Formula: floor + (percentile/100) * width
        """
        division_group = school_data.get_division_group()
        band = SCHOOL_LEVEL_BANDS.get(division_group, SCHOOL_LEVEL_BANDS["Non-P4 D1"])

        floor = band["floor"]
        width = band["width"]
        percentile = school_data.division_percentile / 100.0

        return floor + (percentile * width)

    def _calculate_team_fit_bonus(
        self,
        school_data: SchoolData,
        player_strength: PlayerStrength,
        best_stat_z: float
    ) -> TeamFitBreakdown:
        """
        Calculate team needs alignment bonus.

        Bonus is given when player's strength aligns with team's weakness.
        Bonus scales from 0.05 (at z=0.5) to 0.20 (at z=2.0+) based on
        how strong the player's aligned stat is.
        """
        # Determine team need
        team_need = self._determine_team_need(school_data)

        # Check alignment
        alignment = self._check_alignment(team_need, player_strength)

        # Calculate bonus
        bonus = 0.0
        if alignment and best_stat_z >= MIN_Z_FOR_ALIGNMENT_BONUS:
            # Linear scale from MIN_ALIGNMENT_BONUS to MAX_ALIGNMENT_BONUS
            bonus = MIN_ALIGNMENT_BONUS + (best_stat_z - MIN_Z_FOR_ALIGNMENT_BONUS) * ALIGNMENT_BONUS_SCALE
            bonus = min(MAX_ALIGNMENT_BONUS, bonus)  # Cap at maximum

        return TeamFitBreakdown(
            team_needs=team_need,
            team_offensive_rating=school_data.offensive_rating or 0,
            team_defensive_rating=school_data.defensive_rating or 0,
            player_strength=player_strength,
            best_stat_z=best_stat_z,
            alignment=alignment,
            bonus=bonus,
        )

    def _determine_team_need(self, school_data: SchoolData) -> TeamNeed:
        """
        Determine team's primary need based on offensive/defensive ratings.

        In Massey ratings, LOWER = BETTER.
        If offensive_rating > defensive_rating + threshold → offense is weaker
        """
        off_rating = school_data.offensive_rating
        def_rating = school_data.defensive_rating

        # Handle missing ratings
        if off_rating is None or def_rating is None:
            return TeamNeed.BALANCED

        if off_rating > def_rating + TEAM_NEEDS_RATING_THRESHOLD:
            return TeamNeed.OFFENSE  # Offense is weaker (higher rating = worse)
        elif def_rating > off_rating + TEAM_NEEDS_RATING_THRESHOLD:
            return TeamNeed.DEFENSE  # Defense is weaker
        else:
            return TeamNeed.BALANCED

    def _check_alignment(self, team_need: TeamNeed, player_strength: PlayerStrength) -> bool:
        """Check if player's strength aligns with team's need."""
        if team_need == TeamNeed.BALANCED:
            return False

        if team_need == TeamNeed.OFFENSE and player_strength == PlayerStrength.OFFENSIVE:
            return True

        if team_need == TeamNeed.DEFENSE and player_strength == PlayerStrength.DEFENSIVE:
            return True

        # Speed players get partial credit for either need
        if player_strength == PlayerStrength.SPEED and team_need != TeamNeed.BALANCED:
            return True

        return False

    def _calculate_trend_bonus(self, school_data: SchoolData) -> TrendBreakdown:
        """
        Calculate program trend bonus.

        Declining programs: +0.12 (more roster opportunity)
        Improving programs: -0.08 (more competition)
        Stable programs: 0
        """
        trend_str = school_data.trend.lower() if school_data.trend else "stable"

        if trend_str == "declining":
            trend = ProgramTrend.DECLINING
            bonus = TREND_BONUS_DECLINING
        elif trend_str == "improving":
            trend = ProgramTrend.IMPROVING
            bonus = TREND_BONUS_IMPROVING
        else:
            trend = ProgramTrend.STABLE
            bonus = TREND_BONUS_STABLE

        return TrendBreakdown(
            trend=trend,
            rating_change=school_data.trend_change,
            years_span=school_data.trend_years,
            bonus=bonus,
        )

    def _z_to_percentile(self, z_score: float) -> float:
        """
        Convert z-score to percentile using the standard normal CDF.

        Uses the error function approximation for efficiency.
        """
        # Standard normal CDF using error function
        # CDF(z) = 0.5 * (1 + erf(z / sqrt(2)))
        return 0.5 * (1 + math.erf(z_score / math.sqrt(2))) * 100

    def _assign_bucket(self, z_score: float) -> Tuple[str, str]:
        """
        Assign a playing time bucket based on z-score.

        Returns tuple of (bucket_name, description).
        """
        for min_z, bucket_name, description in PLAYING_TIME_BUCKETS:
            if z_score >= min_z:
                return bucket_name, description

        # Fallback (should not reach here due to float('-inf') in last bucket)
        return "Unknown", "Unable to determine bucket"

    def _generate_interpretation(
        self,
        final_z: float,
        bucket: str,
        stats_breakdown: StatsBreakdown,
        team_fit: TeamFitBreakdown,
        trend: TrendBreakdown,
        division_group: str
    ) -> str:
        """
        Generate a human-readable interpretation of the result.
        """
        parts = []

        # Main assessment
        percentile = self._z_to_percentile(final_z)
        parts.append(f"Your stats put you in the top {100 - percentile:.0f}% for {division_group}.")

        # Best stat highlight
        best_stat_name = stats_breakdown.best.stat_name.replace("_", " ").title()
        best_z = stats_breakdown.best.z_score

        if best_z > 1.5:
            parts.append(f"Your {best_stat_name} is a standout tool (top 7%).")
        elif best_z > 1.0:
            parts.append(f"Your {best_stat_name} is above average (top 16%).")
        elif best_z > 0.5:
            parts.append(f"Your {best_stat_name} is slightly above average.")

        # Team fit context
        if team_fit.alignment and team_fit.bonus > 0:
            need_str = "offensive help" if team_fit.team_needs == TeamNeed.OFFENSE else "defensive help"
            parts.append(f"This team needs {need_str}, and that's your strength.")

        # Trend context
        if trend.trend == ProgramTrend.DECLINING:
            parts.append("The program is in a rebuilding phase, creating more roster opportunity.")
        elif trend.trend == ProgramTrend.IMPROVING:
            parts.append("The program is on the rise, meaning more competition for spots.")

        # Overall assessment
        parts.append(f"Assessment: {bucket}.")

        return " ".join(parts)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def calculate_playing_time(
    player_stats: PlayerStats,
    ml_predictions: MLPredictions,
    school_data: SchoolData,
    benchmarks: Optional[Dict] = None
) -> PlayingTimeResult:
    """
    Convenience function to calculate playing time score.

    Args:
        player_stats: Player statistics
        ml_predictions: ML prediction outputs
        school_data: School/program data
        benchmarks: Optional custom benchmarks

    Returns:
        PlayingTimeResult with full breakdown
    """
    calculator = PlayingTimeCalculator(benchmarks=benchmarks)
    return calculator.calculate(player_stats, ml_predictions, school_data)
