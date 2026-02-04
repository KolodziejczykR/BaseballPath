import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def _base_payload():
    return {
        "height": 74,
        "weight": 200,
        "primary_position": "RHP",
        "player_region": "West",
        "throwing_hand": "R",
        "fastball_velo_max": 90.0,
        "fastball_velo_range": 86.0,
    }


def test_pitcher_predict_minimal():
    response = client.post("/pitcher/predict", json=_base_payload())
    assert response.status_code == 200
    data = response.json()
    assert "final_prediction" in data
    assert data["final_prediction"] in ["Non-D1", "Non-P4 D1", "Power 4 D1"]


def test_pitcher_predict_full_payload():
    payload = _base_payload()
    payload.update({
        "fastball_spin": 2200.0,
        "changeup_velo": 80.0,
        "changeup_spin": 1700.0,
        "curveball_velo": 74.0,
        "curveball_spin": 2200.0,
        "slider_velo": 78.0,
        "slider_spin": 2300.0,
    })
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "final_prediction" in data


def test_pitcher_missing_required_fastball_max():
    payload = _base_payload()
    payload.pop("fastball_velo_max")
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_invalid_height_range():
    payload = _base_payload()
    payload["height"] = 40
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_invalid_fastball_max_range():
    payload = _base_payload()
    payload["fastball_velo_max"] = 200
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_invalid_spin_range():
    payload = _base_payload()
    payload["fastball_spin"] = 5000
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_missing_height():
    payload = _base_payload()
    payload.pop("height")
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_missing_weight():
    payload = _base_payload()
    payload.pop("weight")
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_invalid_weight_type():
    payload = _base_payload()
    payload["weight"] = "heavy"
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_invalid_primary_position_type():
    payload = _base_payload()
    payload["primary_position"] = 123
    response = client.post("/pitcher/predict", json=payload)
    assert response.status_code == 422


def test_pitcher_features_endpoint():
    response = client.get("/pitcher/features")
    assert response.status_code == 200
    data = response.json()
    assert "required_features" in data


def test_pitcher_example_endpoint():
    response = client.get("/pitcher/example")
    assert response.status_code == 200
    data = response.json()
    assert "example_input" in data


def test_pitcher_health_endpoint():
    response = client.get("/pitcher/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "pipeline_loaded" in data
