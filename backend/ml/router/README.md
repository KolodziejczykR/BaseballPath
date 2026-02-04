# ML Router Documentation

This directory contains FastAPI routers for the baseball recruitment ML prediction system. Each router provides HTTP endpoints for making predictions using trained machine learning models.

## Architecture Overview

The ML router system follows a consistent pattern across all position types:

```
HTTP Request → Input Validation → PlayerType Object → ML Pipeline → Response
```

### Supported Position Types

- **Infielders** (`infielder_router.py`): SS, 2B, 3B, 1B positions
- **Outfielders** (`outfielder_router.py`): CF, LF, RF, OF positions
- **Catchers** (`catcher_router.py`): C position (coming soon)
- **Pitchers** (`pitcher_router.py`): RHP, LHP (pitch metrics)

## API Endpoints

Each position router provides the following endpoints:

### Core Endpoints

#### `POST /{position}/predict`
Makes predictions for college recruitment level classification.

**Input**: JSON object with player statistics
**Output**: Prediction results with probabilities for all categories

**Categories**:
- `Non-D1`: Not predicted for Division 1 level
- `Non-P4 D1`: Division 1 but not Power 4 conference
- `Power 4 D1`: Power 4 conference (top tier)

#### `GET /{position}/features`
Returns information about required and optional features.

**Output**:
```json
{
  "required_features": ["height", "weight", ...],
  "feature_info": {
    "numerical_features": [...],
    "categorical_features": [...],
    "descriptions": {...}
  }
}
```

#### `GET /{position}/health`
Health check endpoint to verify pipeline status.

**Output**:
```json
{
  "status": "healthy|unhealthy",
  "pipeline_loaded": true|false
}
```

#### `GET /{position}/example`
Provides an example of valid input data.

**Output**:
```json
{
  "example_input": {...},
  "description": "Example description"
}
```

## Input Validation

### Required Features (All Positions)
- `height`: Player height in inches (60-84)
- `weight`: Player weight in pounds (120-300)
- `sixty_time`: 60-yard dash time in seconds (5.0-10.0)
- `exit_velo_max`: Maximum exit velocity in mph (50-130)
- `primary_position`: Player's primary position
- `hitting_handedness`: R, L, or S (switch)
- `throwing_hand`: R or L
- `player_region`: Geographic region

### Position-Specific Required Features
- **Infielders**: `inf_velo` (50-100 mph)
- **Outfielders**: `of_velo` (50-110 mph)
- **Catchers**: `c_velo` (50-100 mph), `pop_time` (1.5-3.0 seconds)

### Optional Features
- `hand_speed_max`, `bat_speed_max`, `rot_acc_max`
- `thirty_time`, `ten_yard_time`, `run_speed_max`
- `exit_velo_avg`, `distance_max`, `sweet_spot_p`

### Valid Categorical Values

#### Positions
- **Infielders**: SS, 2B, 3B, 1B
- **Outfielders**: CF, LF, RF, OF
- **Catchers**: C
- **Pitchers**: RHP, LHP

#### Handedness
- `R`: Right
- `L`: Left  
- `S`: Switch (hitting only)

#### Regions
- `West`: Western United States
- `South`: Southern United States
- `Northeast`: Northeastern United States
- `Midwest`: Midwestern United States (infielders only)

### Pitcher-Specific Features

Required:
- `height` (inches)
- `weight` (lbs)
- `primary_position` (RHP/LHP)
- `player_region` (West/South/Northeast/Midwest)
- `fastball_velo_max` (mph)

Optional pitch metrics:
- `fastball_velo_range` (mph)
- `fastball_spin` (rpm)
- `changeup_velo` (mph)
- `changeup_spin` (rpm)
- `curveball_velo` (mph)
- `curveball_spin` (rpm)
- `slider_velo` (mph)
- `slider_spin` (rpm)

## ML Pipeline Details

### Two-Stage Hierarchical Classification

Each position uses a sophisticated two-stage prediction system:

1. **Stage 1 (D1 Classification)**
   - Predicts whether player is D1 level or not
   - Uses ensemble of multiple models (XGBoost, LightGBM, CatBoost, SVM)
   - Threshold-based decision making

2. **Stage 2 (P4 Classification)**
   - Only runs if Stage 1 predicts D1 level
   - Predicts Power 4 vs Non-Power 4 D1
   - Position-specific model architectures

### Model Architectures by Position

#### Infielders
- **Stage 1**: Weighted ensemble (XGBoost + LightGBM + CatBoost + SVM)
- **Stage 2**: CatBoost ensemble with elite detection

#### Outfielders
- **Stage 1**: XGBoost ensemble with elite detection + DNN + SVM
- **Stage 2**: XGBoost ensemble with elite detection + MLP + SVM

## Error Handling

The system provides consistent error responses across all endpoints:

### HTTP Status Codes

#### 200 - Success
Prediction completed successfully.

#### 400 - Bad Request
**Error Types**:
- `PREDICTION_FAILED`: ML pipeline encountered an error during prediction
- Missing required fields in input data
- Invalid player data that couldn't create PlayerType object

**Example**:
```json
{
  "detail": "Missing required fields: ['height', 'weight']"
}
```

#### 422 - Unprocessable Entity
**Error Type**: `VALIDATION_ERROR`
Input validation failed (invalid values, out of range, wrong type).

**Examples**:
```json
{
  "detail": "Input validation failed: Position must be one of: ['SS', '2B', '3B', '1B']"
}
```

```json
{
  "detail": [
    {
      "loc": ["height"],
      "msg": "ensure this value is greater than or equal to 60",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

#### 500 - Internal Server Error
**Error Types**:
- `PIPELINE_UNAVAILABLE`: ML pipeline failed to initialize
- `INTERNAL_ERROR`: Unexpected server error

**Example**:
```json
{
  "detail": "Prediction pipeline not available"
}
```

## Response Format

### Successful Prediction Response

```json
{
  "final_prediction": "Power 4 D1",
  "final_category": 2,
  "d1_probability": 0.85,
  "p4_probability": 0.72,
  "probabilities": {
    "non_d1": 0.15,
    "d1_total": 0.85,
    "non_p4_d1": 0.238,
    "p4_d1": 0.612
  },
  "confidence": "High",
  "model_chain": "D1_then_P4",
  "d1_details": {
    "d1_prediction": 1,
    "d1_probability": 0.85,
    "confidence_level": "High",
    "model_votes": {...}
  },
  "p4_details": {
    "p4_prediction": 1,
    "p4_probability": 0.72,
    "confidence": "High",
    "is_elite_candidate": true
  },
  "player_info": {
    "player_type": "Elite Speed-Power Combo",
    "region": "West",
    "elite_candidate_d1": true,
    "elite_candidate_p4": true
  }
}
```

### Field Descriptions

- `final_prediction`: String representation of final classification
- `final_category`: Numeric category (0=Non-D1, 1=Non-P4 D1, 2=Power 4 D1)
- `d1_probability`: Raw probability of being D1 level (0.0-1.0)
- `p4_probability`: Raw probability of being Power 4 (conditional on D1, or null if Non-D1)
- `probabilities`: Breakdown of all category probabilities
- `confidence`: Confidence level (Low, Medium, High)
- `model_chain`: Which models were used ("D1_only" or "D1_then_P4")
- `d1_details`: Detailed results from Stage 1 prediction
- `p4_details`: Detailed results from Stage 2 prediction (null if Non-D1)
- `player_info`: Additional player analysis and metadata

## Usage Examples

### Basic Prediction Request

```bash
curl -X POST "http://localhost:8000/infielder/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "height": 72.0,
    "weight": 180.0,
    "sixty_time": 6.8,
    "exit_velo_max": 88.0,
    "inf_velo": 78.0,
    "throwing_hand": "R",
    "hitting_handedness": "R", 
    "player_region": "West",
    "primary_position": "SS"
  }'
```

### Check Pipeline Health

```bash
curl "http://localhost:8000/infielder/health"
```

### Get Feature Information

```bash
curl "http://localhost:8000/infielder/features"
```

## Logging

All routers include comprehensive logging:

- **Info Level**: Successful predictions, pipeline initialization
- **Error Level**: Prediction failures, validation errors, pipeline errors

Log messages include:
- Player position being processed
- Prediction results
- Error details with stack traces
- Performance metrics

## Development Notes

### Adding New Position Types

1. Create new pipeline class in `backend/ml/pipeline/`
2. Create corresponding router in this directory
3. Follow the established patterns for validation and error handling
4. Add position-specific features and validation rules
5. Update this documentation

### Model Updates

When updating ML models:
1. Update model paths in pipeline classes
2. Verify feature requirements haven't changed
3. Update validation ranges if needed
4. Test all endpoints thoroughly
5. Update documentation if response format changes

### Testing

- Unit tests: `tests/test_api.py`
- Pipeline tests: `tests/test_{position}_model_pipeline.py`
- Integration tests recommended for full workflow validation

## Security Considerations

- Input validation prevents injection attacks
- Numeric ranges prevent extreme values that could crash models
- Error messages don't expose internal system details
- Logging doesn't include sensitive player information
- All endpoints are read-only except prediction endpoints
