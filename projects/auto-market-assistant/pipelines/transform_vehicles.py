import numpy as np
import pandas as pd

from .common import (
    OPTIONAL_VEHICLE_CATEGORIES,
    VEHICLE_TEXT_COLUMNS,
    model_family,
)


REQUIRED_VEHICLE_COLUMNS = {
    "id",
    "price",
    "year",
    "manufacturer",
    "model",
    "odometer",
    "posting_date",
}


def _apply_rule(data, mask, rule, audit):
    before = len(data)
    result = data.loc[mask].copy()
    after = len(result)
    audit.append(
        {
            "rule": rule,
            "rows_before": int(before),
            "rows_after": int(after),
            "rows_removed": int(before - after),
        }
    )
    return result


def clean_vehicle_listings(df):
    """Reproduce the validated Part 1 Craigslist cleaning rules."""
    missing = sorted(REQUIRED_VEHICLE_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(
            "Vehicle input is missing required columns: " + ", ".join(missing)
        )

    clean = df.copy()
    audit = []

    for col in OPTIONAL_VEHICLE_CATEGORIES + ["region", "state"]:
        if col not in clean.columns:
            clean[col] = pd.NA

    clean["price"] = pd.to_numeric(clean["price"], errors="coerce")
    clean["year"] = pd.to_numeric(clean["year"], errors="coerce")
    clean["odometer"] = pd.to_numeric(clean["odometer"], errors="coerce")
    clean["posting_date"] = pd.to_datetime(
        clean["posting_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    for col in VEHICLE_TEXT_COLUMNS:
        clean[col] = (
            clean[col]
            .astype("string")
            .str.lower()
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )

    clean["model"] = (
        clean["model"]
        .str.replace(r"[^a-z0-9]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    before = len(clean)
    clean = clean.drop_duplicates(subset="id").copy()
    audit.append(
        {
            "rule": "duplicate listing id",
            "rows_before": int(before),
            "rows_after": int(len(clean)),
            "rows_removed": int(before - len(clean)),
        }
    )

    required = [
        "price",
        "year",
        "manufacturer",
        "model",
        "odometer",
        "posting_date",
    ]
    clean = _apply_rule(
        clean,
        clean[required].notna().all(axis=1),
        "missing required fields",
        audit,
    )

    clean = _apply_rule(
        clean,
        clean["manufacturer"].ne("") & clean["model"].ne(""),
        "blank manufacturer or model",
        audit,
    )

    clean["posting_year"] = clean["posting_date"].dt.year
    valid_year = (clean["year"] >= 1990) & (
        clean["year"] <= clean["posting_year"] + 1
    )
    clean = _apply_rule(clean, valid_year, "invalid vehicle year", audit)

    clean["vehicle_age"] = (clean["posting_year"] - clean["year"]).clip(
        lower=0
    )

    clean = _apply_rule(
        clean,
        clean["price"].between(1000, 100000),
        "price outside project range",
        audit,
    )

    price_q01 = clean["price"].quantile(0.01)
    price_q99 = clean["price"].quantile(0.99)
    clean["price_extreme_flag"] = (clean["price"] < price_q01) | (
        clean["price"] > price_q99
    )

    clean = _apply_rule(
        clean,
        clean["odometer"].between(0, 300000),
        "invalid odometer",
        audit,
    )

    clean["odometer_zero_flag"] = (clean["odometer"] == 0) & (
        clean["vehicle_age"] > 2
    )

    for col in OPTIONAL_VEHICLE_CATEGORIES:
        clean[f"{col}_missing"] = clean[col].isna().astype("int8")
        clean[col] = clean[col].fillna("unknown")

    missing_flags = [
        f"{col}_missing" for col in OPTIONAL_VEHICLE_CATEGORIES
    ]
    clean["quality_issue_count"] = (
        clean[missing_flags].sum(axis=1)
        + clean["price_extreme_flag"].astype(int)
        + clean["odometer_zero_flag"].astype(int)
    )

    clean["quality_band"] = pd.cut(
        clean["quality_issue_count"],
        bins=[-1, 0, 2, np.inf],
        labels=["0 issues", "1-2 issues", "3+ issues"],
    )

    clean["model_family"] = clean["model"].map(model_family)
    clean["id"] = clean["id"].astype("string")

    for col in ["year", "posting_year", "vehicle_age"]:
        clean[col] = pd.to_numeric(clean[col], errors="coerce").astype("Int64")

    return clean.reset_index(drop=True), pd.DataFrame(audit)


def scope_vehicle_model(clean, top_n=10):
    """Keep the top-N manufacturers used by the final price-model scope."""
    counts = clean["manufacturer"].value_counts().head(top_n)
    top_makes = counts.index.tolist()
    scoped = clean[clean["manufacturer"].isin(top_makes)].copy()
    return scoped.reset_index(drop=True), top_makes
