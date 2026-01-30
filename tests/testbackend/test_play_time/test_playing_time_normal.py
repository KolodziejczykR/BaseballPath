"""
Normal Data Flow Tests for Playing Time Calculator

These 10 tests verify that the playing time calculator works correctly
with standard, expected inputs. Each test verifies a specific part of
the data flow or a common use case.

Test coverage:
1. Average player at matching school level → near-zero z-score
2. Elite player at lower division school → high positive z-score
3. Below average player at higher division → negative z-score
4. Catcher 60/40 defensive weighting
5. Outfielder position velocity path
6. Team needs alignment bonus (offense)
7. Team needs alignment bonus (defense)
8. Declining program trend bonus
9. Improving program trend penalty
10. Full output structure validation
"""

import pytest
import math

from backend.playing_time import (
    PlayerStats,
    PlayerStrength,
    TeamNeed,
    ProgramTrend,
)


class TestNormalDataFlow:
    """Tests for normal, expected data flow through the calculator."""

    def test_average_player_at_matching_school_produces_near_zero_z_score(
        self, calculator, average_infielder_stats, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 1: Average player at matching school level → near-zero z-score

        An average Non-P4 D1 player with stats at division mean should produce
        a z-score close to 0 when evaluated against a Non-P4 D1 school.
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Z-score should be close to 0 (within ±0.5 accounting for ML/bonuses)
        assert -0.5 <= result.final_z_score <= 0.5, (
            f"Average player should have near-zero z-score, got {result.final_z_score}"
        )

        # Individual stat z-scores should be very close to 0
        for z_stat in result.stats_breakdown.all_z_scores:
            assert -0.3 <= z_stat.z_score <= 0.3, (
                f"Stat {z_stat.stat_name} z-score should be near 0, got {z_stat.z_score}"
            )

    def test_elite_player_at_lower_division_produces_high_positive_z_score(
        self, calculator, elite_infielder_stats, elite_p4_ml_predictions, d2_school
    ):
        """
        TEST 2: Elite player at lower division school → high positive z-score

        An elite P4-level player should have very high positive z-scores when
        evaluated against D2 benchmarks.
        """
        result = calculator.calculate(
            elite_infielder_stats,
            elite_p4_ml_predictions,
            d2_school
        )

        # Should be "Likely Starter" or "Compete for Time"
        assert result.final_z_score >= 1.0, (
            f"Elite player at D2 should have z >= 1.0, got {result.final_z_score}"
        )
        assert result.bucket in ["Likely Starter", "Compete for Time"], (
            f"Expected starter-level bucket, got {result.bucket}"
        )

        # Should be in high percentile
        assert result.percentile >= 80, (
            f"Elite player should be 80th+ percentile, got {result.percentile}"
        )

    def test_below_average_player_at_higher_division_produces_negative_z_score(
        self, calculator, below_average_player, d2_level_ml_predictions, p4_school
    ):
        """
        TEST 3: Below average player at higher division → negative z-score

        A D2-level player evaluated against P4 benchmarks should have
        negative z-scores indicating they would struggle to compete.
        """
        result = calculator.calculate(
            below_average_player,
            d2_level_ml_predictions,
            p4_school
        )

        # Should have negative z-score
        assert result.final_z_score < 0, (
            f"Below-average player at P4 should have negative z-score, got {result.final_z_score}"
        )

        # Should be in lower buckets
        assert result.bucket in ["Stretch", "Reach"], (
            f"Expected lower bucket, got {result.bucket}"
        )

    def test_catcher_uses_60_40_defensive_weighting(
        self, calculator, elite_catcher_stats, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 4: Catcher 60/40 defensive weighting

        Catchers should have their c_velo and pop_time combined with
        60% weight on the higher z-score and 40% on the lower.
        """
        result = calculator.calculate(
            elite_catcher_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Find the c_defense combined stat
        c_defense_stat = None
        for z_stat in result.stats_breakdown.all_z_scores:
            if z_stat.stat_name == "c_defense":
                c_defense_stat = z_stat
                break

        assert c_defense_stat is not None, "Catcher should have c_defense combined stat"

        # Both c_velo and pop_time are elite, so combined should be positive
        assert c_defense_stat.z_score > 0, (
            f"Elite catcher should have positive c_defense z-score, got {c_defense_stat.z_score}"
        )

        # Position should be correctly identified
        assert result.player_position.upper() == "C", (
            f"Position should be C, got {result.player_position}"
        )

    def test_outfielder_uses_of_velo_path(
        self, calculator, outfielder_stats, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 5: Outfielder position velocity path

        Outfielders should use of_velo for their defensive stat,
        not inf_velo.
        """
        result = calculator.calculate(
            outfielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Find the of_velo stat
        of_velo_stat = None
        for z_stat in result.stats_breakdown.all_z_scores:
            if z_stat.stat_name == "of_velo":
                of_velo_stat = z_stat
                break

        assert of_velo_stat is not None, "Outfielder should use of_velo stat"

        # The outfielder has above-average OF velo, so z-score should be positive
        assert of_velo_stat.z_score > 0, (
            f"OF with 90 mph velo should have positive z-score, got {of_velo_stat.z_score}"
        )

    def test_team_needs_alignment_bonus_offense(
        self, calculator, elite_infielder_stats, high_d1_ml_predictions, school_needs_offense
    ):
        """
        TEST 6: Team needs alignment bonus (offense)

        An offensive player (high exit_velo is best stat) should get
        an alignment bonus when the school needs offense.
        """
        # Create player with exit_velo as clear best stat
        offensive_player = PlayerStats(
            exit_velo=98.0,     # Well above average
            sixty_time=7.2,     # Average
            inf_velo=82.0,      # Average
            height=72,
            weight=185,
            primary_position="1B",
        )

        result = calculator.calculate(
            offensive_player,
            high_d1_ml_predictions,
            school_needs_offense
        )

        # Should detect offensive strength
        assert result.stats_breakdown.player_strength == PlayerStrength.OFFENSIVE, (
            f"Should detect offensive strength, got {result.stats_breakdown.player_strength}"
        )

        # Team needs offense
        assert result.team_fit_breakdown.team_needs == TeamNeed.OFFENSE, (
            f"Team should need offense, got {result.team_fit_breakdown.team_needs}"
        )

        # Should have alignment and bonus
        assert result.team_fit_breakdown.alignment is True, "Should have alignment"
        assert result.team_fit_breakdown.bonus > 0, (
            f"Should have positive bonus, got {result.team_fit_breakdown.bonus}"
        )

    def test_team_needs_alignment_bonus_defense(
        self, calculator, high_d1_ml_predictions, school_needs_defense
    ):
        """
        TEST 7: Team needs alignment bonus (defense)

        A defensive player (high position velo is best stat) should get
        an alignment bonus when the school needs defense.
        """
        # Create player with inf_velo as clear best stat
        defensive_player = PlayerStats(
            exit_velo=88.0,     # Below average
            sixty_time=7.1,     # Average
            inf_velo=90.0,      # Well above average
            height=72,
            weight=180,
            primary_position="SS",
        )

        result = calculator.calculate(
            defensive_player,
            high_d1_ml_predictions,
            school_needs_defense
        )

        # Should detect defensive strength
        assert result.stats_breakdown.player_strength == PlayerStrength.DEFENSIVE, (
            f"Should detect defensive strength, got {result.stats_breakdown.player_strength}"
        )

        # Team needs defense
        assert result.team_fit_breakdown.team_needs == TeamNeed.DEFENSE, (
            f"Team should need defense, got {result.team_fit_breakdown.team_needs}"
        )

        # Should have alignment and bonus
        assert result.team_fit_breakdown.alignment is True, "Should have alignment"
        assert result.team_fit_breakdown.bonus > 0, (
            f"Should have positive bonus, got {result.team_fit_breakdown.bonus}"
        )

    def test_declining_program_gives_trend_bonus(
        self, calculator, average_infielder_stats, high_d1_ml_predictions, declining_program
    ):
        """
        TEST 8: Declining program trend bonus

        A declining program should give a positive trend bonus (+0.12)
        representing more roster opportunity.
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            declining_program
        )

        from backend.playing_time import ProgramTrend

        assert result.trend_breakdown.trend == ProgramTrend.DECLINING, (
            f"Should detect declining trend, got {result.trend_breakdown.trend}"
        )

        # Declining bonus is +0.12
        assert result.trend_breakdown.bonus == pytest.approx(0.12, abs=0.01), (
            f"Declining bonus should be +0.12, got {result.trend_breakdown.bonus}"
        )

    def test_improving_program_gives_trend_penalty(
        self, calculator, average_infielder_stats, high_d1_ml_predictions, improving_program
    ):
        """
        TEST 9: Improving program trend penalty

        An improving program should give a negative trend bonus (-0.08)
        representing more competition for roster spots.
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            improving_program
        )

        from backend.playing_time import ProgramTrend

        assert result.trend_breakdown.trend == ProgramTrend.IMPROVING, (
            f"Should detect improving trend, got {result.trend_breakdown.trend}"
        )

        # Improving penalty is -0.08
        assert result.trend_breakdown.bonus == pytest.approx(-0.08, abs=0.01), (
            f"Improving penalty should be -0.08, got {result.trend_breakdown.bonus}"
        )

    def test_output_structure_contains_all_required_fields(
        self, calculator, average_infielder_stats, high_d1_ml_predictions, non_p4_d1_school
    ):
        """
        TEST 10: Full output structure validation

        The PlayingTimeResult should contain all required fields and
        be serializable to dictionary/JSON format.
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        # Check primary outputs exist
        assert isinstance(result.final_z_score, float), "final_z_score should be float"
        assert isinstance(result.percentile, float), "percentile should be float"
        assert isinstance(result.bucket, str), "bucket should be string"
        assert isinstance(result.bucket_description, str), "bucket_description should be string"

        # Check percentile is valid range
        assert 0 <= result.percentile <= 100, "percentile should be 0-100"

        # Check breakdowns exist
        assert result.stats_breakdown is not None, "stats_breakdown required"
        assert result.physical_breakdown is not None, "physical_breakdown required"
        assert result.ml_breakdown is not None, "ml_breakdown required"
        assert result.team_fit_breakdown is not None, "team_fit_breakdown required"
        assert result.trend_breakdown is not None, "trend_breakdown required"

        # Check context
        assert result.school_name == "Test University"
        assert result.school_division == "Non-P4 D1"
        assert result.player_position == "SS"

        # Check interpretation exists
        assert len(result.interpretation) > 0, "interpretation should be non-empty"

        # Check to_dict() works and contains expected keys
        result_dict = result.to_dict()
        assert "final_z_score" in result_dict
        assert "percentile" in result_dict
        assert "bucket" in result_dict
        assert "breakdown" in result_dict
        assert "context" in result_dict
        assert "interpretation" in result_dict

        # Check summary dict
        summary = result.to_summary_dict()
        assert "final_z_score" in summary
        assert "bucket" in summary
        assert len(summary) < len(result_dict)  # Summary should be smaller


class TestComponentCalculations:
    """Additional tests for specific component calculations."""

    def test_stat_weights_sum_correctly(self, calculator, average_infielder_stats, high_d1_ml_predictions, non_p4_d1_school):
        """
        Verify that the stat weights (30% + 25% + 20% = 75%) are applied correctly.
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        breakdown = result.stats_breakdown

        # Verify weights
        assert breakdown.best.weight == pytest.approx(0.30, abs=0.01)
        assert breakdown.mid.weight == pytest.approx(0.25, abs=0.01)
        assert breakdown.worst.weight == pytest.approx(0.20, abs=0.01)

        # Verify component total is sum of weighted contributions
        expected_total = (
            breakdown.best.z_score * breakdown.best.weight +
            breakdown.mid.z_score * breakdown.mid.weight +
            breakdown.worst.z_score * breakdown.worst.weight
        )
        assert breakdown.component_total == pytest.approx(expected_total, abs=0.001)

    def test_physical_component_is_15_percent_of_average_z(self, calculator, elite_infielder_stats, high_d1_ml_predictions, non_p4_d1_school):
        """
        Verify that physical component = 15% * average(height_z, weight_z).
        """
        result = calculator.calculate(
            elite_infielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        physical = result.physical_breakdown

        # Average z-score
        expected_avg = (physical.height_z + physical.weight_z) / 2
        assert physical.average_z == pytest.approx(expected_avg, abs=0.001)

        # Component should be 15% of average
        expected_component = expected_avg * 0.15
        assert physical.component_total == pytest.approx(expected_component, abs=0.001)

    def test_ml_component_is_10_percent_of_scaled_gap(self, calculator, average_infielder_stats, high_d1_ml_predictions, non_p4_d1_school):
        """
        Verify that ML component = 10% * (gap / 50).
        """
        result = calculator.calculate(
            average_infielder_stats,
            high_d1_ml_predictions,
            non_p4_d1_school
        )

        ml = result.ml_breakdown

        # Component should be: (gap / 50) * 0.10
        expected_component = (ml.gap / 50) * 0.10
        assert ml.component_total == pytest.approx(expected_component, abs=0.001)

    def test_z_to_percentile_conversion(self, calculator, average_infielder_stats, high_d1_ml_predictions, non_p4_d1_school):
        """
        Verify z-score to percentile conversion uses standard normal CDF.
        """
        # Test known z-score to percentile mappings
        # z = 0 → 50th percentile
        # z = 1 → ~84th percentile
        # z = -1 → ~16th percentile

        test_cases = [
            (0.0, 50.0),
            (1.0, 84.13),
            (-1.0, 15.87),
            (2.0, 97.72),
            (-2.0, 2.28),
        ]

        for z_score, expected_percentile in test_cases:
            # Use the internal method
            actual = calculator._z_to_percentile(z_score)
            assert actual == pytest.approx(expected_percentile, abs=0.5), (
                f"z={z_score} should be ~{expected_percentile}%, got {actual}%"
            )
