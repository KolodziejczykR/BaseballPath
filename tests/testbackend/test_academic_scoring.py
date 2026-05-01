import pytest

from backend.evaluation.academic_scoring import (
    act_to_rating,
    ap_to_rating,
    compute_academic_score,
    gpa_to_rating,
    sat_to_rating,
)


def test_gpa_anchors_preserved():
    """Anchor floors map to the same legacy ratings."""
    assert gpa_to_rating(3.00) == 5.0
    assert gpa_to_rating(3.30) == 6.0
    assert gpa_to_rating(3.50) == 7.0
    assert gpa_to_rating(3.70) == 8.0
    assert gpa_to_rating(3.85) == 9.0
    assert gpa_to_rating(3.95) == 10.0
    assert gpa_to_rating(2.70) == 4.0
    assert gpa_to_rating(2.40) == 3.0
    assert gpa_to_rating(2.00) == 2.0


def test_gpa_clamps_at_extremes():
    assert gpa_to_rating(4.0) == 10.0
    assert gpa_to_rating(5.0) == 10.0
    assert gpa_to_rating(1.0) == 1.0
    assert gpa_to_rating(0.0) == 1.0


def test_gpa_interpolates_between_anchors():
    """The 3.0 / 3.29 cliff (both rated 5 under old brackets) is fixed."""
    r_30 = gpa_to_rating(3.00)
    r_315 = gpa_to_rating(3.15)
    r_329 = gpa_to_rating(3.29)
    r_330 = gpa_to_rating(3.30)
    assert r_30 == 5.0
    assert r_315 == pytest.approx(5.5, abs=0.01)
    assert r_329 < r_330  # no cliff
    assert r_329 > 5.9


def test_act_anchors_preserved():
    assert act_to_rating(15) == 2.0
    assert act_to_rating(18) == 3.0
    assert act_to_rating(21) == 4.0
    assert act_to_rating(24) == 5.0
    assert act_to_rating(27) == 6.0
    assert act_to_rating(30) == 7.0
    assert act_to_rating(33) == 8.0
    assert act_to_rating(34) == 9.0
    assert act_to_rating(35) == 10.0


def test_act_interpolates_between_anchors():
    """ACT 22 / 23 used to both rate 4 — now they differentiate."""
    assert act_to_rating(21) == 4.0
    assert act_to_rating(22) == pytest.approx(4.33, abs=0.01)
    assert act_to_rating(23) == pytest.approx(4.67, abs=0.01)
    assert act_to_rating(24) == 5.0
    # Above-35 clamps to 10.
    assert act_to_rating(36) == 10.0


def test_sat_anchors_preserved():
    assert sat_to_rating(900) == 2.0
    assert sat_to_rating(1000) == 3.0
    assert sat_to_rating(1100) == 4.0
    assert sat_to_rating(1200) == 5.0
    assert sat_to_rating(1290) == 6.0
    assert sat_to_rating(1370) == 7.0
    assert sat_to_rating(1440) == 8.0
    assert sat_to_rating(1500) == 9.0
    assert sat_to_rating(1550) == 10.0


def test_sat_interpolates_between_anchors():
    r_1200 = sat_to_rating(1200)
    r_1245 = sat_to_rating(1245)
    r_1290 = sat_to_rating(1290)
    assert r_1200 == 5.0
    assert r_1290 == 6.0
    assert r_1200 < r_1245 < r_1290


def test_ap_brackets_unchanged_integer_input():
    """AP courses are integer-valued; brackets stay as-is."""
    assert ap_to_rating(0) == 3
    assert ap_to_rating(1) == 4
    assert ap_to_rating(3) == 6
    assert ap_to_rating(7) == 10
    assert ap_to_rating(20) == 10


def test_compute_academic_score_low_profile_run_user():
    """Regression for the 3.0 GPA / 23 ACT / 0 AP profile from run
    95aefeb8. Composite shifts up slightly vs. the bracketed version
    because ACT 23 now interpolates (4.67 instead of 4)."""
    result = compute_academic_score(gpa=3.0, sat_score=None, act_score=23, ap_courses=0)
    assert result["gpa_rating"] == 5.0
    assert result["test_rating"] == pytest.approx(4.67, abs=0.01)
    assert result["ap_rating"] == 3
    # composite = 5.0*0.4 + 4.67*0.4 + 3*0.2 = 2.0 + 1.868 + 0.6 = 4.468
    assert result["composite"] == pytest.approx(4.47, abs=0.01)
    assert result["effective"] == pytest.approx(4.97, abs=0.01)


def test_compute_academic_score_picks_higher_test_score():
    result = compute_academic_score(gpa=3.50, sat_score=1290, act_score=24, ap_courses=2)
    # SAT 1290 → 6.0, ACT 24 → 5.0; max is 6.0
    assert result["test_rating"] == 6.0


def test_compute_academic_score_differentiates_within_old_bracket():
    """Two students who scored identically under the old brackets now
    receive distinct composites."""
    low = compute_academic_score(gpa=3.00, sat_score=None, act_score=21, ap_courses=0)
    high = compute_academic_score(gpa=3.29, sat_score=None, act_score=23, ap_courses=0)
    assert high["composite"] > low["composite"]
