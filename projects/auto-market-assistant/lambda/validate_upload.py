import csv
import io
import json
import os
from datetime import datetime, timezone
from urllib.parse import unquote_plus
import boto3

s3 = boto3.client("s3")
MAX_ROWS = int(os.getenv("MAX_VALIDATION_ROWS", "5000"))

LISTING_REQUIRED = {"id", "price", "year", "manufacturer", "model", "odometer", "posting_date"}
REVIEW_REQUIRED = {"Vehicle_Title", "Review_Title", "Review"}

def _validate_csv(bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    stream = io.TextIOWrapper(obj["Body"], encoding="utf-8", errors="replace")
    reader = csv.DictReader(stream)
    columns = set(reader.fieldnames or [])
    lower_key = key.lower()

    if "craigslist" in lower_key or "vehicle" in lower_key:
        dataset, required = "listings", LISTING_REQUIRED
    elif "edmund" in lower_key or "review" in lower_key:
        dataset, required = "reviews", REVIEW_REQUIRED
    else:
        dataset, required = "unknown", set()

    missing = sorted(required - columns)
    issues = []
    checked = 0

    for row in reader:
        checked += 1
        if checked > MAX_ROWS:
            break

        if dataset == "listings":
            try:
                price = float(row.get("price") or "nan")
                if not (0 <= price <= 1_000_000):
                    issues.append(f"row {checked}: price out of range")
            except ValueError:
                issues.append(f"row {checked}: invalid price")

            try:
                odometer = float(row.get("odometer") or "nan")
                if not (0 <= odometer <= 500_000):
                    issues.append(f"row {checked}: odometer out of range")
            except ValueError:
                issues.append(f"row {checked}: invalid odometer")

            if not str(row.get("manufacturer", "")).strip():
                issues.append(f"row {checked}: blank manufacturer")
            if not str(row.get("model", "")).strip():
                issues.append(f"row {checked}: blank model")

        if len(issues) >= 100:
            break

    return {
        "dataset": dataset,
        "status": "passed" if not missing and not issues else "failed",
        "columns": sorted(columns),
        "missing_required_columns": missing,
        "sampled_rows": checked,
        "sample_issues": issues[:100],
    }

def handler(event, context):
    results = []

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        result = {"bucket": bucket, "key": key, "validated_at": datetime.now(timezone.utc).isoformat()}

        if not key.lower().endswith(".csv"):
            result.update({"status": "skipped", "reason": "validator currently checks raw CSV uploads"})
        else:
            result.update(_validate_csv(bucket, key))

        validation_key = "validation/" + key.replace("/", "__") + ".validation.json"
        s3.put_object(
            Bucket=bucket,
            Key=validation_key,
            Body=json.dumps(result, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        results.append(result)

        if result["status"] == "failed":
            raise ValueError(json.dumps(result))

    return {"results": results}
