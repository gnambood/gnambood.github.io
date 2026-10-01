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

def test_catalog_endpoint(monkeypatch):
    import api.main as main_module

    monkeypatch.setattr(
        main_module,
        "load_vehicle_catalog",
        lambda: {
            "market_year": 2021,
            "manufacturer_count": 1,
            "model_count": 1,
            "manufacturers": [
                {
                    "value": "ford",
                    "label": "Ford",
                    "models": [
                        {
                            "value": "f-150",
                            "label": "F-150",
                            "years": [2004],
                            "mileages": [65000],
                            "conditions": ["good"],
                            "defaults": {},
                            "listing_count": 60,
                            "review_count": 5,
                        }
                    ],
                }
            ],
        },
    )

    response = client.get("/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["manufacturer_count"] == 1
    assert body["manufacturers"][0]["models"][0]["value"] == "f-150"
