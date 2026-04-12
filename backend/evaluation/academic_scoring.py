"""
Academic scoring module for BaseballPath evaluation flow.

Computes a composite academic score (1.0–10.0) from GPA, SAT/ACT, and AP courses,
then adds a +0.5 recruited-athlete admissions boost.  The effective score is
compared against each school's ``academic_selectivity_score`` column for fit
matching.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# GPA → Rating (1–10)
# ---------------------------------------------------------------------------
_GPA_BRACKETS = [
    (3.95, 10),
    (3.85, 9),
    (3.70, 8),
    (3.50, 7),
    (3.30, 6),
    (3.00, 5),
    (2.70, 4),
    (2.40, 3),
    (2.00, 2),
    (0.00, 1),
]


def gpa_to_rating(gpa: float) -> int:
    for floor, rating in _GPA_BRACKETS:
        if gpa >= floor:
            return rating
    return 1


# ---------------------------------------------------------------------------
# ACT → Rating (1–10)
# ---------------------------------------------------------------------------
_ACT_BRACKETS = [
    (35, 10),
    (34, 9),
    (33, 8),
    (30, 7),
    (27, 6),
    (24, 5),
    (21, 4),
    (18, 3),
    (15, 2),
    (1, 1),
]


def act_to_rating(act: int) -> int:
    for floor, rating in _ACT_BRACKETS:
        if act >= floor:
            return rating
    return 1


# ---------------------------------------------------------------------------
# SAT → Rating (1–10)
# ---------------------------------------------------------------------------
_SAT_BRACKETS = [
    (1550, 10),
    (1500, 9),
    (1440, 8),
    (1370, 7),
    (1290, 6),
    (1200, 5),
    (1100, 4),
    (1000, 3),
    (900, 2),
    (0, 1),
]


def sat_to_rating(sat: int) -> int:
    for floor, rating in _SAT_BRACKETS:
        if sat >= floor:
            return rating
    return 1


# ---------------------------------------------------------------------------
# AP Courses → Rating (3–10), floor of 3
# ---------------------------------------------------------------------------
_AP_BRACKETS = [
    (13, 10),
    (12, 10),
    (11, 10),
    (10, 10),
    (9, 10),
    (8, 10),
    (7, 10),
    (6, 9),
    (5, 8),
    (4, 7),
    (3, 6),
    (2, 5),
    (1, 4),
    (0, 3),
]


def ap_to_rating(ap_courses: int) -> int:
    for floor, rating in _AP_BRACKETS:
        if ap_courses >= floor:
            return rating
    return 3


# ---------------------------------------------------------------------------
# Athlete boost — all users are prospective recruits
# ---------------------------------------------------------------------------
ATHLETE_BOOST = 0.5


# ---------------------------------------------------------------------------
# Niche grade → numeric (kept for backward compatibility / display)
# ---------------------------------------------------------------------------
NICHE_GRADE_MAP = {
    "A+": 10, "A": 9, "A-": 8,
    "B+": 7, "B": 6, "B-": 5,
    "C+": 4, "C": 3, "C-": 2,
    "D+": 1, "D": 1, "D-": 1,
    "F": 1,
}


def niche_grade_to_numeric(grade: Optional[str]) -> Optional[int]:
    if not grade:
        return None
    return NICHE_GRADE_MAP.get(grade.strip())


# ---------------------------------------------------------------------------
# Composite academic score
# ---------------------------------------------------------------------------
def compute_academic_score(
    gpa: float,
    sat_score: Optional[int],
    act_score: Optional[int],
    ap_courses: int,
) -> dict:
    """
    Compute composite academic score from student inputs.

    Returns dict with:
        composite: float (1.0–10.0) — raw weighted score
        effective: float — composite + athlete boost (used for matching)
        gpa_rating: int
        test_rating: int
        ap_rating: int
    """
    gpa_r = gpa_to_rating(gpa)

    # Use the higher resulting rating if both provided
    test_r = 1
    if sat_score is not None and act_score is not None:
        test_r = max(sat_to_rating(sat_score), act_to_rating(act_score))
    elif sat_score is not None:
        test_r = sat_to_rating(sat_score)
    elif act_score is not None:
        test_r = act_to_rating(act_score)

    ap_r = ap_to_rating(ap_courses)

    composite = (gpa_r * 0.40) + (test_r * 0.40) + (ap_r * 0.20)

    return {
        "composite": round(composite, 2),
        "effective": round(composite + ATHLETE_BOOST, 2),
        "gpa_rating": gpa_r,
        "test_rating": test_r,
        "ap_rating": ap_r,
    }
