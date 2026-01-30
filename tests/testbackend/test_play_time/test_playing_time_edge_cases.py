"""
Edge Case / Breaking Tests for Playing Time Calculator

These 10 tests are designed to stress test the calculator with edge cases,
boundary conditions, and inputs that might cause failures or unexpected behavior.

Test coverage:
1. All stats missing (None values)
2. Partially missing stats (mixed None and values)
3. Extreme stat values (far outside normal range)
4. Invalid/unknown division group
5. Missing team ratings (None offensive/defensive)
6. Catcher with only one defensive stat
7. Zero standard deviation in benchmarks
8. Negative z-scores with alignment check (below threshold)
9. Boundary condition: z-score exactly at bucket threshold
10. Unknown position string handling
"""

import pytest
import math
from typing import Dict

from backend.playing_time import (
    PlayingTimeCalculator,
    PlayerStats,
    MLPredictions,
    SchoolData,
    PlayerStrength,
    TeamNeed,
    ProgramTrend,
)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_all_stats_missing_produces_zero_z_scores(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 1: All stats missing (None values)

        When all player stats are None, the calculator should handle gracefully
        by using division averages (z-score = 0 for each stat).
        """
        # Player with no stats provided
        empty_player = PlayerStats(
            exit_velo=None,
            sixty_time=None,
            inf_velo=None,
            height=None,
            weight=None,
            primary_position="IF",  # Must have position
        )

        result = calculator.calculate(
            empty_player,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # All stat z-scores should be 0
        for z_stat in result.stats_breakdown.all_z_scores:
            assert z_stat.z_score == 0.0, (
                f"Missing stat {z_stat.stat_name} should have z-score 0, got {z_stat.z_score}"
            )

        # Physical z-scores should also be 0
        assert result.physical_breakdown.height_z == 0.0
        assert result.physical_breakdown.weight_z == 0.0

        # Result should still be valid
        assert isinstance(result.final_z_score, float)
        assert result.bucket is not None

    def test_partially_missing_stats_handled_correctly(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 2: Partially missing stats (mixed None and values)

        Calculator should handle mix of provided and missing stats.
        """
        partial_player = PlayerStats(
            exit_velo=95.0,      # Provided
            sixty_time=None,     # Missing
            inf_velo=85.0,       # Provided
            height=None,         # Missing
            weight=190,          # Provided
            primary_position="SS",
        )

        result = calculator.calculate(
            partial_player,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Find the z-scores
        exit_z = None
        sixty_z = None
        for z_stat in result.stats_breakdown.all_z_scores:
            if z_stat.stat_name == "exit_velo":
                exit_z = z_stat
            elif z_stat.stat_name == "sixty_time":
                sixty_z = z_stat

        # exit_velo should have non-zero z-score (95 vs 92 mean)
        assert exit_z is not None and exit_z.z_score != 0, "Provided stat should have non-zero z"

        # sixty_time should have zero z-score (missing)
        assert sixty_z is not None and sixty_z.z_score == 0, "Missing stat should have z=0"

    def test_extreme_stat_values_dont_cause_overflow(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 3: Extreme stat values (far outside normal range)

        Calculator should handle extreme values without overflow or NaN.
        """
        extreme_player = PlayerStats(
            exit_velo=120.0,     # Impossibly high (would be ~6σ)
            sixty_time=5.0,      # Impossibly fast
            inf_velo=100.0,      # Impossibly high
            height=84,           # 7 feet tall
            weight=300,          # Very heavy
            primary_position="1B",
        )

        result = calculator.calculate(
            extreme_player,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Should not be NaN or infinite
        assert not math.isnan(result.final_z_score), "Z-score should not be NaN"
        assert not math.isinf(result.final_z_score), "Z-score should not be infinite"

        # Should have very high z-scores
        assert result.final_z_score > 2.0, (
            f"Extreme stats should produce high z-score, got {result.final_z_score}"
        )

        # Should be "Likely Starter"
        assert result.bucket == "Likely Starter"

    def test_invalid_division_group_falls_back_to_default(self, calculator, high_d1_ml_predictions):
        """
        TEST 4: Invalid/unknown division group

        If somehow an invalid division is passed, should fall back to Non-P4 D1.
        """
        player = PlayerStats(
            exit_velo=92.0,
            sixty_time=7.0,
            inf_velo=83.0,
            height=72,
            weight=185,
            primary_position="SS",
        )

        # Create school with invalid division
        weird_school = SchoolData(
            school_name="Weird School",
            division=99,  # Invalid division
            is_power_4=False,
            division_percentile=50.0,
        )

        # The get_division_group() will return "D3" for division != 1,2
        # But internally, if benchmarks don't have that key, it falls back
        result = calculator.calculate(player, high_d1_ml_predictions, weird_school)

        # Should still produce valid result
        assert isinstance(result.final_z_score, float)
        assert result.bucket is not None

    def test_missing_team_ratings_results_in_balanced_need(
        self, calculator, average_infielder_stats, high_d1_ml_predictions
    ):
        """
        TEST 5: Missing team ratings (None offensive/defensive)

        When both ratings are None, team should be marked as BALANCED.
        """
        school_no_ratings = SchoolData(
            school_name="No Ratings U",
            division=1,
            is_power_4=False,
            division_percentile=50.0,
            offensive_rating=None,  # Missing
            defensive_rating=None,  # Missing
            trend="stable",
        )

        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            school_no_ratings
        )

        # Should be BALANCED
        assert result.team_fit_breakdown.team_needs == TeamNeed.BALANCED, (
            f"Missing ratings should result in BALANCED, got {result.team_fit_breakdown.team_needs}"
        )

        # No alignment bonus
        assert result.team_fit_breakdown.bonus == 0.0, (
            "Balanced team should have no alignment bonus"
        )

    def test_catcher_with_only_c_velo_no_pop_time(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 6: Catcher with only one defensive stat

        If catcher has c_velo but no pop_time (or vice versa), should handle gracefully.
        """
        partial_catcher = PlayerStats(
            exit_velo=90.0,
            sixty_time=7.2,
            c_velo=84.0,         # Provided
            pop_time=None,       # Missing
            height=72,
            weight=195,
            primary_position="C",
        )

        result = calculator.calculate(
            partial_catcher,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Should have c_defense combined stat
        c_defense = None
        for z_stat in result.stats_breakdown.all_z_scores:
            if z_stat.stat_name == "c_defense":
                c_defense = z_stat
                break

        assert c_defense is not None, "Should have c_defense stat"

        # Result should be valid (not NaN)
        assert not math.isnan(c_defense.z_score)

    def test_zero_std_benchmark_doesnt_cause_division_by_zero(self, high_d1_ml_predictions, non_p4_d1_school):
        """
        TEST 7: Zero standard deviation in benchmarks

        Custom benchmarks with std=0 should not cause division by zero.
        """
        # Custom benchmarks with zero std
        bad_benchmarks = {
            "Non-P4 D1": {
                "exit_velo": {"mean": 92.0, "std": 0.0},  # Zero std!
                "sixty_time": {"mean": 7.0, "std": 0.0},
                "inf_velo": {"mean": 83.0, "std": 0.0},
                "height": {"mean": 72.0, "std": 0.0},
                "weight": {"mean": 185.0, "std": 0.0},
            }
        }

        calculator = PlayingTimeCalculator(benchmarks=bad_benchmarks)

        player = PlayerStats(
            exit_velo=95.0,
            sixty_time=6.8,
            inf_velo=85.0,
            height=73,
            weight=190,
            primary_position="SS",
        )

        result = calculator.calculate(player, high_d1_ml_predictions, non_p4_d1_school)

        # Should not crash, z-scores should be 0 when std is 0
        for z_stat in result.stats_breakdown.all_z_scores:
            assert not math.isnan(z_stat.z_score), f"Z-score for {z_stat.stat_name} is NaN"
            assert z_stat.z_score == 0.0, (
                f"Zero std should produce z=0, got {z_stat.z_score} for {z_stat.stat_name}"
            )

    def test_low_z_score_below_alignment_threshold_gets_no_bonus(
        self, calculator, high_d1_ml_predictions, school_needs_offense
    ):
        """
        TEST 8: Negative z-scores with alignment check (below threshold)

        A player whose best stat is below the MIN_Z_FOR_ALIGNMENT_BONUS (0.5)
        should not get an alignment bonus even if strength matches team need.
        """
        # Player with offensive strength but z-score below 0.5
        weak_offensive_player = PlayerStats(
            exit_velo=90.0,      # z = (90-92)/4.5 = -0.44 for Non-P4 D1
            sixty_time=7.1,      # Average
            inf_velo=81.0,       # Below average
            height=72,
            weight=185,
            primary_position="1B",
        )

        result = calculator.calculate(
            weak_offensive_player,
            high_d1_ml_predictions,
            school_needs_offense
        )

        # Best stat z-score should be below 0.5 (negative or near zero)
        best_z = result.stats_breakdown.best.z_score

        # If best z < 0.5, no bonus should be given
        if best_z < 0.5:
            assert result.team_fit_breakdown.bonus == 0.0, (
                f"Z-score {best_z} below 0.5 should get no bonus, got {result.team_fit_breakdown.bonus}"
            )

    def test_z_score_exactly_at_bucket_threshold(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 9: Boundary condition: z-score exactly at bucket threshold

        When z-score lands exactly on a bucket threshold, should assign
        to the higher bucket (>= comparison).
        """
        # The buckets are defined as:
        # (1.5, "Likely Starter", ...)
        # (1.0, "Compete for Time", ...)
        # (0.5, "Developmental", ...)
        # etc.

        # We need to manipulate inputs to get close to threshold
        # This is tricky, so we'll test the _assign_bucket method directly

        # Test z = 1.0 exactly
        bucket, _ = calculator._assign_bucket(1.0)
        assert bucket == "Compete for Time", f"z=1.0 should be 'Compete for Time', got {bucket}"

        # Test z = 0.9999 (just below 1.0)
        bucket, _ = calculator._assign_bucket(0.9999)
        assert bucket == "Developmental", f"z=0.9999 should be 'Developmental', got {bucket}"

        # Test z = 1.5 exactly
        bucket, _ = calculator._assign_bucket(1.5)
        assert bucket == "Likely Starter", f"z=1.5 should be 'Likely Starter', got {bucket}"

        # Test z = -0.5 exactly
        bucket, _ = calculator._assign_bucket(-0.5)
        assert bucket == "Stretch", f"z=-0.5 should be 'Stretch', got {bucket}"

    def test_unknown_position_defaults_to_infielder(
        self, calculator, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 10: Unknown position string handling

        An unknown position string should default to infielder velocity path.
        """
        # Player with weird position
        weird_position_player = PlayerStats(
            exit_velo=92.0,
            sixty_time=7.0,
            inf_velo=85.0,       # Should use this
            of_velo=88.0,        # Should NOT use this
            height=72,
            weight=185,
            primary_position="DH",  # Not a fielding position
        )

        result = calculator.calculate(
            weird_position_player,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Should use inf_velo (default for non-OF, non-C positions)
        inf_stat = None
        for z_stat in result.stats_breakdown.all_z_scores:
            if z_stat.stat_name == "inf_velo":
                inf_stat = z_stat
                break

        assert inf_stat is not None, "DH should default to inf_velo path"


class TestMLEdgeCases:
    """Edge cases specific to ML component calculations."""

    def test_ml_probability_at_boundaries(self, calculator, non_p4_d1_school):
        """
        Test ML with probability at exact boundaries (0, 1).
        """
        player = PlayerStats(
            exit_velo=92.0,
            sixty_time=7.0,
            inf_velo=83.0,
            height=72,
            weight=185,
            primary_position="SS",
        )

        # Test d1_probability = 0
        low_ml = MLPredictions(
            d1_probability=0.0,
            p4_probability=0.0,
            is_elite=False,
        )

        result = calculator.calculate(player, low_ml, non_p4_d1_school)
        assert not math.isnan(result.ml_breakdown.predicted_level)
        assert result.ml_breakdown.predicted_level >= 0

        # Test d1_probability = 1
        high_ml = MLPredictions(
            d1_probability=1.0,
            p4_probability=1.0,
            is_elite=True,
        )

        result = calculator.calculate(player, high_ml, non_p4_d1_school)
        assert not math.isnan(result.ml_breakdown.predicted_level)
        assert result.ml_breakdown.predicted_level <= 100

    def test_p4_probability_none_handled(self, calculator, non_p4_d1_school):
        """
        Test when p4_probability is explicitly None.
        """
        player = PlayerStats(
            exit_velo=92.0,
            sixty_time=7.0,
            inf_velo=83.0,
            height=72,
            weight=185,
            primary_position="SS",
        )

        ml_no_p4 = MLPredictions(
            d1_probability=0.65,
            p4_probability=None,  # Explicitly None
            is_elite=False,
        )

        result = calculator.calculate(player, ml_no_p4, non_p4_d1_school)

        # Should not crash
        assert isinstance(result.final_z_score, float)
        assert result.ml_breakdown.p4_probability is None


class TestSchoolLevelEdgeCases:
    """Edge cases for school level calculations."""

    def test_school_percentile_at_extremes(self, calculator, average_infielder_stats, high_d1_ml_predictions):
        """
        Test school percentile at 0 and 100.
        """
        player = average_infielder_stats

        # Bottom of division (0th percentile)
        bottom_school = SchoolData(
            school_name="Last Place U",
            division=1,
            is_power_4=False,
            division_percentile=0.0,
        )

        result = calculator.calculate(player, high_d1_ml_predictions, bottom_school)
        assert result.ml_breakdown.school_level >= 0
        # Non-P4 D1 floor is 45, so school_level should be 45
        assert result.ml_breakdown.school_level == pytest.approx(45.0, abs=1.0)

        # Top of division (100th percentile)
        top_school = SchoolData(
            school_name="First Place U",
            division=1,
            is_power_4=False,
            division_percentile=100.0,
        )

        result = calculator.calculate(player, high_d1_ml_predictions, top_school)
        # Non-P4 D1 ceiling is 45 + 30 = 75
        assert result.ml_breakdown.school_level == pytest.approx(75.0, abs=1.0)

    def test_trend_string_case_insensitive(self, calculator, average_infielder_stats, high_d1_ml_predictions):
        """
        Test that trend string is case-insensitive.
        """
        player = average_infielder_stats

        # Test uppercase
        school_upper = SchoolData(
            school_name="Test U",
            division=1,
            is_power_4=False,
            division_percentile=50.0,
            trend="DECLINING",  # Uppercase
        )

        result = calculator.calculate(player, high_d1_ml_predictions, school_upper)
        assert result.trend_breakdown.trend == ProgramTrend.DECLINING

        # Test mixed case
        school_mixed = SchoolData(
            school_name="Test U",
            division=1,
            is_power_4=False,
            division_percentile=50.0,
            trend="Improving",  # Mixed case
        )

        result = calculator.calculate(player, high_d1_ml_predictions, school_mixed)
        assert result.trend_breakdown.trend == ProgramTrend.IMPROVING
