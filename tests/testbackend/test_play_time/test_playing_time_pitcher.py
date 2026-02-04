"""
Pitcher-specific tests for Playing Time Calculator

Validates that pitcher benchmarks are used and pitcher stats are handled correctly.
"""

from backend.playing_time import PlayingTimeCalculator, PlayerStats, MLPredictions, SchoolData, PITCHER_DIVISION_BENCHMARKS


def _p4_school():
    return SchoolData(
        school_name="P4 University",
        division=1,
        conference="SEC",
        is_power_4=True,
        division_percentile=50.0,
        offensive_rating=100.0,
        defensive_rating=100.0,
        trend="stable",
    )


def _ml_predictions():
    return MLPredictions(
        d1_probability=0.8,
        p4_probability=0.6,
        is_elite=False,
        d1_prediction=True,
        p4_prediction=False,
    )


def test_pitcher_uses_pitcher_benchmarks_near_zero():
    """
    Pitcher stats at division means should yield near-zero z-scores.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]

    stats = PlayerStats(
        primary_position="RHP",
        height=b["height"]["mean"],
        weight=b["weight"]["mean"],
        fb_velo_range=b["FastballVelo Range"]["mean"],
        fb_velo_max=b["FastballVelocity (max)"]["mean"],
        fb_spin=b["FastballSpin Rate (avg)"]["mean"],
        ch_velo=b["Changeup Velo Range"]["mean"],
        ch_spin=b["Changeup Spin Rate (avg)"]["mean"],
        cb_velo=b["Curveball Velo Range"]["mean"],
        cb_spin=b["Curveball Spin Rate (avg)"]["mean"],
        sl_velo=b["Slider Velo Range"]["mean"],
        sl_spin=b["Slider Spin Rate (avg)"]["mean"],
    )

    result = calc.calculate(stats, _ml_predictions(), _p4_school())

    # Pitcher stats should be near 0 at benchmark mean
    for z_stat in result.stats_breakdown.all_z_scores:
        assert -0.3 <= z_stat.z_score <= 0.3, (
            f"Pitcher stat {z_stat.stat_name} should be near 0, got {z_stat.z_score}"
        )


def test_pitcher_stat_list_includes_fastball_metrics():
    """
    Ensure pitcher metrics (fastball) are included in stat z-scores.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]

    stats = PlayerStats(
        primary_position="LHP",
        fb_velo_range=b["FastballVelo Range"]["mean"] + b["FastballVelo Range"]["std"],
    )

    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    stat_names = {s.stat_name for s in result.stats_breakdown.all_z_scores}

    assert "FastballVelo Range" in stat_names
    # Pitcher path should not include hitter exit_velo by default
    assert "exit_velo" not in stat_names


def test_pitcher_strength_classified_as_defensive():
    """
    Pitcher stats map to defensive strength classification.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]

    stats = PlayerStats(
        primary_position="RHP",
        fb_velo_range=b["FastballVelo Range"]["mean"] + 2 * b["FastballVelo Range"]["std"],
    )

    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    assert result.stats_breakdown.player_strength.value == "defensive"


def test_pitcher_missing_stats_do_not_crash_and_zero_impact():
    """
    Missing pitcher stats should not crash and should yield z=0 for those stats.
    """
    calc = PlayingTimeCalculator()
    stats = PlayerStats(primary_position="RHP")
    result = calc.calculate(stats, _ml_predictions(), _p4_school())

    # All pitcher stats are missing; z-scores should be 0
    for z_stat in result.stats_breakdown.all_z_scores:
        assert z_stat.z_score == 0.0


def test_pitcher_uses_pitcher_benchmarks_not_hitter_exit_velo():
    """
    Pitcher path should ignore hitter exit_velo and still work.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]
    stats = PlayerStats(
        primary_position="RHP",
        exit_velo=120.0,  # should be ignored for pitcher path
        fb_velo_range=b["FastballVelo Range"]["mean"],
        fb_velo_max=b["FastballVelocity (max)"]["mean"],
    )

    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    stat_names = {s.stat_name for s in result.stats_breakdown.all_z_scores}

    assert "exit_velo" not in stat_names
    assert "FastballVelo Range" in stat_names


def test_pitcher_physical_component_uses_height_weight():
    """
    Physical component should reflect pitcher height/weight against division benchmarks.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]
    stats = PlayerStats(
        primary_position="LHP",
        height=b["height"]["mean"] + b["height"]["std"],
        weight=b["weight"]["mean"] + b["weight"]["std"],
    )

    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    assert result.physical_breakdown.height_z > 0
    assert result.physical_breakdown.weight_z > 0


def test_pitcher_team_needs_alignment_bonus_defense():
    """
    If team needs defense and pitcher strength is defensive, a bonus should be applied.
    """
    calc = PlayingTimeCalculator()
    b = PITCHER_DIVISION_BENCHMARKS["P4"]

    stats = PlayerStats(
        primary_position="RHP",
        fb_velo_range=b["FastballVelo Range"]["mean"] + 2 * b["FastballVelo Range"]["std"],
    )

    school = SchoolData(
        school_name="Defense-Need U",
        division=1,
        conference="SEC",
        is_power_4=True,
        division_percentile=50.0,
        offensive_rating=110.0,
        defensive_rating=100.0,  # offense weaker -> offense need
        trend="stable",
    )
    # Flip to defense need by making defensive rating worse
    school.defensive_rating = 120.0
    school.offensive_rating = 100.0

    result = calc.calculate(stats, _ml_predictions(), school)
    assert result.team_fit_breakdown.bonus >= 0.05


def test_pitcher_ml_component_changes_with_p4_probability():
    """
    ML component should increase when p4_probability increases (holding school constant).
    """
    calc = PlayingTimeCalculator()
    stats = PlayerStats(primary_position="RHP")
    school = _p4_school()

    low_ml = MLPredictions(d1_probability=0.8, p4_probability=0.2, is_elite=False)
    high_ml = MLPredictions(d1_probability=0.8, p4_probability=0.8, is_elite=False)

    res_low = calc.calculate(stats, low_ml, school)
    res_high = calc.calculate(stats, high_ml, school)

    assert res_high.ml_breakdown.component_total > res_low.ml_breakdown.component_total


def test_pitcher_trend_bonus_applied():
    """
    Trend bonus should apply for declining and improving programs.
    """
    calc = PlayingTimeCalculator()
    stats = PlayerStats(primary_position="RHP")

    school_declining = _p4_school()
    school_declining.trend = "declining"

    school_improving = _p4_school()
    school_improving.trend = "improving"

    res_declining = calc.calculate(stats, _ml_predictions(), school_declining)
    res_improving = calc.calculate(stats, _ml_predictions(), school_improving)

    assert res_declining.trend_breakdown.bonus > res_improving.trend_breakdown.bonus


def test_pitcher_invalid_position_falls_back_to_hitter_path():
    """
    Invalid/unknown position should not use pitcher benchmarks.
    """
    calc = PlayingTimeCalculator()
    stats = PlayerStats(
        primary_position="XYZ",
        exit_velo=95.0,
        sixty_time=6.9,
        inf_velo=85.0,
    )
    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    stat_names = {s.stat_name for s in result.stats_breakdown.all_z_scores}
    assert "exit_velo" in stat_names
    assert "FastballVelo Range" not in stat_names


def test_pitcher_extreme_values_do_not_crash():
    """
    Extreme values should not crash the calculator (z-scores may be large).
    """
    calc = PlayingTimeCalculator()
    stats = PlayerStats(
        primary_position="RHP",
        fb_velo_range=200.0,
        fb_velo_max=200.0,
        fb_spin=6000.0,
        ch_velo=10.0,
        ch_spin=100.0,
        cb_velo=10.0,
        cb_spin=100.0,
        sl_velo=10.0,
        sl_spin=100.0,
        height=100.0,
        weight=400.0,
    )
    result = calc.calculate(stats, _ml_predictions(), _p4_school())
    assert result.final_z_score is not None
