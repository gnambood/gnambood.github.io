from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "auto-market-assistant"

def test_price_input_validation():
    response = client.post(
        "/predict-price",
        json={"manufacturer": "ford", "model": "f-150", "year": 2004, "mileage": -1},
    )
    assert response.status_code == 422

def test_ask_input_validation():
    response = client.post(
        "/ask",
        json={"manufacturer": "ford", "model": "f-150", "year": 2004, "question": "bad"},
    )
    assert response.status_code == 422


def test_vehicle_options_route(monkeypatch):
    payload = {
        "market_year": 2021,
        "vehicle_count": 1,
        "vehicles": {
            "ford-f-150": {
                "display_make": "Ford",
                "display_model": "F-150",
                "make": "ford",
                "model": "f 150",
                "years": [2004],
                "mileages": [65000],
                "conditions": ["good"],
                "defaults": {},
            }
        },
    }
    monkeypatch.setattr("api.main.load_vehicle_options", lambda: payload)
    response = client.get("/options")
    assert response.status_code == 200
    assert response.json()["vehicle_count"] == 1
