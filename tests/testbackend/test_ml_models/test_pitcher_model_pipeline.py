import pytest
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend/ml'))
from backend.ml.pipeline.pitcher_pipeline import PitcherPredictionPipeline
from backend.utils.player_types import PlayerPitcher


@pytest.fixture(scope="module")
def pipeline():
    return PitcherPredictionPipeline()


def test_high_performer(pipeline):
    player = PlayerPitcher(
        height=75,
        weight=205,
        primary_position="RHP",
        throwing_hand="R",
        region="West",
        fastball_velo_max=94.0,
        fastball_velo_range=90.0,
        fastball_spin=2300.0,
        changeup_velo=82.0,
        changeup_spin=1800.0,
        curveball_velo=76.0,
        curveball_spin=2400.0,
        slider_velo=80.0,
        slider_spin=2400.0,
    )
    result = pipeline.predict(player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert 0.0 <= result.d1_results.d1_probability <= 1.0


def test_average_performer(pipeline):
    player = PlayerPitcher(
        height=73,
        weight=185,
        primary_position="RHP",
        throwing_hand="R",
        region="South",
        fastball_velo_max=87.0,
        fastball_velo_range=85.0,
    )
    result = pipeline.predict(player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert 0.0 <= result.d1_results.d1_probability <= 1.0


def test_low_performer(pipeline):
    player = PlayerPitcher(
        height=70,
        weight=170,
        primary_position="LHP",
        throwing_hand="L",
        region="Midwest",
        fastball_velo_max=80.0,
        fastball_velo_range=78.0,
    )
    result = pipeline.predict(player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert 0.0 <= result.d1_results.d1_probability <= 1.0


def test_different_positions(pipeline):
    for pos in ["RHP", "LHP"]:
        player = PlayerPitcher(
            height=73,
            weight=190,
            primary_position=pos,
            throwing_hand="R",
            region="South",
            fastball_velo_max=88.0,
            fastball_velo_range=85.0,
        )
        result = pipeline.predict(player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]


def test_different_regions(pipeline):
    for region in ["West", "South", "Northeast", "Midwest"]:
        player = PlayerPitcher(
            height=73,
            weight=190,
            primary_position="RHP",
            throwing_hand="R",
            region=region,
            fastball_velo_max=88.0,
            fastball_velo_range=85.0,
        )
        result = pipeline.predict(player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]


def test_missing_optional_metrics(pipeline):
    player = PlayerPitcher(
        height=74,
        weight=200,
        primary_position="RHP",
        throwing_hand="R",
        region="West",
        fastball_velo_max=90.0,
    )
    result = pipeline.predict(player)
    assert 0.0 <= result.d1_results.d1_probability <= 1.0


def test_pipeline_structure(pipeline):
    player = PlayerPitcher(
        height=74,
        weight=200,
        primary_position="RHP",
        throwing_hand="R",
        region="West",
        fastball_velo_max=90.0,
        fastball_velo_range=86.0,
    )
    result = pipeline.predict(player)
    assert hasattr(result, "d1_results")
    assert hasattr(result.d1_results, "d1_probability")
    if result.d1_results.d1_prediction:
        assert result.p4_results is not None
        assert 0.0 <= result.p4_results.p4_probability <= 1.0
    else:
        assert result.p4_results is None


def test_invalid_input_type_raises(pipeline):
    with pytest.raises(TypeError):
        pipeline.predict({"bad": "input"})
