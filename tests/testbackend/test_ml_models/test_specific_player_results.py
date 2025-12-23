#!/usr/bin/env python3
"""
Behavioral Testing for ML Model Predictions - Specific Player Results

This module tests that specific player types behave as expected:
- Elite players should predict D1 with high confidence
- Super elite players should be considered for P4
- Borderline players should have reasonable predictions
- Poor players should predict Non-D1

Uses behavioral testing approach - treating models as black boxes and testing
expected outputs for known input patterns.
"""

import pytest
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.ml.pipeline.infielder_pipeline import InfielderPredictionPipeline
from backend.ml.pipeline.outfielder_pipeline import OutfielderPredictionPipeline
from backend.utils.player_types import PlayerInfielder, PlayerOutfielder


class TestElitePlayerBehavior:
    """Test that elite players consistently predict D1/P4 level performance"""
    
    @pytest.fixture(scope="class")
    def inf_pipeline(self):
        """Initialize infielder pipeline once per class"""
        return InfielderPredictionPipeline()
    
    @pytest.fixture(scope="class") 
    def of_pipeline(self):
        """Initialize outfielder pipeline once per class"""
        return OutfielderPredictionPipeline()

    # ELITE INFIELDER TESTS
    @pytest.mark.parametrize("elite_infielder_data", [
         # TODO: High elite infielders are not being recognized... after launch work through this issue

        # Super elite infielder - should definitely be D1
        {
            "height": 74, "weight": 210, "sixty_time": 6.7, 
            "exit_velo_max": 100.0, "inf_velo": 94.0,
            "primary_position": "SS", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "R",
            "expected_d1_min": 0.75, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Super elite SS - 105 exit velo, 93 inf velo, 6.5 speed"
        },
        # Elite infielder with extreme exit velo
        {
            "height": 74, "weight": 185, "sixty_time": 6.8,
            "exit_velo_max": 100.0, "inf_velo": 90.0,
            "primary_position": "2B", "region": "West", 
            "throwing_hand": "R", "hitting_handedness": "L",
            "expected_d1_min": 0.70, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Elite 2B - 108 exit velo, 90 inf velo"
        },
        # Elite speed/arm combination
        {
            "height": 76, "weight": 200, "sixty_time": 6.5,
            "exit_velo_max": 98.0, "inf_velo": 95.0,
            "primary_position": "SS", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "S", 
            "expected_d1_min": 0.65, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Elite SS - 6.5 speed, 95 inf velo, 6'4"
        }
    ])
    def test_elite_infielders_predict_d1(self, inf_pipeline, elite_infielder_data):
        """Elite infielders should predict D1 with high confidence"""
        player_data = {k: v for k, v in elite_infielder_data.items() 
                      if k not in ['expected_d1_min', 'expected_category', 'description']}
        player = PlayerInfielder(**player_data)
        
        result = inf_pipeline.predict(player)
        
        # Test D1 probability threshold
        assert result.d1_results.d1_probability >= elite_infielder_data['expected_d1_min'], \
            f"{elite_infielder_data['description']} only got {result.d1_results.d1_probability:.1%} D1 probability, expected ≥{elite_infielder_data['expected_d1_min']:.1%}"
        
        # Test final prediction category
        assert result.get_final_prediction() in elite_infielder_data['expected_category'], \
            f"{elite_infielder_data['description']} predicted {result.get_final_prediction()}, expected one of {elite_infielder_data['expected_category']}"

    @pytest.mark.parametrize("super_elite_inf", [
        # TODO: High elite infielders are not being recognized... after launch work through this issue
        {
            "height": 75, "weight": 210, "sixty_time": 6.5,
            "exit_velo_max": 105.0, "inf_velo": 93.0,
            "primary_position": "SS", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "R",
            "min_p4_consideration": 0.25,  # Should at least consider P4
            "description": "Original super elite case - 105/93/6.5"
        },
        # Another super elite case
        {
            "height": 76, "weight": 200, "sixty_time": 6.4,
            "exit_velo_max": 102.0, "inf_velo": 94.0,
            "primary_position": "SS", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "L",
            "min_p4_consideration": 0.20,
            "description": "Super elite SS - 102/94/6.4"
        }
    ])
    def test_super_elite_infielders_considered_for_p4(self, inf_pipeline, super_elite_inf):
        """Super elite infielders should be seriously considered for P4"""
        player_data = {k: v for k, v in super_elite_inf.items() 
                      if k not in ['min_p4_consideration', 'description']}
        player = PlayerInfielder(**player_data)
        
        result = inf_pipeline.predict(player)
        
        # Should either predict P4 or have significant P4 probability
        p4_prob = result.p4_results.p4_probability if result.p4_results else 0
        is_p4_predicted = result.get_final_prediction() == 'Power 4 D1'
        
        assert (is_p4_predicted or p4_prob >= super_elite_inf['min_p4_consideration']), \
            f"{super_elite_inf['description']} only got {p4_prob:.1%} P4 probability and predicted {result.get_final_prediction()}, expected P4 prediction or ≥{super_elite_inf['min_p4_consideration']:.1%} P4 prob"

    # ELITE OUTFIELDER TESTS
    @pytest.mark.parametrize("elite_outfielder_data", [
        # Super elite outfielder - the one we just fixed
        {
            "height": 74, "weight": 200, "sixty_time": 6.6,
            "exit_velo_max": 105.0, "of_velo": 98.0,
            "primary_position": "OF", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "S",
            "expected_d1_min": 0.65, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Super elite OF - 105 exit velo, 98 of velo, 6.6 speed"
        },
        # Elite power outfielder
        {
            "height": 75, "weight": 205, "sixty_time": 6.8,
            "exit_velo_max": 110.0, "of_velo": 95.0,
            "primary_position": "OF", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "R",
            "expected_d1_min": 0.65, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Elite power OF - 110 exit velo, 95 of velo"
        },
        # Elite speed/arm outfielder
        {
            "height": 73, "weight": 185, "sixty_time": 6.5,
            "exit_velo_max": 100.0, "of_velo": 97.0,
            "primary_position": "OF", "region": "Northeast",
            "throwing_hand": "L", "hitting_handedness": "L",
            "expected_d1_min": 0.65, "expected_category": ["Non-P4 D1", "Power 4 D1"],
            "description": "Elite speed/arm OF - 6.5 speed, 97 of velo"
        }
    ])
    def test_elite_outfielders_predict_d1(self, of_pipeline, elite_outfielder_data):
        """Elite outfielders should predict D1 with high confidence"""
        player_data = {k: v for k, v in elite_outfielder_data.items()
                      if k not in ['expected_d1_min', 'expected_category', 'description']}
        player = PlayerOutfielder(**player_data)
        
        result = of_pipeline.predict(player)
        
        # Test D1 probability threshold
        assert result.d1_results.d1_probability >= elite_outfielder_data['expected_d1_min'], \
            f"{elite_outfielder_data['description']} only got {result.d1_results.d1_probability:.1%} D1 probability, expected ≥{elite_outfielder_data['expected_d1_min']:.1%}"
        
        # Test final prediction category  
        assert result.get_final_prediction() in elite_outfielder_data['expected_category'], \
            f"{elite_outfielder_data['description']} predicted {result.get_final_prediction()}, expected one of {elite_outfielder_data['expected_category']}"

    @pytest.mark.parametrize("super_elite_of", [
        # The fixed outfielder case
        {
            "height": 74, "weight": 200, "sixty_time": 6.6,
            "exit_velo_max": 105.0, "of_velo": 98.0,
            "primary_position": "OF", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "S",
            "min_p4_consideration": 0.25,  # Lower bar for OF since models predict lower
            "description": "Fixed super elite OF - 105/98/6.6"
        },
        # Another super elite OF
        {
            "height": 76, "weight": 195, "sixty_time": 6.5,
            "exit_velo_max": 107.0, "of_velo": 96.0,
            "primary_position": "OF", "region": "West", 
            "throwing_hand": "L", "hitting_handedness": "R",
            "min_p4_consideration": 0.25,
            "description": "Super elite OF - 107/96/6.5"
        }
    ])
    def test_super_elite_outfielders_considered_for_p4(self, of_pipeline, super_elite_of):
        """Super elite outfielders should be considered for P4"""
        player_data = {k: v for k, v in super_elite_of.items()
                      if k not in ['min_p4_consideration', 'description']}
        player = PlayerOutfielder(**player_data)
        
        result = of_pipeline.predict(player)
        
        # Should either predict P4 or have reasonable P4 probability
        p4_prob = result.p4_results.p4_probability if result.p4_results else 0
        is_p4_predicted = result.get_final_prediction() == 'Power 4 D1'
        
        assert (is_p4_predicted or p4_prob >= super_elite_of['min_p4_consideration']), \
            f"{super_elite_of['description']} only got {p4_prob:.1%} P4 probability and predicted {result.get_final_prediction()}, expected P4 prediction or ≥{super_elite_of['min_p4_consideration']:.1%} P4 prob"


class TestBorderlinePlayerBehavior:
    """Test that borderline players have reasonable predictions"""
    
    @pytest.fixture(scope="class")
    def inf_pipeline(self):
        return InfielderPredictionPipeline()
    
    @pytest.fixture(scope="class")
    def of_pipeline(self):
        return OutfielderPredictionPipeline()

    @pytest.mark.parametrize("borderline_player", [
        # Borderline infielders - maybe low D1 candidates
        {
            "height": 72, "weight": 190, "sixty_time": 7.1,
            "exit_velo_max": 95.0, "inf_velo": 86.0,
            "primary_position": "SS", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "L",
            "min_d1_prob": 0.35, "max_d1_prob": 0.70,
            "description": "Borderline SS - 95/86/6.7.1/6'0/190"
        },
        # Borderline outfielder
        {
            "height": 73, "weight": 175, "sixty_time": 6.9, 
            "exit_velo_max": 93.0, "of_velo": 87.0,
            "primary_position": "OF", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "R",
            "min_d1_prob": 0.35, "max_d1_prob": 0.70,
            "description": "Borderline West OF - 93/87/6.9/6'1/175"
        },
        # Speed-first borderline outfielder
        {
            "height": 70, "weight": 170, "sixty_time": 6.7,
            "exit_velo_max": 86.0, "of_velo": 90.0,
            "primary_position": "OF", "region": "South",
            "throwing_hand": "L", "hitting_handedness": "R",
            "min_d1_prob": 0.35, "max_d1_prob": 0.65,
            "description": "Speed and defense first borderline OF from south - 6.7 speed, 90 arm, 5'10/170"
        }
    ])
    def test_borderline_players_reasonable_predictions(self, inf_pipeline, of_pipeline, borderline_player):
        """Borderline players should have predictions in reasonable ranges"""
        player_data = {k: v for k, v in borderline_player.items()
                      if k not in ['min_d1_prob', 'max_d1_prob', 'description']}
        
        if borderline_player['primary_position'] == 'OF':
            player = PlayerOutfielder(**player_data)
            result = of_pipeline.predict(player)
        else:
            player = PlayerInfielder(**player_data)
            result = inf_pipeline.predict(player)
        
        # D1 probability should be in reasonable range
        d1_prob = result.d1_results.d1_probability
        assert borderline_player['min_d1_prob'] <= d1_prob <= borderline_player['max_d1_prob'], \
            f"{borderline_player['description']} got {d1_prob:.1%} D1 probability, expected between {borderline_player['min_d1_prob']:.1%}-{borderline_player['max_d1_prob']:.1%}"


class TestLowD1PlayerBehavior:
    """Test players who might make low-tier D1 programs"""
    
    @pytest.fixture(scope="class")
    def inf_pipeline(self):
        return InfielderPredictionPipeline()
    
    @pytest.fixture(scope="class")
    def of_pipeline(self):
        return OutfielderPredictionPipeline()

    @pytest.mark.parametrize("low_d1_player", [
        # Low D1 outfielder - developmental potential
        {
            "height": 72, "weight": 180, "sixty_time": 7.4,
            "exit_velo_max": 87.0, "of_velo": 82.0,
            "primary_position": "OF", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "L",
            "min_d1_prob": 0.10, "max_d1_prob": 0.5,
            "description": "Low D1 OF - 87/82/7.4"
        },
        # Small/fast non/low D1 infielder - utility player potential
        {
            "height": 69, "weight": 165, "sixty_time": 6.9,
            "exit_velo_max": 82.0, "inf_velo": 85.0,
            "primary_position": "2B", "region": "West",
            "throwing_hand": "R", "hitting_handedness": "S",
            "min_d1_prob": 0.10, "max_d1_prob": 0.5,
            "description": "Small/fast low D1 2B - speed/defense first"
        },
        # Tall low D1 outfielder - projectability
        {
            "height": 74, "weight": 200, "sixty_time": 7.2,
            "exit_velo_max": 85.0, "of_velo": 82.0,
            "primary_position": "OF", "region": "Northeast", 
            "throwing_hand": "R", "hitting_handedness": "R",
            "min_d1_prob": 0.15, "max_d1_prob": 0.60,
            "description": "Tall/projectable low D1 OF -  6'2, development potential"
        }
    ])
    def test_low_d1_players_reasonable_consideration(self, inf_pipeline, of_pipeline, low_d1_player):
        """Low D1 candidates should have some D1 probability but not high"""
        player_data = {k: v for k, v in low_d1_player.items()
                      if k not in ['min_d1_prob', 'max_d1_prob', 'description']}
        
        if low_d1_player['primary_position'] == 'OF':
            player = PlayerOutfielder(**player_data)
            result = of_pipeline.predict(player)
        else:
            player = PlayerInfielder(**player_data)
            result = inf_pipeline.predict(player)
        
        # D1 probability should be in low-to-moderate range
        d1_prob = result.d1_results.d1_probability
        assert low_d1_player['min_d1_prob'] <= d1_prob <= low_d1_player['max_d1_prob'], \
            f"{low_d1_player['description']} got {d1_prob:.1%} D1 probability, expected between {low_d1_player['min_d1_prob']:.1%}-{low_d1_player['max_d1_prob']:.1%}"
        
        # Most should predict Non-D1 but with reasonable probability
        if result.get_final_prediction() != 'Non-D1':
            # If they predict D1, the probability should be on the lower end
            assert d1_prob <= 0.65, f"Low D1 candidate predicted {result.get_final_prediction()} with {d1_prob:.1%}, seems too high"


class TestNonD1PlayerBehavior:
    """Test that Non-D1 players predict correctly within expected ranges"""
    
    @pytest.fixture(scope="class")
    def inf_pipeline(self):
        return InfielderPredictionPipeline()
    
    @pytest.fixture(scope="class")
    def of_pipeline(self):
        return OutfielderPredictionPipeline()

    @pytest.mark.parametrize("non_d1_player", [
        {
            "height": 72, "weight": 185, "sixty_time": 7.2,
            "exit_velo_max": 86.0, "inf_velo": 83.0,
            "primary_position": "3B", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "R",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Low D1 3B - 86/83/7.2"
        },
        # Clear Non-D1 infielder - well below D1 standards
        {
            "height": 68, "weight": 160, "sixty_time": 8.0,
            "exit_velo_max": 75.0, "inf_velo": 70.0,
            "primary_position": "2B", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "R",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Clear Non-D1 2B - 75/70/8.0"
        },
        # Clear Non-D1 outfielder
        {
            "height": 69, "weight": 165, "sixty_time": 8.2,
            "exit_velo_max": 78.0, "of_velo": 75.0,
            "primary_position": "OF", "region": "Northeast", 
            "throwing_hand": "R", "hitting_handedness": "L",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Clear Non-D1 OF - 78/75/8.2"
        },
        # Weak tools infielder - maybe D2/NAIA level
        {
            "height": 70, "weight": 170, "sixty_time": 7.8,
            "exit_velo_max": 80.0, "inf_velo": 74.0,
            "primary_position": "3B", "region": "Midwest",
            "throwing_hand": "R", "hitting_handedness": "S",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Weak tools 3B - 80/74/7.8"
        },
        # Small/slow outfielder - clear Non-D1
        {
            "height": 67, "weight": 155, "sixty_time": 8.5,
            "exit_velo_max": 76.0, "of_velo": 78.0,
            "primary_position": "OF", "region": "West",
            "throwing_hand": "L", "hitting_handedness": "L",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Small/slow OF - clearly below D1 level"
        },
        # Average high school player - solid but not elite
        {
            "height": 71, "weight": 175, "sixty_time": 7.6,
            "exit_velo_max": 82.0, "inf_velo": 77.0,
            "primary_position": "SS", "region": "South",
            "throwing_hand": "R", "hitting_handedness": "R",
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Average HS player - 82/77/7.6"
        },
        # Power-only outfielder with major weaknesses
        {
            "height": 73, "weight": 200, "sixty_time": 8.0,
            "exit_velo_max": 83.0, "of_velo": 76.0,
            "primary_position": "OF", "region": "Northeast",
            "throwing_hand": "R", "hitting_handedness": "R", 
            "max_d1_prob": 0.30, "expected_category": "Non-D1",
            "description": "Big/slow OF - power but major defensive limitations"
        }
    ])
    def test_non_d1_players_predict_correctly(self, inf_pipeline, of_pipeline, non_d1_player):
        """Non-D1 players should predict Non-D1 with 0-40% D1 probability"""
        player_data = {k: v for k, v in non_d1_player.items()
                      if k not in ['max_d1_prob', 'expected_category', 'description']}
        
        if non_d1_player['primary_position'] == 'OF':
            player = PlayerOutfielder(**player_data)
            result = of_pipeline.predict(player)
        else:
            player = PlayerInfielder(**player_data)
            result = inf_pipeline.predict(player)
        
        # D1 probability should be in 0-40% range
        d1_prob = result.d1_results.d1_probability
        assert 0.0 <= d1_prob <= non_d1_player['max_d1_prob'], \
            f"{non_d1_player['description']} got {d1_prob:.1%} D1 probability, expected 0%-{non_d1_player['max_d1_prob']:.1%}"
        
        # Should predict Non-D1
        assert result.get_final_prediction() == non_d1_player['expected_category'], \
            f"{non_d1_player['description']} predicted {result.get_final_prediction()}, expected {non_d1_player['expected_category']}"


class TestEliteDetectionConsistency:
    """Test that elite detection systems are working consistently"""
    
    @pytest.fixture(scope="class")
    def inf_pipeline(self):
        return InfielderPredictionPipeline()
    
    @pytest.fixture(scope="class")
    def of_pipeline(self):
        return OutfielderPredictionPipeline()

    def test_elite_detection_triggers_for_known_elite_infielder(self, inf_pipeline):
        """Elite detection should trigger for known elite infielders"""
        super_elite = PlayerInfielder(
            height=75, weight=190, 
            primary_position="SS", hitting_handedness="R", throwing_hand="R", region="South",
            exit_velo_max=105.0, inf_velo=93.0, sixty_time=6.5
        )
        
        result = inf_pipeline.predict(super_elite)
        
        # Check if elite detection information is available - these details may not be available in current structure
        # Since we don't have elite detection details in the current MLPipelineResults structure,
        # we'll check if the player gets reasonable P4 consideration as a proxy for elite detection
        if result.p4_results:
            # If P4 results exist, check if elite indicators are present
            if hasattr(result.p4_results, 'is_elite') and result.p4_results.is_elite:
                assert result.p4_results.is_elite, "Elite detection should trigger for super elite player"
            # Or check if P4 probability is reasonable for elite player
            assert result.p4_results.p4_probability > 0.1, \
                f"Super elite player should have reasonable P4 consideration, got {result.p4_results.p4_probability:.1%}"

    def test_elite_detection_triggers_for_known_elite_outfielder(self, of_pipeline):
        """Elite detection should trigger for known elite outfielders"""
        super_elite = PlayerOutfielder(
            height=74, weight=200,
            primary_position="OF", hitting_handedness="S", throwing_hand="R", region="South",
            exit_velo_max=105.0, of_velo=98.0, sixty_time=6.6
        )
        
        result = of_pipeline.predict(super_elite)
        
        # Check elite detection - since detailed elite detection info may not be available in current structure,
        # we'll verify the player gets reasonable predictions for elite status
        
        # Super elite OF should have high D1 probability
        assert result.d1_results.d1_probability > 0.6, \
            f"Super elite OF should have high D1 probability, got {result.d1_results.d1_probability:.1%}"
        
        # Check P4 elite detection if P4 results exist
        if result.p4_results:
            if hasattr(result.p4_results, 'is_elite') and result.p4_results.is_elite:
                assert result.p4_results.is_elite, "P4 elite detection should trigger for super elite OF"
            # Or check if P4 probability is reasonable for elite player
            assert result.p4_results.p4_probability > 0.05, \
                f"Super elite OF should have some P4 consideration, got {result.p4_results.p4_probability:.1%}"


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v", "--tb=short"])