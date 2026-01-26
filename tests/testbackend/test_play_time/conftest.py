"""
Shared fixtures for playing time calculator tests.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path.parent))

from backend.playing_time import (
    PlayingTimeCalculator,
    PlayerStats,
    MLPredictions,
    SchoolData,
    DIVISION_BENCHMARKS,
)


@pytest.fixture
def calculator():
    """Create a fresh PlayingTimeCalculator instance."""
    return PlayingTimeCalculator()


@pytest.fixture
def average_infielder_stats():
    """
    A perfectly average infielder for Non-P4 D1.
    All stats at division mean should produce z-scores near 0.
    """
    return PlayerStats(
        exit_velo=92.0,     # Non-P4 D1 mean
        sixty_time=7.0,     # Non-P4 D1 mean
        inf_velo=83.0,      # Non-P4 D1 mean
        height=72,          # Non-P4 D1 mean
        weight=185,         # Non-P4 D1 mean
        primary_position="SS",
    )


@pytest.fixture
def elite_infielder_stats():
    """
    An elite infielder with stats 1-2 standard deviations above P4 mean.
    Should produce high positive z-scores at any level.
    """
    return PlayerStats(
        exit_velo=100.0,    # P4 mean (96) + 1 std (4)
        sixty_time=6.5,     # P4 mean (6.75) - 1.4 std (faster is better)
        inf_velo=91.0,      # P4 mean (87) + 1.1 std
        height=74,          # Above average
        weight=200,         # Above average
        primary_position="SS",
    )


@pytest.fixture
def below_average_player():
    """
    A player with stats below division average.
    Should produce negative z-scores.
    """
    return PlayerStats(
        exit_velo=84.0,     # Below D3 mean
        sixty_time=7.5,     # Slow for all divisions
        inf_velo=75.0,      # Below D3 mean
        height=69,          # Short
        weight=165,         # Light
        primary_position="2B",
    )


@pytest.fixture
def elite_catcher_stats():
    """
    An elite catcher with excellent arm and pop time.
    Tests the 60/40 weighted average for catchers.
    """
    return PlayerStats(
        exit_velo=95.0,
        sixty_time=7.1,     # Catchers can be slower
        c_velo=86.0,        # P4 mean (83) + 1 std
        pop_time=1.88,      # P4 mean (1.95) - 1 std (faster is better)
        height=73,
        weight=200,
        primary_position="C",
    )


@pytest.fixture
def outfielder_stats():
    """
    A solid outfielder for testing OF velocity path.
    """
    return PlayerStats(
        exit_velo=94.0,
        sixty_time=6.85,
        of_velo=90.0,       # Non-P4 D1 mean (86) + 1.1 std
        height=73,
        weight=195,
        primary_position="CF",
    )


@pytest.fixture
def high_d1_ml_predictions():
    """
    ML predictions for a high-level D1 player (Non-P4).
    """
    return MLPredictions(
        d1_probability=0.78,
        p4_probability=0.25,
        is_elite=False,
        d1_prediction=True,
        p4_prediction=False,
    )


@pytest.fixture
def elite_p4_ml_predictions():
    """
    ML predictions for an elite P4 player.
    """
    return MLPredictions(
        d1_probability=0.95,
        p4_probability=0.85,
        is_elite=True,
        d1_prediction=True,
        p4_prediction=True,
    )


@pytest.fixture
def low_d1_ml_predictions():
    """
    ML predictions for a borderline D1/D2 player.
    """
    return MLPredictions(
        d1_probability=0.45,
        p4_probability=0.10,
        is_elite=False,
        d1_prediction=False,
        p4_prediction=False,
    )


@pytest.fixture
def d2_level_ml_predictions():
    """
    ML predictions for a D2 level player.
    """
    return MLPredictions(
        d1_probability=0.25,
        p4_probability=0.0,
        is_elite=False,
        d1_prediction=False,
        p4_prediction=False,
    )


@pytest.fixture
def non_p4_d1_school():
    """
    A mid-tier Non-P4 D1 school with balanced team needs.
    """
    return SchoolData(
        school_name="Test University",
        division=1,
        conference="Big South",
        is_power_4=False,
        division_percentile=50.0,
        offensive_rating=150.0,
        defensive_rating=150.0,  # Balanced
        trend="stable",
    )


@pytest.fixture
def p4_school():
    """
    A mid-tier P4 school.
    """
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


@pytest.fixture
def top_p4_school():
    """
    A top-tier P4 school (like Vanderbilt or LSU).
    """
    return SchoolData(
        school_name="Elite P4 University",
        division=1,
        conference="SEC",
        is_power_4=True,
        division_percentile=95.0,
        offensive_rating=10.0,   # Very good (lower is better)
        defensive_rating=15.0,
        trend="stable",
    )


@pytest.fixture
def d2_school():
    """
    A mid-tier D2 school.
    """
    return SchoolData(
        school_name="D2 State University",
        division=2,
        is_power_4=False,
        division_percentile=50.0,
        offensive_rating=200.0,
        defensive_rating=200.0,
        trend="stable",
    )


@pytest.fixture
def d3_school():
    """
    A mid-tier D3 school.
    """
    return SchoolData(
        school_name="D3 College",
        division=3,
        is_power_4=False,
        division_percentile=50.0,
        offensive_rating=250.0,
        defensive_rating=250.0,
        trend="stable",
    )


@pytest.fixture
def school_needs_offense():
    """
    A school with weak offense (needs offensive players).
    Higher offensive_rating = worse offense in Massey.
    """
    return SchoolData(
        school_name="Weak Offense U",
        division=1,
        is_power_4=False,
        division_percentile=45.0,
        offensive_rating=180.0,  # Weak offense (higher = worse)
        defensive_rating=120.0,  # Good defense (lower = better)
        trend="stable",
    )


@pytest.fixture
def school_needs_defense():
    """
    A school with weak defense (needs defensive players).
    """
    return SchoolData(
        school_name="Weak Defense U",
        division=1,
        is_power_4=False,
        division_percentile=55.0,
        offensive_rating=120.0,  # Good offense
        defensive_rating=180.0,  # Weak defense
        trend="stable",
    )


@pytest.fixture
def declining_program():
    """
    A declining program (more roster opportunity).
    """
    return SchoolData(
        school_name="Declining Program U",
        division=1,
        is_power_4=False,
        division_percentile=30.0,
        offensive_rating=200.0,
        defensive_rating=210.0,
        trend="declining",
        trend_change=25.0,
        trend_years="2023-2025",
    )


@pytest.fixture
def improving_program():
    """
    An improving program (more competition).
    """
    return SchoolData(
        school_name="Rising Program U",
        division=1,
        is_power_4=False,
        division_percentile=65.0,
        offensive_rating=100.0,
        defensive_rating=110.0,
        trend="improving",
        trend_change=-30.0,
        trend_years="2023-2025",
    )
