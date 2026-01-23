# AI Baseball Recruitment - Test Suite

This directory contains comprehensive tests for the AI Baseball Recruitment project, covering both the machine learning pipelines and the API endpoints.

## Test Files Overview

### 1. `test_infield_model_pipeline.py`
Tests for the infielder prediction pipeline, including:
- **Basic functionality tests**: High, average, and low performing players
- **Edge cases**: Very high/low values, boundary conditions
- **Position-specific tests**: SS, 2B, 3B, 1B positions
- **Regional tests**: Different player regions (West, South, Midwest, etc.)
- **Handedness combinations**: All throwing/hitting hand combinations
- **Missing data handling**: Tests with minimal or missing features
- **Probability validation**: Ensures probabilities sum to 1.0
- **Feature validation**: Tests required features and feature info methods

### 2. `test_outfielder_model_pipeline.py`
Tests for the outfielder prediction pipeline, including:
- **Basic functionality tests**: High, average, and low performing players
- **Edge cases**: Very high/low values, boundary conditions
- **Position-specific tests**: CF, LF, RF, OF positions
- **Regional tests**: Different player regions
- **Handedness combinations**: All throwing/hitting hand combinations
- **Missing data handling**: Tests with minimal or missing features
- **Probability validation**: Ensures probabilities sum to 1.0
- **Feature validation**: Tests required features and feature info methods
- **Specialized player types**: Speed-focused and power-focused players

### 3. `test_api.py`
Tests for the FastAPI endpoints, including:
- **Basic API tests**: Root endpoint, health check
- **Infielder API tests**: All infielder endpoints with various data scenarios
- **Outfielder API tests**: All outfielder endpoints with various data scenarios
- **Error handling**: Invalid data, empty data, validation errors
- **Endpoint validation**: Features, health, example endpoints
- **Position-specific API tests**: Different positions for both infielders and outfielders

## Running Tests

### Prerequisites
Make sure you have the required dependencies installed:
```bash
pip install pytest fastapi httpx
```

### Using VS Code Testing Sidebar (Recommended)
1. Open the Testing sidebar in VS Code (beaker icon)
2. Click "Configure Python Tests" if not already configured
3. Select "pytest" as the test framework
4. Set the test directory to `tests/`
5. Use the sidebar to:
   - Run all tests
   - Run individual test files
   - Run specific test functions
   - Debug tests
   - View test results and coverage

### Running Tests from Command Line
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test files
python3 -m pytest tests/test_infield_model_pipeline.py -v
python3 -m pytest tests/test_outfielder_model_pipeline.py -v
python3 -m pytest tests/test_api.py -v

# Run specific test functions
python3 -m pytest tests/test_infield_model_pipeline.py::test_high_performer -v

# Run tests matching a pattern
python3 -m pytest tests/test_api.py -k "infielder" -v
```

## Test Data

The tests use realistic baseball player statistics:

### High Performer Example
- **Exit Velocity**: 88-92 mph
- **60-yard dash**: 6.6-6.8 seconds
- **Bat Speed**: 75-78 mph
- **Height/Weight**: 72-73", 180-190 lbs

### Average Performer Example
- **Exit Velocity**: 82-85 mph
- **60-yard dash**: 7.0-7.2 seconds
- **Bat Speed**: 70-72 mph
- **Height/Weight**: 70-71", 165-175 lbs

### Low Performer Example
- **Exit Velocity**: 75-78 mph
- **60-yard dash**: 7.6-7.8 seconds
- **Bat Speed**: 65-67 mph
- **Height/Weight**: 68-69", 150-155 lbs

## Test Coverage

### Model Pipeline Tests
- ✅ Input validation and preprocessing
- ✅ Missing value handling
- ✅ Categorical feature encoding
- ✅ Numerical feature scaling
- ✅ Prediction output validation
- ✅ Probability distribution validation
- ✅ Edge cases and boundary conditions
- ✅ Different player types and positions
- ✅ Regional and demographic variations

### API Tests
- ✅ Endpoint availability and response codes
- ✅ Request/response schema validation
- ✅ Error handling for invalid inputs
- ✅ Empty data handling
- ✅ All available endpoints (predict, features, health, example)
- ✅ Different data scenarios and player types

## Expected Test Results

### Successful Test Run
When running tests through VS Code's testing sidebar or pytest, you should see output similar to:

```
============================= test session starts ==============================
platform darwin -- Python 3.x.x, pytest-7.x.x, pluggy-1.x.x
rootdir: /path/to/project
plugins: hypothesis-6.x.x, cov-4.x.x, reportlog-0.3.x, timeout-2.x.x
collected 51 items

tests/test_infield_model_pipeline.py ................... [ 37%]
tests/test_outfielder_model_pipeline.py ................ [ 69%]
tests/test_api.py ............................. [100%]

============================== 51 passed in 15.23s ==============================
```

### Test Counts
- **Infielder Pipeline Tests**: ~15 tests
- **Outfielder Pipeline Tests**: ~16 tests  
- **API Tests**: ~20 tests
- **Total**: ~51 tests

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're running tests from the project root directory
2. **Model Loading Errors**: Ensure the model files exist in `backend/ml/models/`
3. **API Connection Errors**: The API tests require the FastAPI server to be running
4. **Timeout Errors**: Some tests may take longer if models are loading for the first time

### Debug Mode
Run tests with more verbose output:
```bash
pytest tests/ -v -s --tb=long
```

### Running Tests in Isolation
To test individual components without dependencies:
```bash
# Test only the pipeline logic
pytest tests/test_infield_model_pipeline.py::test_minimal_input -v

# Test only API endpoints
pytest tests/test_api.py::test_infielder_health_endpoint -v
```

## Adding New Tests

When adding new tests:

1. **Follow the existing naming convention**: `test_<functionality>`
2. **Include docstrings**: Describe what the test validates
3. **Use realistic data**: Base test data on actual baseball statistics
4. **Test edge cases**: Include boundary conditions and error scenarios
5. **Update this README**: Document new test categories or patterns

### Test Structure Template
```python
def test_new_functionality(pipeline):
    """Test description of what this validates"""
    # Setup test data
    test_data = {
        "key_feature": value,
        # ... other features
    }
    
    # Execute test
    result = pipeline.predict(test_data)
    
    # Validate results
    assert "prediction" in result
    assert "probabilities" in result
    assert result["prediction"] in ["Non D1", "Non P4 D1", "Power 4 D1"]
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines using pytest directly:
- **Exit code 0**: All tests passed
- **Exit code 1**: Some tests failed

The tests are compatible with pytest's standard output format for integration with CI tools like GitHub Actions, Jenkins, or GitLab CI.

### CI Configuration Example
```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    pip install pytest fastapi httpx
    pytest tests/ -v
``` 