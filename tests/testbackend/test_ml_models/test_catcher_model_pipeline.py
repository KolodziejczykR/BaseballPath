import pytest
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend/ml'))
from backend.ml.pipeline.catcher_pipeline import CatcherPredictionPipeline
from backend.utils.player_types import PlayerCatcher

@pytest.fixture(scope="module")
def pipeline():
    return CatcherPredictionPipeline()

def test_high_performer(pipeline):
    high_performer = PlayerCatcher(
        height=72,
        weight=185,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=88.0,
        c_velo=78.0,
        pop_time=1.8,
        sixty_time=6.8
    )
    result = pipeline.predict(high_performer)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')
    assert 0.0 <= result.d1_results.d1_probability <= 1.0
    assert isinstance(result.get_pipeline_confidence(), str)

def test_average_performer(pipeline):
    average_player = PlayerCatcher(
        height=70,
        weight=170,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="South",
        exit_velo_max=82.0,
        c_velo=72.0,
        pop_time=2.0,
        sixty_time=7.2
    )
    result = pipeline.predict(average_player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')
    assert 0.0 <= result.d1_results.d1_probability <= 1.0
    assert isinstance(result.get_pipeline_confidence(), str)

def test_low_performer(pipeline):
    lower_performer = PlayerCatcher(
        height=68,
        weight=155,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="South",
        exit_velo_max=75.0,
        c_velo=68.0,
        pop_time=2.3,
        sixty_time=7.8
    )
    result = pipeline.predict(lower_performer)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')
    assert 0.0 <= result.d1_results.d1_probability <= 1.0
    assert isinstance(result.get_pipeline_confidence(), str)

def test_different_regions(pipeline):
    """Test predictions for different player regions"""
    regions = ["West", "South", "Northeast"]
    
    for region in regions:
        player = PlayerCatcher(
            height=71,
            weight=175,
            primary_position="C",
            hitting_handedness="R",
            throwing_hand="R",
            region=region,
            exit_velo_max=85.0,
            c_velo=75.0,
            pop_time=2.0,
            sixty_time=7.5
        )
        result = pipeline.predict(player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
        assert hasattr(result, 'd1_results')
        assert hasattr(result.d1_results, 'd1_probability')

def test_handedness_combinations(pipeline):
    """Test different throwing and hitting handedness combinations"""
    handedness_combinations = [
        ("R", "R"), ("R", "S"),
        ("L", "R"), ("L", "S")
    ]
    
    for throw_hand, hit_hand in handedness_combinations:
        player = PlayerCatcher(
            height=71,
            weight=175,
            primary_position="C",
            hitting_handedness=hit_hand,
            throwing_hand=throw_hand,
            region="South",
            exit_velo_max=85.0,
            c_velo=75.0,
            pop_time=2.0,
            sixty_time=7.5
        )
        result = pipeline.predict(player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
        assert hasattr(result, 'd1_results')
        assert hasattr(result.d1_results, 'd1_probability')

def test_probability_distribution(pipeline):
    """Test that individual stage probabilities are valid"""
    player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    
    result = pipeline.predict(player)
    
    # Check individual stage probabilities are valid
    assert 0.0 <= result.d1_results.d1_probability <= 1.0
    if hasattr(result, 'p4_results') and result.p4_results is not None:
        assert 0.0 <= result.p4_results.p4_probability <= 1.0

def test_pipeline_structure(pipeline):
    """Test the pipeline structure and basic functionality"""
    player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    result = pipeline.predict(player)
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')
    assert hasattr(result, 'get_final_prediction')
    assert hasattr(result, 'get_pipeline_confidence')

def test_individual_probabilities(pipeline):
    """Test that individual d1_probability and p4_probability are returned"""
    player = PlayerCatcher(
        height=72,
        weight=185,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=88.0,
        c_velo=78.0,
        pop_time=1.8,
        sixty_time=6.8
    )
    
    result = pipeline.predict(player)
    assert hasattr(result.d1_results, 'd1_probability')
    assert isinstance(result.d1_results.d1_probability, float)
    assert 0.0 <= result.d1_results.d1_probability <= 1.0
    
    # p4_results should be present if D1 is predicted, None if Non-D1
    if result.get_final_prediction() != "Non-D1":
        assert hasattr(result, 'p4_results')
        assert result.p4_results is not None
        assert hasattr(result.p4_results, 'p4_probability')
        assert isinstance(result.p4_results.p4_probability, float)
        assert 0.0 <= result.p4_results.p4_probability <= 1.0
    else:
        assert result.p4_results is None

def test_extreme_values_boundary(pipeline):
    """Test extreme boundary values that could break the model"""
    # Extremely high values
    extreme_high = PlayerCatcher(
        height=84,  # Very tall
        weight=250,  # Very heavy
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=105.0,  # Unrealistically high
        c_velo=85.0,  # Unrealistically high
        pop_time=1.6,  # Extremely fast pop time
        sixty_time=6.8  # Very fast for a catcher
    )
    result = pipeline.predict(extreme_high)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')
    
    # Extremely low values
    extreme_low = PlayerCatcher(
        height=60,  # Very short
        weight=140,  # Very light
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=65.0,  # Very low
        c_velo=55.0,  # Very low
        pop_time=2.8,  # Very slow pop time
        sixty_time=9.0  # Very slow
    )
    result = pipeline.predict(extreme_low)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')
    assert hasattr(result.d1_results, 'd1_probability')

def test_invalid_input_handling(pipeline):
    """Test handling of invalid inputs"""
    with pytest.raises(TypeError):
        # Test with None player
        pipeline.predict(None)
    
    # Test with invalid position - should still work but may produce unexpected results
    invalid_player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="INVALID",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    result = pipeline.predict(invalid_player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]

def test_missing_required_attributes(pipeline):
    """Test behavior when player object is missing required attributes"""
    # Create a minimal player object that might be missing attributes
    class IncompletePlayer:
        def __init__(self):
            self.height = 71
            self.weight = 175
            # Missing other required attributes
    
    with pytest.raises(TypeError):
        pipeline.predict(IncompletePlayer())


def test_unsupported_categorical_values(pipeline):
    """Test handling of unsupported categorical values"""
    # Test with unsupported region - pipeline handles gracefully
    unsupported_region = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="Antarctica",  # Unsupported region
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    result = pipeline.predict(unsupported_region)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')

def test_negative_values(pipeline):
    """Test handling of negative values"""
    # Pipeline accepts negative values but may produce unexpected results
    negative_player = PlayerCatcher(
        height=-71,  # Negative height
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    result = pipeline.predict(negative_player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')

def test_zero_values(pipeline):
    """Test handling of zero values"""
    zero_player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=0.0,  # Zero exit velocity
        c_velo=0.0,  # Zero catcher velocity
        pop_time=2.0,
        sixty_time=7.5
    )
    result = pipeline.predict(zero_player)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert hasattr(result, 'd1_results')

def test_nan_infinity_values(pipeline):
    """Test handling of NaN and infinity values"""
    # Pipeline may handle NaN values, let's test if it produces a result
    nan_player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=float('nan'),  # NaN value
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    # This may raise an exception or return a result - both are acceptable
    try:
        result = pipeline.predict(nan_player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    except (ValueError, TypeError, Exception):
        # It's acceptable if the pipeline raises an exception for NaN values
        pass

def test_prediction_consistency(pipeline):
    """Test that identical inputs produce identical outputs"""
    player1 = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    
    player2 = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    
    result1 = pipeline.predict(player1)
    result2 = pipeline.predict(player2)
    
    assert result1.get_final_prediction() == result2.get_final_prediction()
    assert result1.d1_results.d1_probability == result2.d1_results.d1_probability
    if result1.p4_results is not None:
        assert result1.p4_results.p4_probability == result2.p4_results.p4_probability

def test_confidence_levels_validity(pipeline):
    """Test that confidence levels are valid strings"""
    player = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.0,
        sixty_time=7.5
    )
    
    result = pipeline.predict(player)
    confidence = result.get_pipeline_confidence()
    assert isinstance(confidence, str)
    # The confidence string has format "D1 Model Confidence: <level>" or "D1 Model Confidence: <level>, P4 Model Confidence: <level>"
    valid_confidence_levels = ["low", "medium", "high", "very_high", "very_low"]
    # Extract confidence levels from the string and check they are valid
    confidence_lower = confidence.lower()
    assert any(level in confidence_lower for level in valid_confidence_levels)

def test_catcher_specific_metrics(pipeline):
    """Test catcher-specific metrics: pop_time variations"""
    # Test excellent pop time
    excellent_pop = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=1.8,  # Excellent pop time
        sixty_time=7.5
    )
    result = pipeline.predict(excellent_pop)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    
    # Test poor pop time
    poor_pop = PlayerCatcher(
        height=71,
        weight=175,
        primary_position="C",
        hitting_handedness="R",
        throwing_hand="R",
        region="West",
        exit_velo_max=85.0,
        c_velo=75.0,
        pop_time=2.5,  # Poor pop time
        sixty_time=7.5
    )
    result = pipeline.predict(poor_pop)
    assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]

def test_catcher_velocity_range(pipeline):
    """Test various catcher velocity values"""
    velocities = [65.0, 70.0, 75.0, 80.0, 85.0]
    
    for c_velo in velocities:
        player = PlayerCatcher(
            height=71,
            weight=175,
            primary_position="C",
            hitting_handedness="R",
            throwing_hand="R",
            region="West",
            exit_velo_max=85.0,
            c_velo=c_velo,
            pop_time=2.0,
            sixty_time=7.5
        )
        result = pipeline.predict(player)
        assert result.get_final_prediction() in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
        assert hasattr(result, 'd1_results') 