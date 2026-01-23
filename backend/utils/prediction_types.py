"""
Prediction classes for ML pipeline returns
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.utils.player_types import PlayerType
from backend.utils.school_group_constants import POWER_4_D1, NON_P4_D1, NON_D1

@dataclass
class P4PredictionResult:
    """
    Prediction result class for P4 classification
    Designed for LLM school selection use cases
    """
    p4_probability: float
    p4_prediction: bool  
    confidence: str    
    is_elite: bool         
    model_version: str
    elite_indicators: Optional[List[str]] = None  # Why they're elite
    
    def __post_init__(self):
        """Validate probability bounds"""
        if not 0.0 <= self.p4_probability <= 1.0:
            raise ValueError(f"P4 probability must be between 0 and 1, got {self.p4_probability}")
    
@dataclass
class D1PredictionResult:
    """
    Prediction result class for D1 classification
    Designed for LLM school selection use cases and ML pipeline
    """
    d1_probability: float
    d1_prediction: bool
    confidence: str
    model_version: str

    def __post_init__(self):
        """Validate probability bounds"""
        if not 0.0 <= self.d1_probability <= 1.0:
            raise ValueError(f"D1 probability must be between 0 and 1, got {self.d1_probability}")
        
@dataclass
class MLPipelineResults:
    player: PlayerType
    d1_results: D1PredictionResult

    p4_results: Optional[P4PredictionResult] = None  # P4PredictionResult only if it passes D1

    def get_final_prediction(self) -> str:
        """
        Determine the final prediction given the results of both stages

        Returns:
            str: One of POWER_4_D1, NON_P4_D1, or NON_D1
        """
        if self.p4_results and self.p4_results.p4_prediction:
            return POWER_4_D1
        elif self.d1_results.d1_prediction:
            return NON_P4_D1
        else:
            return NON_D1

    def get_pipeline_confidence(self) -> str:
        """
        Return a string indicating the confidence levels of both D1 and P4 models,
        or just the D1 model if the P4 model was not used.

        Returns:
            str: A string describing the confidence levels of the models
        """
        if self.p4_results:
            return f"D1 Model Confidence: {self.d1_results.confidence}, P4 Model Confidence: {self.p4_results.confidence}"
        else:
            return f"D1 Model Confidence: {self.d1_results.confidence}"

    def get_player_type(self) -> str:
        """Gets the player type, a str"""
        return self.player.get_player_type()

    def get_player_info(self) -> dict:
        """
        Gets the player info as a dictionary
        
        Returns:
            dict: The player info as a dictionary
        """
        return self.player.get_player_info()
    
    def get_base_features(self) -> dict:
        """
        Gets the base features as a dictionary
        
        Returns:
            dict: The base features as a dictionary
        """
        return self.player.get_player_features()
    
    def _get_p4_probs(self) -> Dict[str, float]:
        """
        helper for get_player_probabilities, checking if the player is p4 of not
        and returning the probabilities.
        """
        return {
            "Non-P4": 1.0 - self.p4_results.p4_probability,
            "P4": self.p4_results.p4_probability
        } if self.p4_results else {}
    
    def get_player_probabilities(self) -> Dict[str, Dict[str, float]]:
        """
        Gets a dictionary with the probabilities of the player being D1 or Non-D1 and P4 or Non-P4.
        
        Returns:
            dict: A dictionary with two keys: "D1 vs Non-D1" and "P4 vs Non-P4". The values are dictionaries
            with two keys: the options and their probabilities.
        """
        return {
            "D1 vs Non-D1": {
                "Non-D1": 1.0 - self.d1_results.d1_probability,
                "D1": self.d1_results.d1_probability
            },
            "P4 vs Non-P4": self._get_p4_probs()   
        }
    
    def get_models_used(self) -> str:
        """
        Gets a list of the models used to make the prediction.
        Returns a list with two elements: the D1 model version and the P4 model version.
        If the P4 model was not used, the second element will be None.

        Returns:
            str: A string with the versions of the models used to make the prediction.
        """
        return f"D1: {self.d1_results.model_version}" + (f", P4: {self.p4_results.model_version}" if self.p4_results else "")
    
    def get_api_response(self) -> Dict[str, Any]:
        """
        Gets the API response as a dictionary (json)
        
        Returns:
            dict: The API response as a dictionary
        """
        return {
            "final_prediction": self.get_final_prediction(),
            "d1_probability": self.d1_results.d1_probability,
            "p4_probability": self.p4_results.p4_probability if self.p4_results else None,
            'probabilities': self.get_player_probabilities(),
            "confidence": self.get_pipeline_confidence(),
            "model_chain": self.get_models_used(),
            "d1_details": {
                "probability": self.d1_results.d1_probability,
                "prediction": self.d1_results.d1_prediction,
                "confidence": self.d1_results.confidence,
                "model_version": self.d1_results.model_version
            },
            "p4_details": {
                "probability": self.p4_results.p4_probability,
                "prediction": self.p4_results.p4_prediction,
                "confidence": self.p4_results.confidence,
                "model_version": self.p4_results.model_version,
                "is_elite": self.p4_results.is_elite,
                "elite_indicators": self.p4_results.elite_indicators
            } if self.p4_results else None,
            "player_type": self.get_player_type(),
            "player_info": self.get_player_info()
        }
