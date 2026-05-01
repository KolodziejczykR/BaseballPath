"""
Academic scoring module for BaseballPath evaluation flow.

Computes a composite academic score (1.0–10.0) from GPA, SAT/ACT, and AP courses,
then adds a +0.5 recruited-athlete admissions boost.  The effective score is
compared against each school's ``academic_selectivity_score`` column for fit
matching.
"""

from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Piecewise-linear rating interpolation
# ---------------------------------------------------------------------------
# GPA, ACT, and SAT ratings are continuous along the domain rather than
# bracketed in steps. Anchors below preserve the historical bracket floors,
# so the rating at each anchor matches the legacy table; values between
# anchors interpolate linearly. Step brackets created cliffs where, e.g., a
# 3.00 and a 3.29 GPA both rated 5/10 — linear interpolation differentiates
# them while preserving the same scale and downstream composite weighting.
def _interpolate_rating(value: float, anchors: List[Tuple[float, float]]) -> float:
    if value <= anchors[0][0]:
        return float(anchors[0][1])
    if value >= anchors[-1][0]:
        return float(anchors[-1][1])
    for (x1, y1), (x2, y2) in zip(anchors, anchors[1:]):
        if x1 <= value <= x2:
            if x2 == x1:
                return float(y1)
            t = (value - x1) / (x2 - x1)
            return float(y1) + t * (float(y2) - float(y1))
    return float(anchors[-1][1])


# ---------------------------------------------------------------------------
# GPA → Rating (1–10)
# ---------------------------------------------------------------------------
_GPA_ANCHORS: List[Tuple[float, float]] = [
    (1.00, 1),
    (2.00, 2),
    (2.40, 3),
    (2.70, 4),
    (3.00, 5),
    (3.30, 6),
    (3.50, 7),
    (3.70, 8),
    (3.85, 9),
    (3.95, 10),
]


def gpa_to_rating(gpa: float) -> float:
    return round(_interpolate_rating(float(gpa), _GPA_ANCHORS), 2)


# ---------------------------------------------------------------------------
# ACT → Rating (1–10)
# ---------------------------------------------------------------------------
_ACT_ANCHORS: List[Tuple[float, float]] = [
    (1, 1),
    (15, 2),
    (18, 3),
    (21, 4),
    (24, 5),
    (27, 6),
    (30, 7),
    (33, 8),
    (34, 9),
    (35, 10),
]


def act_to_rating(act: int) -> float:
    return round(_interpolate_rating(float(act), _ACT_ANCHORS), 2)


# ---------------------------------------------------------------------------
# SAT → Rating (1–10)
# ---------------------------------------------------------------------------
_SAT_ANCHORS: List[Tuple[float, float]] = [
    (400, 1),
    (900, 2),
    (1000, 3),
    (1100, 4),
    (1200, 5),
    (1290, 6),
    (1370, 7),
    (1440, 8),
    (1500, 9),
    (1550, 10),
]


def sat_to_rating(sat: int) -> float:
    return round(_interpolate_rating(float(sat), _SAT_ANCHORS), 2)


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
        gpa_rating: float
        test_rating: float
        ap_rating: int
    """
    gpa_r = gpa_to_rating(gpa)

    # Use the higher resulting rating if both provided
    test_r: float = 1.0
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
        "gpa_rating": round(gpa_r, 2),
        "test_rating": round(test_r, 2),
        "ap_rating": ap_r,
    }
