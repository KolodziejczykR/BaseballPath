from backend.evaluation.competitiveness import (
    classify_fit,
    compute_school_sci_from_rankings,
    effective_tier,
    final_pci,
    ml_based_pci,
    normalize_hitter_position,
    rank_to_percentile,
    to_national_scale,
)
from backend.evaluation.school_matching import (
    compute_player_pci,
    compute_within_tier_percentile,
    match_and_rank_schools,
)
from backend.utils.school_group_constants import NON_D1, NON_P4_D1, POWER_4_D1


def test_rank_to_percentile_and_band_overlap():
    d1_best = to_national_scale(rank_to_percentile(1, 305), 1)
    d1_worst = to_national_scale(rank_to_percentile(305, 305), 1)
    d2_best = to_national_scale(rank_to_percentile(1, 253), 2)
    d3_best = to_national_scale(rank_to_percentile(1, 388), 3)

    assert d1_best == 100.0
    assert d1_worst == 40.0
    assert d2_best == 43.0
    assert d3_best == 38.0
    assert d2_best > d1_worst  # intentional D1/D2 overlap


def test_school_sci_extremes_within_d1():
    elite_school = {
        "2025": {
            "division": 1,
            "overall_rating": 1,
            "offensive_rating": 2,
            "defensive_rating": 3,
            "power_rating": 2,
        },
        "2024": {
            "division": 1,
            "overall_rating": 4,
            "offensive_rating": 5,
            "defensive_rating": 6,
            "power_rating": 5,
        },
        "2023": {
            "division": 1,
            "overall_rating": 8,
            "offensive_rating": 9,
            "defensive_rating": 10,
            "power_rating": 9,
        },
    }
    weak_school = {
        "2025": {
            "division": 1,
            "overall_rating": 300,
            "offensive_rating": 299,
            "defensive_rating": 298,
            "power_rating": 300,
        },
        "2024": {
            "division": 1,
            "overall_rating": 297,
            "offensive_rating": 296,
            "defensive_rating": 295,
            "power_rating": 297,
        },
        "2023": {
            "division": 1,
            "overall_rating": 294,
            "offensive_rating": 293,
            "defensive_rating": 292,
            "power_rating": 294,
        },
    }

    elite = compute_school_sci_from_rankings(elite_school)
    weak = compute_school_sci_from_rankings(weak_school)

    assert elite["sci_hitter"] is not None and elite["sci_hitter"] > 95
    assert weak["sci_hitter"] is not None and weak["sci_hitter"] < 45


def test_player_pci_uses_ml_pci_directly():
    ml_pci = ml_based_pci(
        predicted_tier=NON_P4_D1,
        within_tier_percentile=72.0,
        d1_prob=0.79,
        p4_prob=None,
    )
    blended = final_pci(ml_pci)

    assert 0 <= ml_pci <= 100
    assert blended == round(ml_pci, 10) or abs(blended - ml_pci) < 1e-9
    assert 0 <= blended <= 100


def test_non_d1_ml_pci_keeps_run_player_below_top_d3():
    """Regression: a 53rd-percentile Non-D1 with d1_prob ~0.12 must not Fit top D3."""
    run_player_pci = ml_based_pci(
        predicted_tier=NON_D1,
        within_tier_percentile=52.7,
        d1_prob=0.116,
        p4_prob=None,
    )
    top_d3_sci = 37.73  # Johns Hopkins
    delta = run_player_pci - top_d3_sci
    assert classify_fit(delta) == "Strong Reach"


def test_non_d1_ml_pci_borderline_can_fit_top_d3():
    """An ~85th-percentile Non-D1 with materially high d1_prob should reach
    top D3 at Reach or Fit (not Strong Reach)."""
    borderline_pci = ml_based_pci(
        predicted_tier=NON_D1,
        within_tier_percentile=72.5,
        d1_prob=0.48,
        p4_prob=None,
    )
    top_d3_sci = 37.73
    delta = borderline_pci - top_d3_sci
    assert classify_fit(delta) in {"Fit", "Safety"}


def test_non_d1_ml_pci_uses_d1_probability_meaningfully():
    """Non-D1 d1_prob nudge must be strong enough to differentiate confident
    Non-D1 players from borderline D1 players at the same percentile."""
    lower_prob = ml_based_pci(
        predicted_tier=NON_D1,
        within_tier_percentile=70.0,
        d1_prob=0.05,
        p4_prob=None,
    )
    higher_prob = ml_based_pci(
        predicted_tier=NON_D1,
        within_tier_percentile=70.0,
        d1_prob=0.45,
        p4_prob=None,
    )

    assert higher_prob > lower_prob
    assert (higher_prob - lower_prob) >= 6.0


def test_effective_tier_demotes_low_confidence_p4():
    """A P4 call at p4_prob < 0.30 should be demoted to Non-P4 D1."""
    assert effective_tier(POWER_4_D1, d1_probability=0.63, p4_probability=0.25) == NON_P4_D1


def test_effective_tier_demotes_borderline_p4():
    """A P4 call at p4_prob just below the 0.30 floor is demoted."""
    assert effective_tier(POWER_4_D1, d1_probability=0.70, p4_probability=0.28) == NON_P4_D1


def test_effective_tier_preserves_confident_p4():
    assert effective_tier(POWER_4_D1, d1_probability=0.92, p4_probability=0.81) == POWER_4_D1


def test_effective_tier_cascades_p4_to_non_d1():
    """A P4 call that also fails the D1 floor should cascade to Non-D1."""
    assert effective_tier(POWER_4_D1, d1_probability=0.30, p4_probability=0.25) == NON_D1


def test_effective_tier_demotes_low_confidence_non_p4_d1():
    assert effective_tier(NON_P4_D1, d1_probability=0.32, p4_probability=0.10) == NON_D1


def test_effective_tier_never_promotes():
    assert effective_tier(NON_D1, d1_probability=0.95, p4_probability=0.85) == NON_D1


def test_fit_classification_thresholds():
    assert classify_fit(9.0) == "Strong Safety"
    assert classify_fit(5.0) == "Safety"
    assert classify_fit(0.0) == "Fit"
    assert classify_fit(-6.0) == "Reach"
    assert classify_fit(-9.0) == "Strong Reach"


def test_match_and_rank_uses_school_sci_delta_not_flat_tier():
    schools = [
        {
            "school_name": "Tennessee",
            "display_school_name": "Tennessee",
            "division_group": NON_P4_D1,
            "school_state": "TN",
            "conference": "SEC",
            "academics_grade": "B",
            "academic_selectivity_score": 6.5,
            "baseball_sci_hitter": 86.0,
            "baseball_trend_bonus": 2.5,
            "out_of_state_tuition": 45000,
        },
        {
            "school_name": "Missouri",
            "display_school_name": "Missouri",
            "division_group": NON_P4_D1,
            "school_state": "MO",
            "conference": "SEC",
            "academics_grade": "B",
            "academic_selectivity_score": 5.5,
            "baseball_sci_hitter": 70.0,
            "baseball_trend_bonus": -0.3,
            "out_of_state_tuition": 35000,
        },
    ]
    player_stats = {
        "primary_position": "OF",
        "exit_velo_max": 89.0,
        "of_velo": 84.0,
        "sixty_time": 6.9,
    }

    results = match_and_rank_schools(
        schools=schools,
        player_stats=player_stats,
        predicted_tier=NON_P4_D1,
        player_pci=78.0,
        academic_composite=6.1,
        is_pitcher=False,
        selected_regions=None,
        max_budget=None,
        user_state=None,
        limit=15,
    )

    by_name = {row["school_name"]: row for row in results}
    assert by_name["Tennessee"]["fit_label"] == "Strong Reach"
    assert by_name["Missouri"]["fit_label"] == "Strong Safety"
    assert by_name["Tennessee"]["display_school_name"] == "Tennessee"
    assert by_name["Missouri"]["display_school_name"] == "Missouri"
    assert by_name["Tennessee"]["delta"] < 0
    assert by_name["Missouri"]["delta"] > 0
    assert by_name["Tennessee"]["academic_selectivity_score"] == 6.5
    assert by_name["Missouri"]["academic_selectivity_score"] == 5.5
    assert "academic_delta" in by_name["Tennessee"]
    assert "academic_delta" in by_name["Missouri"]


def test_non_d1_schools_surface_d2_d3_labels():
    schools = [
        {
            "school_name": "Top D2 Program",
            "division_group": NON_D1,
            "baseball_division": 2,
            "school_state": "FL",
            "academics_grade": "B",
            "baseball_sci_hitter": 42.0,
            "out_of_state_tuition": 30000,
        },
        {
            "school_name": "Top D3 Program",
            "division_group": NON_D1,
            "baseball_division": 3,
            "school_state": "MA",
            "academics_grade": "B",
            "baseball_sci_hitter": 33.0,
            "out_of_state_tuition": 28000,
        },
    ]
    player_stats = {
        "primary_position": "OF",
        "exit_velo_max": 88.0,
        "of_velo": 83.0,
        "sixty_time": 6.95,
    }

    results = match_and_rank_schools(
        schools=schools,
        player_stats=player_stats,
        predicted_tier=NON_D1,
        player_pci=38.0,
        academic_composite=6.0,
        is_pitcher=False,
        selected_regions=None,
        max_budget=None,
        user_state=None,
        limit=15,
    )

    by_name = {row["school_name"]: row for row in results}
    assert by_name["Top D2 Program"]["division_label"] == "Division 2"
    assert by_name["Top D3 Program"]["division_label"] == "Division 3"


def test_unresolved_non_d1_fallback_produces_blank_division_label():
    schools = [
        {
            "school_name": "Unresolved Program",
            "division_group": NON_D1,
            "school_state": "OH",
            "academics_grade": "B",
            "baseball_sci_hitter": 60.0,
            "out_of_state_tuition": 30000,
        },
    ]
    player_stats = {
        "primary_position": "OF",
        "exit_velo_max": 88.0,
        "of_velo": 83.0,
        "sixty_time": 6.95,
    }

    results = match_and_rank_schools(
        schools=schools,
        player_stats=player_stats,
        predicted_tier=NON_D1,
        player_pci=58.0,
        academic_composite=6.0,
        is_pitcher=False,
        selected_regions=None,
        max_budget=None,
        user_state=None,
        limit=15,
    )

    assert results[0]["division_label"] == ""


def test_safety_safety_school_is_not_excluded_but_strong_safety_is():
    schools = [
        {
            "school_name": "Regular Safety",
            "display_school_name": "Regular Safety",
            "division_group": NON_D1,
            "baseball_division": 2,
            "school_state": "FL",
            "academics_grade": "B-",
            "baseball_sci_hitter": 45.0,
            "out_of_state_tuition": 30000,
        },
        {
            "school_name": "Strong Safety",
            "display_school_name": "Strong Safety",
            "division_group": NON_D1,
            "baseball_division": 2,
            "school_state": "GA",
            "academics_grade": "B-",
            "baseball_sci_hitter": 41.0,
            "out_of_state_tuition": 28000,
        },
    ]
    player_stats = {
        "primary_position": "OF",
        "exit_velo_max": 88.0,
        "of_velo": 83.0,
        "sixty_time": 6.95,
    }

    results = match_and_rank_schools(
        schools=schools,
        player_stats=player_stats,
        predicted_tier=NON_D1,
        player_pci=50.0,
        academic_composite=6.0,
        is_pitcher=False,
        selected_regions=None,
        max_budget=None,
        user_state=None,
        limit=15,
    )

    by_name = {row["school_name"]: row for row in results}
    assert by_name["Regular Safety"]["fit_label"] == "Safety"
    assert "Strong Safety" not in by_name


def test_backfill_includes_strong_fit_bands_when_regular_band_is_too_small():
    schools = [
        {
            "school_name": "Only Fit",
            "display_school_name": "Only Fit",
            "division_group": NON_P4_D1,
            "baseball_division": 1,
            "school_state": "MD",
            "academics_grade": "B",
            "academic_selectivity_score": 5.5,
            "baseball_sci_hitter": 50.0,
            "out_of_state_tuition": 30000,
        },
        {
            "school_name": "Strong Safety One",
            "display_school_name": "Strong Safety One",
            "division_group": NON_D1,
            "baseball_division": 2,
            "school_state": "FL",
            "academics_grade": "B",
            "academic_selectivity_score": 5.5,
            "baseball_sci_hitter": 38.0,
            "out_of_state_tuition": 28000,
        },
        {
            "school_name": "Strong Reach One",
            "display_school_name": "Strong Reach One",
            "division_group": NON_P4_D1,
            "baseball_division": 1,
            "school_state": "TN",
            "academics_grade": "B",
            "academic_selectivity_score": 5.5,
            "baseball_sci_hitter": 60.0,
            "out_of_state_tuition": 32000,
        },
    ]

    results = match_and_rank_schools(
        schools=schools,
        player_stats={
            "primary_position": "SS",
            "exit_velo_max": 92.0,
            "inf_velo": 86.0,
            "sixty_time": 6.9,
        },
        predicted_tier=NON_D1,
        player_pci=50.0,
        academic_composite=6.0,
        is_pitcher=False,
        selected_regions=None,
        max_budget=None,
        user_state=None,
        limit=15,
    )

    by_name = {row["school_name"]: row for row in results}
    assert "Only Fit" in by_name
    assert "Strong Safety One" in by_name
    assert "Strong Reach One" in by_name


def test_consideration_pool_reserves_academic_diversity_slots():
    """Consideration pool reserves slots for academically appropriate schools."""
    schools = []
    # 8 schools: baseball fit, academic strong safety (too easy)
    for i in range(8):
        schools.append({
            "school_name": f"AcadSS_{i}",
            "division_group": NON_P4_D1,
            "baseball_division": 1,
            "school_state": "FL",
            "academic_selectivity_score": 3.0,
            "baseball_sci_hitter": 50.0 + i * 0.1,
            "out_of_state_tuition": 30000,
        })
    # 4 schools: baseball fit, academic fit
    for i in range(4):
        schools.append({
            "school_name": f"AcadFit_{i}",
            "division_group": NON_P4_D1,
            "baseball_division": 1,
            "school_state": "GA",
            "academic_selectivity_score": 7.0,
            "baseball_sci_hitter": 50.0 + i * 0.1,
            "out_of_state_tuition": 35000,
        })

    results = match_and_rank_schools(
        schools=schools,
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 90.0,
            "of_velo": 85.0,
            "sixty_time": 6.8,
        },
        predicted_tier=NON_P4_D1,
        player_pci=52.0,
        academic_composite=7.5,
        is_pitcher=False,
        limit=10,
        consideration_pool=True,
    )

    acad_fit_count = sum(1 for r in results if r["academic_fit"] in ("Fit", "Safety", "Reach"))
    assert acad_fit_count >= 4, (
        f"Expected at least 4 academically appropriate schools, got {acad_fit_count}"
    )


def test_consideration_pool_excludes_double_settling():
    """Consideration pool excludes baseball safety + academic strong safety."""
    schools = [
        {
            "school_name": "Good Match",
            "division_group": NON_P4_D1,
            "baseball_division": 1,
            "school_state": "FL",
            "academic_selectivity_score": 7.0,
            "baseball_sci_hitter": 50.0,
            "out_of_state_tuition": 30000,
        },
        {
            "school_name": "Double Settling",
            "division_group": NON_D1,
            "baseball_division": 2,
            "school_state": "GA",
            "academic_selectivity_score": 3.0,
            "baseball_sci_hitter": 46.0,
            "out_of_state_tuition": 25000,
        },
    ]

    results = match_and_rank_schools(
        schools=schools,
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 90.0,
            "of_velo": 85.0,
            "sixty_time": 6.8,
        },
        predicted_tier=NON_P4_D1,
        player_pci=52.0,
        academic_composite=7.5,
        is_pitcher=False,
        limit=15,
        consideration_pool=True,
    )

    by_name = {r["school_name"]: r for r in results}
    assert "Good Match" in by_name
    assert "Double Settling" not in by_name, (
        "Baseball safety + academic strong safety should be excluded from consideration pool"
    )


def test_stat_demotion_p4_outfielder_below_threshold():
    """An OF predicted P4 but with stats well below P4 benchmarks should be
    demoted from P4. Stats here are ~bottom 5% of P4 outfielders."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 85.0,
            "of_velo": 78.0,
            "sixty_time": 7.3,
        },
        predicted_tier=POWER_4_D1,
        d1_probability=0.55,
        p4_probability=0.60,
        is_pitcher=False,
    )
    # Should be demoted out of P4 — tier should NOT be Power 4 D1
    assert result["predicted_tier"] != POWER_4_D1
    # PCI should be well below the P4 band floor of 69
    assert result["player_pci"] < 69.0


def test_stat_demotion_cascade_to_non_d1():
    """An OF predicted P4 with stats below both P4 and Non-P4 D1 benchmarks
    should cascade all the way to Non-D1."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 82.0,
            "of_velo": 74.0,
            "sixty_time": 7.5,
        },
        predicted_tier=POWER_4_D1,
        d1_probability=0.55,
        p4_probability=0.60,
        is_pitcher=False,
    )
    assert result["predicted_tier"] == NON_D1
    assert result["player_pci"] < 45.0


def test_stat_demotion_no_trigger_above_threshold():
    """An OF with solid P4-level stats should NOT be demoted."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 97.0,
            "of_velo": 90.0,
            "sixty_time": 6.7,
        },
        predicted_tier=POWER_4_D1,
        d1_probability=0.90,
        p4_probability=0.80,
        is_pitcher=False,
    )
    assert result["predicted_tier"] == POWER_4_D1
    assert result["player_pci"] >= 69.0


def test_stat_demotion_infielder_uses_position_benchmarks():
    """A MIF predicted P4 should be evaluated against MIF-specific benchmarks,
    not generic hitter benchmarks."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "SS",
            "exit_velo_max": 86.0,
            "inf_velo": 78.0,
            "sixty_time": 7.2,
        },
        predicted_tier=POWER_4_D1,
        d1_probability=0.55,
        p4_probability=0.60,
        is_pitcher=False,
    )
    # SS with these stats should be demoted from P4
    assert result["predicted_tier"] != POWER_4_D1
    assert result["player_pci"] < 69.0


def test_stat_demotion_pitcher_uses_15pct_threshold():
    """Pitchers use a 15% demotion threshold (tighter than hitters' 20%)."""
    # A pitcher at ~18th percentile of P4 should NOT be demoted (above 15%)
    borderline_result = compute_player_pci(
        player_stats={
            "primary_position": "RHP",
            "fastball_velo_max": 87.0,
            "fastball_velo_range": 85.0,
            "fastball_spin": 2050,
        },
        predicted_tier=POWER_4_D1,
        d1_probability=0.70,
        p4_probability=0.65,
        is_pitcher=True,
    )
    # Verify the percentile calculation determines the tier correctly.
    # The exact tier depends on where these stats land against P4 pitcher
    # benchmarks — the key invariant is that the 15% threshold is used.
    pct = compute_within_tier_percentile(
        player_stats={
            "primary_position": "RHP",
            "fastball_velo_max": 87.0,
            "fastball_velo_range": 85.0,
            "fastball_spin": 2050,
        },
        predicted_tier=POWER_4_D1,
        is_pitcher=True,
    )
    if pct >= 15.0:
        assert borderline_result["predicted_tier"] == POWER_4_D1
    else:
        assert borderline_result["predicted_tier"] != POWER_4_D1


def test_stat_demotion_non_p4_d1_to_non_d1():
    """A Non-P4 D1 predicted OF with stats well below Non-P4 D1 benchmarks
    should be demoted to Non-D1."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 82.0,
            "of_velo": 74.0,
            "sixty_time": 7.5,
        },
        predicted_tier=NON_P4_D1,
        d1_probability=0.55,
        p4_probability=None,
        is_pitcher=False,
    )
    assert result["predicted_tier"] == NON_D1
    assert result["player_pci"] < 45.0


def test_stat_demotion_non_p4_d1_no_trigger_above_threshold():
    """A Non-P4 D1 OF with reasonable D1-level stats should NOT be demoted."""
    result = compute_player_pci(
        player_stats={
            "primary_position": "OF",
            "exit_velo_max": 93.0,
            "of_velo": 85.0,
            "sixty_time": 6.95,
        },
        predicted_tier=NON_P4_D1,
        d1_probability=0.70,
        p4_probability=None,
        is_pitcher=False,
    )
    assert result["predicted_tier"] == NON_P4_D1


def test_normalize_hitter_position_handles_catcher_alias():
    assert normalize_hitter_position("C") == "C"
    assert normalize_hitter_position("catcher") == "C"
    assert normalize_hitter_position("OF") == "OF"
    assert normalize_hitter_position("SS") == "IF"


def test_soft_routed_player_capped_at_non_p4_d1():
    """A borderline player (d1_prediction=False) who gets p4_prediction=True
    via soft routing should be capped at Non-P4 D1, not Power 4 D1."""
    from backend.utils.prediction_types import (
        D1PredictionResult, P4PredictionResult, MLPipelineResults,
    )
    from backend.utils.player_types import PlayerOutfielder

    player = PlayerOutfielder(
        height=74, weight=200, primary_position="OF",
        throwing_hand="R", hitting_handedness="R", region="South",
        exit_velo_max=95.0, of_velo=90.0, sixty_time=6.8,
    )
    d1 = D1PredictionResult(
        d1_probability=0.40, d1_prediction=False,
        confidence="Low", model_version="test",
    )
    p4 = P4PredictionResult(
        p4_probability=0.50, p4_prediction=True,
        confidence="Medium", is_elite=False, model_version="test",
    )
    result = MLPipelineResults(player=player, d1_results=d1, p4_results=p4)
    assert result.get_final_prediction() == NON_P4_D1


def test_effective_tier_preserves_calibrated_p4():
    """A P4 call at p4_prob=0.45 (above calibrated floor 0.30) should stay P4."""
    assert effective_tier(POWER_4_D1, d1_probability=0.70, p4_probability=0.45) == POWER_4_D1
