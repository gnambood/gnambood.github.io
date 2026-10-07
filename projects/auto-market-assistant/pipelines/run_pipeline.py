import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .common import combined_fingerprint, file_sha256
from .io import (
    publish_directory_to_s3,
    write_json,
    write_partitioned_parquet,
)
from .quality import (
    evaluate_quality_gates,
    review_quality_report,
    vehicle_quality_report,
)
from .transform_reviews import (
    clean_reviews,
    load_review_directory,
    match_reviews_to_vehicle_scope,
)
from .transform_vehicles import (
    clean_vehicle_listings,
    scope_vehicle_model,
)


def run_pipeline(
    vehicles_csv,
    reviews_dir,
    output_dir,
    top_n=10,
    s3_bucket=None,
    s3_prefix="",
):
    """Build deterministic curated datasets and data-quality artifacts."""
    vehicles_csv = Path(vehicles_csv)
    reviews_dir = Path(reviews_dir)
    output_dir = Path(output_dir)

    review_files = sorted(reviews_dir.rglob("*.csv"))
    fingerprint = combined_fingerprint([vehicles_csv, *review_files])
    run_id = fingerprint[:12]

    raw_vehicles = pd.read_csv(vehicles_csv, low_memory=False)
    clean_vehicles, cleaning_audit = clean_vehicle_listings(raw_vehicles)
    scoped_vehicles, top_makes = scope_vehicle_model(
        clean_vehicles, top_n=top_n
    )

    raw_reviews, review_load = load_review_directory(reviews_dir, top_makes)
    clean_review_df = clean_reviews(raw_reviews)
    reviews_with_match, matched_reviews = match_reviews_to_vehicle_scope(
        clean_review_df,
        scoped_vehicles,
    )

    vehicle_report = vehicle_quality_report(
        raw_rows=len(raw_vehicles),
        clean_rows=len(clean_vehicles),
        scoped_rows=len(scoped_vehicles),
        audit=cleaning_audit,
        clean_df=clean_vehicles,
    )
    review_report = review_quality_report(
        raw_rows=len(raw_reviews),
        clean_rows=len(clean_review_df),
        matched_rows=len(matched_reviews),
        load_metadata=review_load,
    )
    quality_gate = evaluate_quality_gates(vehicle_report, review_report)

    if quality_gate["status"] != "PASS":
        raise RuntimeError(
            "Data quality gates failed: " + json.dumps(quality_gate)
        )

    curated_root = output_dir / "curated"
    quality_root = output_dir / "quality"
    manifest_root = output_dir / "manifests"

    write_partitioned_parquet(
        scoped_vehicles,
        curated_root / "vehicles",
        partition_cols=["manufacturer"],
    )
    write_partitioned_parquet(
        reviews_with_match,
        curated_root / "reviews",
        partition_cols=["manufacturer"],
    )
    write_partitioned_parquet(
        matched_reviews,
        curated_root / "vehicle_review_matches",
        partition_cols=["manufacturer"],
    )

    quality_root.mkdir(parents=True, exist_ok=True)
    cleaning_audit.to_csv(
        quality_root / "vehicle_cleaning_audit.csv",
        index=False,
    )
    write_json(vehicle_report, quality_root / "vehicle_quality.json")
    write_json(review_report, quality_root / "review_quality.json")
    write_json(quality_gate, quality_root / "quality_gate.json")

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "vehicles_csv": str(vehicles_csv),
            "vehicles_sha256": file_sha256(vehicles_csv),
            "review_files": [
                {"name": path.name, "sha256": file_sha256(path)}
                for path in review_files
            ],
        },
        "rows": {
            "vehicle_raw": int(len(raw_vehicles)),
            "vehicle_clean": int(len(clean_vehicles)),
            "vehicle_model_scope": int(len(scoped_vehicles)),
            "review_raw": int(len(raw_reviews)),
            "review_clean": int(len(clean_review_df)),
            "review_matched": int(len(matched_reviews)),
        },
        "top_makes": top_makes,
        "quality_gate": quality_gate,
        "outputs": {
            "vehicles": "curated/vehicles/",
            "reviews": "curated/reviews/",
            "vehicle_review_matches": "curated/vehicle_review_matches/",
        },
    }

    manifest_path = manifest_root / f"pipeline_{run_id}.json"
    write_json(manifest, manifest_path)
    write_json(manifest, manifest_root / "latest.json")

    uploaded = []
    if s3_bucket:
        uploaded = publish_directory_to_s3(
            output_dir,
            s3_bucket,
            prefix=s3_prefix,
        )

    return {
        "manifest": manifest,
        "local_output": str(output_dir),
        "uploaded": uploaded,
    }


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Build validated curated datasets for Auto Market Assistant."
        )
    )
    parser.add_argument("--vehicles-csv", required=True)
    parser.add_argument("--reviews-dir", required=True)
    parser.add_argument("--output-dir", default="data-platform-output")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--s3-bucket")
    parser.add_argument("--s3-prefix", default="")
    return parser


def main():
    args = build_parser().parse_args()
    result = run_pipeline(
        vehicles_csv=args.vehicles_csv,
        reviews_dir=args.reviews_dir,
        output_dir=args.output_dir,
        top_n=args.top_n,
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
    )
    print(json.dumps(result["manifest"], indent=2))


if __name__ == "__main__":
    main()
