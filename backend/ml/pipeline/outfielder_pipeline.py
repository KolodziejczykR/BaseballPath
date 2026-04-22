import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

MODEL_DIR_D1 = os.path.join(project_root, os.getenv('OF_MODEL_DIR_D1', 'backend/ml/models/models_of/models_d1_or_not_of/version_04202026'))
MODEL_DIR_P4 = os.path.join(project_root, os.getenv('OF_MODEL_DIR_P4', 'backend/ml/models/models_of/models_p4_or_not_of/version_04202026'))

from backend.utils.player_types import PlayerOutfielder
from backend.utils.prediction_types import MLPipelineResults
from backend.ml.models.v2_predict import predict_d1, predict_p4


class OutfielderPredictionPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def predict(self, player: PlayerOutfielder) -> MLPipelineResults:
        if not isinstance(player, PlayerOutfielder):
            self.logger.error(f"Invalid input type: {type(player)}. Expected PlayerOutfielder")
            raise TypeError("Input must be a PlayerOutfielder object")

        try:
            player_data = player.get_player_info()

            self.logger.info("Running Stage 1: D1 vs Non-D1 prediction")
            d1_result = predict_d1(player_data, MODEL_DIR_D1)

            if not d1_result.d1_prediction:
                return MLPipelineResults(player=player, d1_results=d1_result, p4_results=None)

            self.logger.info("Running Stage 2: P4 vs Non-P4 D1 prediction")
            p4_result = predict_p4(player_data, MODEL_DIR_P4, float(d1_result.d1_probability))

            return MLPipelineResults(player=player, d1_results=d1_result, p4_results=p4_result)

        except Exception as e:
            self.logger.error(f"Prediction failed: {str(e)}", exc_info=True)
            raise
