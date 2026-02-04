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

MODEL_DIR_D1 = os.path.join(project_root, os.getenv('P_MODEL_DIR_D1', ''))
MODEL_DIR_P4 = os.path.join(project_root, os.getenv('P_MODEL_DIR_P4', ''))

from backend.utils.player_types import PlayerPitcher
from backend.utils.prediction_types import MLPipelineResults
from backend.ml.models.models_p.models_d1_or_not_p.version_01302026 import prediction_pipeline as d1_pipeline
from backend.ml.models.models_p.models_p4_or_not_p.version_02042026 import prediction_pipeline as p4_pipeline


class PitcherPredictionPipeline:
    def __init__(self):
        """
        Initialize the pitcher prediction pipeline using the latest production models.
        """
        self.logger = logging.getLogger(__name__)

    def predict(self, player: PlayerPitcher) -> MLPipelineResults:
        """
        Run the complete two-stage pitcher prediction pipeline.
        """
        if not isinstance(player, PlayerPitcher):
            self.logger.error(f"Invalid input type: {type(player)}. Expected PlayerPitcher")
            raise TypeError("Input must be a PlayerPitcher object")

        try:
            player_data = player.get_player_info()
            self.logger.debug(f"Player data converted to dict with {len(player_data)} features")

            # Stage 1: Predict D1 vs Non-D1
            self.logger.info("Running Stage 1: D1 vs Non-D1 prediction")
            d1_result = d1_pipeline.predict_pitcher_d1_probability(player_data, MODEL_DIR_D1)

            if not d1_result.d1_prediction:
                return MLPipelineResults(
                    player=player,
                    d1_results=d1_result,
                    p4_results=None
                )

            # Stage 2: Predict P4 vs Non-P4 D1
            self.logger.info("Running Stage 2: P4 vs Non-P4 D1 prediction")
            p4_result = p4_pipeline.predict_pitcher_p4_probability(player_data, MODEL_DIR_P4, float(d1_result.d1_probability))

            return MLPipelineResults(
                player=player,
                d1_results=d1_result,
                p4_results=p4_result
            )

        except Exception as e:
            self.logger.error(f"Prediction failed: {str(e)}", exc_info=True)
            raise e

