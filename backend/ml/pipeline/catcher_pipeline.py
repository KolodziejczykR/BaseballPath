import os
import sys
import warnings
import logging
from dotenv import load_dotenv
warnings.filterwarnings('ignore')

# Add project root to Python path to enable backend imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv()

MODEL_DIR_D1 = os.path.join(project_root, os.getenv('C_MODEL_DIR_D1', 'backend/ml/models/models_c/models_d1_or_not_c/version_08182025'))
MODEL_DIR_P4 = os.path.join(project_root, os.getenv('C_MODEL_DIR_P4', 'backend/ml/models/models_c/models_p4_or_not_c/version_08202025'))

from backend.utils.player_types import PlayerCatcher
from backend.utils.prediction_types import MLPipelineResults
from backend.ml.models.models_c.models_d1_or_not_c.version_08182025 import prediction_pipeline as d1_pipeline
from backend.ml.models.models_c.models_p4_or_not_c.version_08202025 import prediction_pipeline as p4_pipeline

class CatcherPredictionPipeline:
    def __init__(self):
        """
        Initialize the catcher prediction pipeline using the latest production models.
        """
        self.logger = logging.getLogger(__name__)

    def predict(self, player: PlayerCatcher) -> MLPipelineResults:
        """
        Run the complete two-stage catcher prediction pipeline.
        
        Model Thresholds:
            D1 Stage: Uses meta-learner ensemble (LightGBM + DNN + Meta-learner)
            P4 Stage: 
        
        Args:
            player: PlayerCatcher object containing player statistics
        
        Returns:
            MLPipelineResults: Structured prediction results with D1 and P4 predictions
        """
        
        if not isinstance(player, PlayerCatcher):
            self.logger.error(f"Invalid input type: {type(player)}. Expected PlayerCatcher")
            raise TypeError("Input must be a PlayerCatcher object")
                
        try:
            # Convert player to dictionary format expected by models
            player_data = player.get_player_info()
            self.logger.debug(f"Player data converted to dict with {len(player_data)} features")
            
            # Stage 1: Predict D1 vs Non-D1
            self.logger.info("Running Stage 1: D1 vs Non-D1 prediction")
            d1_result = d1_pipeline.predict_catcher_d1_probability(player_data, MODEL_DIR_D1)
            
            # If predicted as Non-D1, return early
            if not d1_result.d1_prediction:
                return MLPipelineResults(
                    player=player,
                    d1_results=d1_result,
                    p4_results=None  # No P4 prediction for Non-D1 players
                )
            
            # Stage 2: For D1-predicted players, predict P4 vs Non-P4 D1
            self.logger.info("Running Stage 2: P4 vs Non-P4 D1 prediction")
            p4_result = p4_pipeline.predict_catcher_p4_probability(player_data, MODEL_DIR_P4, float(d1_result.d1_probability))

            return MLPipelineResults(
                player=player,
                d1_results=d1_result,
                p4_results=p4_result
            )
            
        except Exception as e:
            self.logger.error(f"Prediction failed: {str(e)}", exc_info=True)
            raise e  # Re-raise the exception instead of returning error dict
    
# Example usage
if __name__ == "__main__":
    # Create example catcher
    example_player = PlayerCatcher(
        height=72,
        weight=210,
        primary_position='C',
        hitting_handedness='R',
        throwing_hand='R', 
        region='South',
        exit_velo_max=98.0,
        c_velo=83.0,
        pop_time=1.8,
        sixty_time=6.9
    )
    
    # Initialize pipeline and make prediction
    pipeline = CatcherPredictionPipeline()
    result = pipeline.predict(example_player)
    
    print("\n" + "="*50)
    print("CATCHER PREDICTION RESULTS")
    print("="*50)
    print(f"Final Prediction: {result.get_final_prediction()}")
    print(f"Player Type: {result.get_player_type()}")
    print(f"D1 Probability: {result.d1_results.d1_probability:.1%}")
    print(f"D1 Confidence: {result.d1_results.confidence}")
    
    if result.p4_results:
        print(f"P4 Probability: {result.p4_results.p4_probability:.1%}")
        print(f"P4 Confidence: {result.p4_results.confidence}")
        print(f"Elite P4: {result.p4_results.is_elite}")
    else:
        print("P4 Model: Not implemented yet")
    
    print(f"Pipeline Confidence: {result.get_pipeline_confidence()}")
    print(f"Models Used: {result.get_models_used()}")

    print(f"Player Info: {result.get_player_info()}")
    print("\nRaw Player Object:")
    print(str(example_player))