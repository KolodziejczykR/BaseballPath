"""
Academic scoring module for BaseballPath V1 evaluation flow.

Computes a composite academic score (1.0–10.0) from GPA, SAT/ACT, and AP courses.
The composite maps against Niche school grades for academic fit matching.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# GPA → Rating (1–10), non-linear mapping
# ---------------------------------------------------------------------------
_GPA_BRACKETS = [
    (3.90, 10),
    (3.70, 9),
    (3.50, 8),
    (3.30, 7),
    (3.00, 6),
    (2.70, 5),
    (2.40, 4),
    (2.00, 3),
    (1.50, 2),
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
    (34, 10),
    (30, 9),
    (27, 8),
    (24, 7),
    (21, 6),
    (19, 5),
    (16, 4),
    (13, 3),
    (10, 2),
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
    (1450, 9),
    (1350, 8),
    (1200, 7),
    (1100, 6),
    (1020, 5),
    (900, 4),
    (800, 3),
    (600, 2),
    (400, 1),
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
# Niche grade → numeric (for school comparison)
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
        composite: float (1.0–10.0)
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

    composite = (gpa_r * 0.40) + (test_r * 0.35) + (ap_r * 0.25)

    return {
        "composite": round(composite, 2),
        "gpa_rating": gpa_r,
        "test_rating": test_r,
        "ap_rating": ap_r,
    }
