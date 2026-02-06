from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def _assert_prediction_response(resp):
    assert resp.status_code == 200
    data = resp.json()
    assert data["final_prediction"] in ["Non-D1", "Non-P4 D1", "Power 4 D1"]
    assert "probabilities" in data
    assert "confidence" in data
    assert "model_chain" in data
    assert "d1_probability" in data
    assert "player_type" in data


def test_end_to_end_infielder_predict():
    payload = {
        "height": 72.0,
        "weight": 180.0,
        "sixty_time": 7.0,
        "exit_velo_max": 85.0,
        "inf_velo": 75.0,
        "throwing_hand": "R",
        "hitting_handedness": "R",
        "player_region": "West",
        "primary_position": "SS",
    }
    resp = client.post("/infielder/predict", json=payload)
    _assert_prediction_response(resp)
    assert resp.json()["player_type"] == "Infielder"


def test_end_to_end_outfielder_predict():
    payload = {
        "height": 71.0,
        "weight": 175.0,
        "sixty_time": 7.1,
        "exit_velo_max": 86.0,
        "of_velo": 78.0,
        "throwing_hand": "R",
        "hitting_handedness": "R",
        "player_region": "West",
        "primary_position": "OF",
    }
    resp = client.post("/outfielder/predict", json=payload)
    _assert_prediction_response(resp)
    assert resp.json()["player_type"] == "Outfielder"


def test_end_to_end_catcher_predict():
    payload = {
        "height": 70,
        "weight": 175,
        "sixty_time": 7.0,
        "exit_velo_max": 85.0,
        "c_velo": 75.0,
        "pop_time": 2.0,
        "primary_position": "C",
        "hitting_handedness": "R",
        "throwing_hand": "R",
        "player_region": "West",
    }
    resp = client.post("/catcher/predict", json=payload)
    _assert_prediction_response(resp)
    assert resp.json()["player_type"] == "Catcher"


def test_end_to_end_pitcher_predict():
    payload = {
        "height": 74,
        "weight": 200,
        "primary_position": "RHP",
        "player_region": "West",
        "throwing_hand": "R",
        "fastball_velo_max": 90.0,
        "fastball_velo_range": 86.0,
    }
    resp = client.post("/pitcher/predict", json=payload)
    _assert_prediction_response(resp)
    assert resp.json()["player_type"] == "Pitcher"
