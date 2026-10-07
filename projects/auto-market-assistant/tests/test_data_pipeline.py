import pandas as pd

from pipelines.quality import evaluate_quality_gates
from pipelines.run_pipeline import run_pipeline
from pipelines.transform_reviews import (
    clean_reviews,
    match_reviews_to_vehicle_scope,
)
from pipelines.transform_vehicles import (
    clean_vehicle_listings,
    scope_vehicle_model,
)


def _vehicle_rows():
    return pd.DataFrame(
        [
            {
                "id": 1,
                "price": 15000,
                "year": 2018,
                "manufacturer": "Honda",
                "model": "Civic Sedan",
                "odometer": 50000,
                "posting_date": "2021-04-01T12:00:00Z",
                "condition": "good",
                "fuel": "gas",
                "title_status": "clean",
                "transmission": "automatic",
                "drive": "fwd",
                "type": "sedan",
                "region": "austin",
                "state": "tx",
            },
            {
                "id": 1,
                "price": 15000,
                "year": 2018,
                "manufacturer": "Honda",
                "model": "Civic Sedan",
                "odometer": 50000,
                "posting_date": "2021-04-01T12:00:00Z",
            },
            {
                "id": 2,
                "price": 900,
                "year": 2018,
                "manufacturer": "Ford",
                "model": "Focus",
                "odometer": 50000,
                "posting_date": "2021-04-01T12:00:00Z",
            },
            {
                "id": 3,
                "price": 18000,
                "year": 2025,
                "manufacturer": "Toyota",
                "model": "Camry",
                "odometer": 50000,
                "posting_date": "2021-04-01T12:00:00Z",
            },
            {
                "id": 4,
                "price": 18000,
                "year": 2016,
                "manufacturer": "Toyota",
                "model": "Corolla LE",
                "odometer": 0,
                "posting_date": "2021-04-01T12:00:00Z",
            },
        ]
    )


def test_vehicle_cleaning_reproduces_core_rules():
    clean, audit = clean_vehicle_listings(_vehicle_rows())

    assert set(clean["id"].astype(str)) == {"1", "4"}
    assert clean.loc[clean["id"] == "1", "model_family"].iloc[0] == "civic sedan"
    assert clean.loc[clean["id"] == "4", "odometer_zero_flag"].iloc[0]
    assert "duplicate listing id" in set(audit["rule"])
    assert "price outside project range" in set(audit["rule"])
    assert "invalid vehicle year" in set(audit["rule"])


def test_vehicle_scope_keeps_top_make():
    clean, _ = clean_vehicle_listings(_vehicle_rows())
    scoped, top_makes = scope_vehicle_model(clean, top_n=1)

    assert len(top_makes) == 1
    assert scoped["manufacturer"].nunique() == 1


def test_review_cleaning_and_scope_matching():
    raw = pd.DataFrame(
        [
            {
                "Vehicle_Title": "2018 Honda Civic Sedan LX",
                "Review_Title": "Reliable",
                "Review": (
                    "This Civic has been reliable for commuting and has needed "
                    "only normal maintenance over several years."
                ),
                "Rating": 4.5,
                "Review_Date": "01/02/2020",
                "manufacturer": "honda",
                "source_file": "Scrapped_Car_Reviews_Honda.csv",
            },
            {
                "Vehicle_Title": "2018 Honda Civic Sedan LX",
                "Review_Title": "Reliable duplicate",
                "Review": (
                    "This Civic has been reliable for commuting and has needed "
                    "only normal maintenance over several years."
                ),
                "Rating": 4.5,
                "Review_Date": "01/02/2020",
                "manufacturer": "honda",
                "source_file": "Scrapped_Car_Reviews_Honda.csv",
            },
            {
                "Vehicle_Title": "2018 Honda Civic Sedan LX",
                "Review_Title": "Too short",
                "Review": "Short review",
                "Rating": 4.0,
                "Review_Date": "01/02/2020",
                "manufacturer": "honda",
                "source_file": "Scrapped_Car_Reviews_Honda.csv",
            },
        ]
    )

    reviews = clean_reviews(raw)
    assert len(reviews) == 1
    assert reviews.iloc[0]["vehicle_year"] == 2018
    assert reviews.iloc[0]["model_family"] == "civic sedan"

    vehicles = pd.DataFrame(
        [{"manufacturer": "honda", "model_family": "civic sedan"}]
    )
    with_match, matched = match_reviews_to_vehicle_scope(reviews, vehicles)

    assert with_match["matched_price_scope"].all()
    assert len(matched) == 1


def test_quality_gate_detects_bad_pipeline_run():
    vehicle_report = {"clean_retention_rate": 0.80}
    review_report = {
        "clean_retention_rate": 0.70,
        "price_scope_match_rate": 0.40,
    }

    result = evaluate_quality_gates(vehicle_report, review_report)

    assert result["status"] == "FAIL"
    assert result["checks"]["vehicle_clean_retention"] is True
    assert result["checks"]["review_match_rate"] is False



def test_end_to_end_pipeline_is_idempotent(tmp_path):
    vehicle_path = tmp_path / "vehicles.csv"
    review_dir = tmp_path / "reviews"
    review_dir.mkdir()
    output_dir = tmp_path / "output"

    vehicles = []
    for i in range(20):
        vehicles.append(
            {
                "id": i + 1,
                "price": 15000 + i * 100,
                "year": 2018,
                "manufacturer": "Honda",
                "model": "Civic Sedan",
                "odometer": 40000 + i * 1000,
                "posting_date": "2021-04-01T12:00:00Z",
                "condition": "good",
                "fuel": "gas",
                "title_status": "clean",
                "transmission": "automatic",
                "drive": "fwd",
                "type": "sedan",
                "region": "austin",
                "state": "tx",
            }
        )

    pd.DataFrame(vehicles).to_csv(vehicle_path, index=False)

    reviews = []
    for i in range(20):
        reviews.append(
            {
                "Vehicle_Title": "2018 Honda Civic Sedan LX",
                "Review_Title": "Reliable",
                "Review": (
                    "This Civic has been reliable for commuting and normal "
                    f"maintenance over several years. Review {i}."
                ),
                "Rating": 4.5,
                "Review_Date": "01/02/2020",
            }
        )

    pd.DataFrame(reviews).to_csv(
        review_dir / "Scrapped_Car_Reviews_Honda.csv",
        index=False,
    )

    first = run_pipeline(
        vehicles_csv=vehicle_path,
        reviews_dir=review_dir,
        output_dir=output_dir,
    )
    first_parts = sorted(
        p.relative_to(output_dir)
        for p in output_dir.rglob("*.parquet")
    )

    second = run_pipeline(
        vehicles_csv=vehicle_path,
        reviews_dir=review_dir,
        output_dir=output_dir,
    )
    second_parts = sorted(
        p.relative_to(output_dir)
        for p in output_dir.rglob("*.parquet")
    )

    assert first["manifest"]["run_id"] == second["manifest"]["run_id"]
    assert first_parts == second_parts
    assert (output_dir / "manifests" / "latest.json").exists()
    assert (output_dir / "quality" / "quality_gate.json").exists()
