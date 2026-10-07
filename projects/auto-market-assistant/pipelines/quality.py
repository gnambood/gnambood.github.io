from datetime import datetime, timezone


DEFAULT_GATES = {
    "vehicle_clean_retention_min": 0.75,
    "review_clean_retention_min": 0.65,
    "review_match_rate_min": 0.60,
}


def vehicle_quality_report(raw_rows, clean_rows, scoped_rows, audit, clean_df):
    retention = clean_rows / raw_rows if raw_rows else 0.0
    scope_rate = scoped_rows / clean_rows if clean_rows else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_rows": int(raw_rows),
        "clean_rows": int(clean_rows),
        "scoped_model_rows": int(scoped_rows),
        "clean_retention_rate": float(retention),
        "model_scope_rate": float(scope_rate),
        "extreme_price_flags": int(clean_df["price_extreme_flag"].sum()),
        "suspicious_zero_mileage_flags": int(
            clean_df["odometer_zero_flag"].sum()
        ),
        "cleaning_rules": audit.to_dict(orient="records"),
    }


def review_quality_report(raw_rows, clean_rows, matched_rows, load_metadata):
    retention = clean_rows / raw_rows if raw_rows else 0.0
    match_rate = matched_rows / clean_rows if clean_rows else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_rows": int(raw_rows),
        "clean_rows": int(clean_rows),
        "matched_rows": int(matched_rows),
        "clean_retention_rate": float(retention),
        "price_scope_match_rate": float(match_rate),
        "selected_files": load_metadata["selected_files"],
        "fallback_parser_files": load_metadata["fallback_files"],
    }


def evaluate_quality_gates(vehicle_report, review_report, gates=None):
    gates = {**DEFAULT_GATES, **(gates or {})}

    checks = {
        "vehicle_clean_retention": (
            vehicle_report["clean_retention_rate"]
            >= gates["vehicle_clean_retention_min"]
        ),
        "review_clean_retention": (
            review_report["clean_retention_rate"]
            >= gates["review_clean_retention_min"]
        ),
        "review_match_rate": (
            review_report["price_scope_match_rate"]
            >= gates["review_match_rate_min"]
        ),
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "thresholds": gates,
        "checks": checks,
    }
