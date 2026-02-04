from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import os
import sys
import logging

models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pipeline.pitcher_pipeline import PitcherPredictionPipeline
from backend.utils.player_types import PlayerPitcher

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize the pipeline
try:
    pipeline = PitcherPredictionPipeline()
    logger.info("Pitcher pipeline initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize pitcher pipeline: {e}")
    pipeline = None


class PitcherInput(BaseModel):
    # Required
    height: int = Field(..., ge=60, le=84)
    weight: int = Field(..., ge=120, le=320)
    primary_position: str = Field(..., description="Primary position (RHP/LHP)")
    player_region: str = Field(..., description="Region (Northeast, South, Midwest, West)")
    throwing_hand: Optional[str] = Field(None, description="Throwing hand (L/R)")

    # Pitch metrics (optional)
    fastball_velo_range: Optional[float] = Field(None, ge=60, le=105)
    fastball_velo_max: float = Field(..., ge=60, le=105)
    fastball_spin: Optional[float] = Field(None, ge=1200, le=3500)

    changeup_velo: Optional[float] = Field(None, ge=60, le=95)
    changeup_spin: Optional[float] = Field(None, ge=800, le=3200)
    curveball_velo: Optional[float] = Field(None, ge=55, le=95)
    curveball_spin: Optional[float] = Field(None, ge=1200, le=3500)
    slider_velo: Optional[float] = Field(None, ge=60, le=100)
    slider_spin: Optional[float] = Field(None, ge=1200, le=3500)

    # Optional precomputed features
    num_pitches: Optional[int] = None
    fb_ch_velo_diff: Optional[float] = None
    fb_cb_velo_diff: Optional[float] = None
    fb_sl_velo_diff: Optional[float] = None


@router.post("/predict", responses={
    400: {"description": "Validation error or prediction failed"},
    422: {"description": "Input validation error"},
    500: {"description": "Internal server error"}
})
async def predict_pitcher(input_data: PitcherInput) -> Dict[str, Any]:
    if pipeline is None:
        logger.error("Prediction pipeline not available")
        raise HTTPException(status_code=500, detail="Prediction pipeline not available")

    try:
        input_dict = input_data.model_dump(exclude_none=True)
        logger.info(f"Processing pitcher prediction for position: {input_dict['primary_position']}")

        player = PlayerPitcher(
            height=input_dict['height'],
            weight=input_dict['weight'],
            primary_position=input_dict['primary_position'],
            throwing_hand=input_dict.get('throwing_hand', 'R'),
            region=input_dict['player_region'],
            fastball_velo_range=input_dict.get('fastball_velo_range'),
            fastball_velo_max=input_dict.get('fastball_velo_max'),
            fastball_spin=input_dict.get('fastball_spin'),
            changeup_velo=input_dict.get('changeup_velo'),
            changeup_spin=input_dict.get('changeup_spin'),
            curveball_velo=input_dict.get('curveball_velo'),
            curveball_spin=input_dict.get('curveball_spin'),
            slider_velo=input_dict.get('slider_velo'),
            slider_spin=input_dict.get('slider_spin'),
        )

        result = pipeline.predict(player)
        return result.get_api_response()

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Input validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/features")
async def get_required_features() -> Dict[str, Any]:
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Prediction pipeline not available")

    dummy_player = PlayerPitcher(
        height=74,
        weight=200,
        primary_position="RHP",
        throwing_hand="R",
        region="West",
        fastball_velo_range=88.0,
        fastball_velo_max=90.0,
        fastball_spin=2200.0,
        changeup_velo=80.0,
        changeup_spin=1700.0,
        curveball_velo=74.0,
        curveball_spin=2200.0,
        slider_velo=77.0,
        slider_spin=2250.0,
    )

    return {
        "required_features": dummy_player.get_player_features(),
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy" if pipeline is not None else "unhealthy",
        "pipeline_loaded": pipeline is not None
    }


@router.get("/example")
async def get_example_input() -> Dict[str, Any]:
    return {
        "example_input": {
            "height": 74,
            "weight": 200,
            "primary_position": "RHP",
            "player_region": "West",
            "throwing_hand": "R",
            "fastball_velo_range": 88.0,
            "fastball_velo_max": 90.0,
            "fastball_spin": 2200.0,
            "changeup_velo": 80.0,
            "changeup_spin": 1700.0,
            "curveball_velo": 74.0,
            "curveball_spin": 2200.0,
            "slider_velo": 77.0,
            "slider_spin": 2250.0
        },
        "description": "Example pitcher input"
    }
