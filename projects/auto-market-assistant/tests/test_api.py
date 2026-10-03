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


def test_catalog_reconstructs_vehicle_year_from_vehicle_age(monkeypatch, tmp_path):
    import pandas as pd
    import api.services as services

    vehicles = pd.DataFrame(
        {
            "manufacturer": ["ford"] * 20,
            "model": ["f-150"] * 20,
            "vehicle_age": [17] * 20,
            "odometer": [65000] * 20,
            "condition": ["good"] * 20,
            "fuel": ["gas"] * 20,
            "title_status": ["clean"] * 20,
            "transmission": ["automatic"] * 20,
            "drive": ["4wd"] * 20,
            "type": ["truck"] * 20,
            "state": ["ca"] * 20,
            "price": [12000] * 20,
            "posting_year": [2021] * 20,
        }
    )
    reviews = pd.DataFrame(
        {
            "manufacturer": ["ford"] * 5,
            "model_family": ["f 150"] * 5,
            "vehicle_year": [2004] * 5,
        }
    )

    vehicle_path = tmp_path / "vehicles_clean.parquet"
    review_path = tmp_path / "review_documents.parquet"
    vehicles.to_parquet(vehicle_path)
    reviews.to_parquet(review_path)

    monkeypatch.setattr(
        services,
        "ensure_artifacts",
        lambda: {
            "vehicles_clean.parquet": vehicle_path,
            "review_documents.parquet": review_path,
        },
    )
    services.load_vehicle_catalog.cache_clear()

    catalog = services.load_vehicle_catalog()

    assert catalog["market_year"] == 2021
    assert catalog["manufacturer_count"] == 1
    assert catalog["manufacturers"][0]["models"][0]["years"] == [2004]


def test_scope_guard_rejects_specific_vehicle_inspection():
    from api.services import RagEngine

    result = RagEngine._scope_guard("Does this vehicle have a dent?")

    assert result is not None
    assert result["reason_code"] == "specific_vehicle_fact"
    assert "specific vehicle" in result["reason"].lower()


def test_scope_guard_rejects_plural_previous_owner_question():
    from api.services import RagEngine

    result = RagEngine._scope_guard(
        "How many previous owners did this exact car have?"
    )

    assert result is not None
    assert result["reason_code"] == "specific_vehicle_fact"


def test_scope_guard_rejects_external_data_questions():
    from api.services import RagEngine

    questions = [
        "How much should I expect to pay for insurance on this vehicle?",
        "Will fuel prices go up next year for this vehicle?",
        "Which dealership has this model in stock today?",
    ]

    for question in questions:
        result = RagEngine._scope_guard(question)
        assert result is not None
        assert result["reason_code"] == "requires_external_data"


def test_scope_guard_rejects_authoritative_specification():
    from api.services import RagEngine

    result = RagEngine._scope_guard(
        "What is the official EPA combined MPG rating?"
    )

    assert result is not None
    assert result["reason_code"] == "authoritative_specification"


def test_scope_guard_allows_model_level_owner_question():
    from api.services import RagEngine

    result = RagEngine._scope_guard(
        "Do owners report body-panel or paint problems with this model?"
    )

    assert result is None



def test_answerability_policy_matches_validated_operating_point():
    from api.services import load_answerability_policy

    policy = load_answerability_policy()

    assert policy == {
        "max_threshold": 0.38,
        "mean_top3_threshold": 0.36,
        "support_threshold": 0.34,
        "min_support_sources": 2,
    }


def test_multi_signal_retrieval_gate_accepts_supported_question():
    import pandas as pd
    from api.services import RagEngine, load_answerability_policy

    retrieved = pd.DataFrame(
        {
            "similarity": [0.3854, 0.3800, 0.3700, 0.3500, 0.3450],
            "review_id": ["a", "b", "c", "d", "e"],
        }
    )

    result = RagEngine._assess_retrieval(
        retrieved,
        load_answerability_policy(),
    )

    assert result["answerable"] is True
    assert result["support_source_count"] == 5
    assert result["relevant_source_count"] == 5


def test_multi_signal_retrieval_gate_rejects_weak_question():
    import pandas as pd
    from api.services import RagEngine, load_answerability_policy

    retrieved = pd.DataFrame(
        {
            "similarity": [0.36, 0.35, 0.34, 0.30, 0.29],
            "review_id": ["a", "b", "c", "d", "e"],
        }
    )

    result = RagEngine._assess_retrieval(
        retrieved,
        load_answerability_policy(),
    )

    assert result["answerable"] is False
    assert result["reason_code"] == "low_retrieval_relevance"
