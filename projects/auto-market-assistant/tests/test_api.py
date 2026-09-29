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
