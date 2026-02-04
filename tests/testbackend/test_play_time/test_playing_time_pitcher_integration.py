"""
End-to-end integration test for pitcher pipeline -> playing time calculation.
"""

from backend.ml.pipeline.pitcher_pipeline import PitcherPredictionPipeline
from backend.utils.player_types import PlayerPitcher
from backend.playing_time import create_playing_time_inputs, PlayingTimeCalculator


def test_pitcher_pipeline_to_playing_time_end_to_end():
    pipeline = PitcherPredictionPipeline()
    player = PlayerPitcher(
        height=74,
        weight=200,
        primary_position="RHP",
        throwing_hand="R",
        region="West",
        fastball_velo_max=90.0,
        fastball_velo_range=86.0,
        fastball_spin=2200.0,
    )

    ml_results = pipeline.predict(player)

    # Minimal school data for playing time
    school_data = {
        "school_name": "Test University",
        "division_group": "Non-P4 D1",
        "division": 1,
        "conference": "Big South",
        "division_percentile": 50.0,
    }

    player_stats, ml_predictions, school_context = create_playing_time_inputs(
        player=ml_results.player,
        ml_results=ml_results,
        school_data=school_data,
        baseball_strength=None,
    )

    calculator = PlayingTimeCalculator()
    result = calculator.calculate(player_stats, ml_predictions, school_context)

    assert result.final_z_score is not None
    assert result.bucket is not None
    assert result.percentile is not None
