"""Export exact, precomputed portfolio-demo results.

Run this after the final Part 2 notebook has created:
- vehicles
- review_docs
- TOP_MAKES
- MARKET_YEAR
- get_market_context()
- retrieve_reviews()
- summarize_owner_reviews()

The website reads the generated auto-market-demo-data.json directly.
"""

from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

DEMO_OUT = Path("/content/auto-market-demo-data.json")
DEMO_QUESTIONS = {
    "reliability": "What do owners mention about reliability and common problems?",
    "comfort": "What do owners say about comfort and daily driving?",
    "fuel_economy": "What do owners say about fuel economy?",
}
DEMO_CONDITIONS = ["excellent", "good", "fair"]


def _mode_or_none(series):
    s = series.dropna().astype(str)
    return None if s.empty else s.mode().iloc[0]


def _display_model(model):
    tokens = str(model).split()
    if len(tokens) == 2 and len(tokens[0]) <= 2 and tokens[1].isdigit():
        return f"{tokens[0].upper()}-{tokens[1]}"
    return " ".join(
        t.upper() if len(t) <= 3 and any(ch.isalpha() for ch in t) else t.title()
        for t in tokens
    )


def build_demo_data():
    price_cov = (
        vehicles.groupby(["manufacturer", "model_family"], observed=True)
        .size().rename("price_rows")
    )
    review_cov = (
        review_docs.groupby(["manufacturer", "model_family"], observed=True)
        .size().rename("review_rows")
    )
    coverage = pd.concat([price_cov, review_cov], axis=1).fillna(0).reset_index()
    coverage["coverage_score"] = np.sqrt(
        coverage["price_rows"] * coverage["review_rows"]
    )

    selected = {}

    for make in TOP_MAKES:
        candidates = coverage[
            coverage["manufacturer"].eq(make)
            & coverage["price_rows"].ge(50)
            & coverage["review_rows"].ge(25)
        ].sort_values("coverage_score", ascending=False)

        if candidates.empty:
            candidates = coverage[
                coverage["manufacturer"].eq(make)
                & coverage["price_rows"].gt(0)
                & coverage["review_rows"].gt(0)
            ].sort_values("coverage_score", ascending=False)

        if candidates.empty:
            continue

        family = candidates.iloc[0]["model_family"]

        price_group = vehicles[
            vehicles["manufacturer"].eq(make)
            & vehicles["model_family"].eq(family)
        ].copy()

        review_group = review_docs[
            review_docs["manufacturer"].eq(make)
            & review_docs["model_family"].eq(family)
        ].copy()

        exact_model = (
            price_group["model"].dropna().astype(str).value_counts().index[0]
        )

        price_year = (
            price_group.groupby("vehicle_year", observed=True)
            .size().rename("price_rows")
        )
        review_year = (
            review_group.dropna(subset=["vehicle_year"])
            .groupby("vehicle_year", observed=True)
            .size().rename("review_rows")
        )

        year_cov = pd.concat(
            [price_year, review_year], axis=1
        ).fillna(0).reset_index()

        year_cov = year_cov[
            year_cov["price_rows"].gt(0)
            & year_cov["review_rows"].gt(0)
            & year_cov["vehicle_year"].between(1990, MARKET_YEAR)
        ].copy()

        year_cov["score"] = np.sqrt(
            year_cov["price_rows"] * year_cov["review_rows"]
        )

        years = (
            year_cov.sort_values("score", ascending=False)
            .head(3)["vehicle_year"].astype(int).tolist()
        )

        if not years:
            years = [int(price_group["vehicle_year"].dropna().mode().iloc[0])]

        years = sorted(set(years), reverse=True)

        odom = pd.to_numeric(
            price_group["odometer"], errors="coerce"
        ).dropna()

        if odom.empty:
            mileages = [50000, 100000, 150000]
        else:
            mileages = sorted(set(
                int(np.clip(
                    round(float(odom.quantile(q)) / 5000) * 5000,
                    5000,
                    250000,
                ))
                for q in [0.25, 0.50, 0.75]
            ))

        defaults = {
            "fuel": _mode_or_none(price_group["fuel"]),
            "title_status": _mode_or_none(price_group["title_status"]),
            "transmission": _mode_or_none(price_group["transmission"]),
            "drive": _mode_or_none(price_group["drive"]),
            "vehicle_type": _mode_or_none(price_group["type"]),
            "state": _mode_or_none(price_group["state"]),
        }

        key = re.sub(
            r"[^a-z0-9]+",
            "-",
            f"{make}-{family}".lower(),
        ).strip("-")

        selected[key] = {
            "display_make": make.title() if make != "bmw" else "BMW",
            "display_model": _display_model(exact_model),
            "make": make,
            "model": exact_model,
            "model_family": family,
            "years": years,
            "mileages": mileages,
            "conditions": DEMO_CONDITIONS,
            "defaults": defaults,
            "price_grid": {},
            "reviews": {},
            "coverage": {
                "price_rows": int(len(price_group)),
                "review_rows": int(len(review_group)),
            },
        }

    for vehicle in selected.values():
        d = vehicle["defaults"]

        for year in vehicle["years"]:
            for mileage in vehicle["mileages"]:
                for condition in vehicle["conditions"]:
                    ctx = get_market_context(
                        make=vehicle["make"],
                        model=vehicle["model"],
                        vehicle_year=year,
                        mileage=mileage,
                        condition=condition,
                        fuel=d["fuel"],
                        title_status=d["title_status"],
                        transmission=d["transmission"],
                        drive=d["drive"],
                        vehicle_type=d["vehicle_type"],
                        state=d["state"],
                    )

                    vehicle["price_grid"][
                        f"{year}|{mileage}|{condition}"
                    ] = {
                        k: (
                            v.item()
                            if isinstance(v, np.generic)
                            else v
                        )
                        for k, v in ctx.items()
                    }

    for vehicle in selected.values():
        for year in vehicle["years"]:
            for qkey, question in DEMO_QUESTIONS.items():
                retrieved, scope = retrieve_reviews(
                    question=question,
                    make=vehicle["make"],
                    model=vehicle["model"],
                    year=year,
                    k=5,
                )

                if retrieved.empty:
                    result = {
                        "answer": "Not enough review evidence for this vehicle.",
                        "citation_valid": False,
                        "fallback_used": False,
                    }
                else:
                    result = summarize_owner_reviews(
                        question,
                        retrieved,
                    )

                sources = []

                for _, row in retrieved.head(5).iterrows():
                    sources.append({
                        "review_id": str(row["review_id"]),
                        "vehicle_year": (
                            int(row["vehicle_year"])
                            if pd.notna(row["vehicle_year"])
                            else None
                        ),
                        "rating": (
                            float(row["rating"])
                            if pd.notna(row["rating"])
                            else None
                        ),
                        "review_title": str(row["review_title"]),
                        "excerpt": re.sub(
                            r"\s+",
                            " ",
                            str(row["review_text"]),
                        ).strip()[:260],
                    })

                vehicle["reviews"][f"{year}|{qkey}"] = {
                    "heading": {
                        "reliability": "Reliability & common problems",
                        "comfort": "Comfort & daily driving",
                        "fuel_economy": "Fuel-economy owner evidence",
                    }[qkey],
                    "question": question,
                    "answer": result["answer"],
                    "citation_valid": bool(
                        result["citation_valid"]
                    ),
                    "fallback_used": bool(
                        result["fallback_used"]
                    ),
                    "scope": scope,
                    "sources": sources,
                }

    return {
        "schema_version": 1,
        "generated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "market_year": int(MARKET_YEAR),
        "source_note": (
            "Precomputed from the trained CatBoost price model "
            "and Edmunds owner-review retrieval pipeline."
        ),
        "questions": DEMO_QUESTIONS,
        "vehicles": selected,
    }


if __name__ == "__main__":
    data = build_demo_data()

    with open(DEMO_OUT, "w") as f:
        json.dump(data, f, indent=2)

    print("Created:", DEMO_OUT)
    print("Vehicle presets:", len(data["vehicles"]))
    print(
        "JSON size KB:",
        round(DEMO_OUT.stat().st_size / 1024, 1),
    )
