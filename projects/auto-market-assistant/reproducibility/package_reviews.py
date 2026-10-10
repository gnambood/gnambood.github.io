import sys
import hashlib
from pathlib import Path

import pandas as pd
import duckdb

root = Path("/tmp/auto-market-etl")
sys.path.insert(0, str(root / "work"))

from pipelines.transform_reviews import (
    load_review_directory,
    clean_reviews,
    match_reviews_to_vehicle_scope,
)
from pipelines.common import model_family

makes = [
    "ford", "chevrolet", "toyota", "honda", "nissan",
    "jeep", "ram", "gmc", "bmw", "dodge",
]

print("===== REBUILD REVIEWS =====", flush=True)

raw, _ = load_review_directory(root / "raw/edmunds", makes)
clean = clean_reviews(raw)
del raw

vehicles = pd.read_parquet(
    root / "output/vehicles_rebuilt.parquet",
    columns=["manufacturer", "model"],
)
vehicles["model_family"] = vehicles["model"].map(model_family)

_, matched = match_reviews_to_vehicle_scope(clean, vehicles)
del clean, vehicles

def stable_review_id(row):
    value = (
        f"{row['manufacturer']}|{row['vehicle_title']}|"
        f"{row['review_title']}|{row['review_text']}"
    )
    return "edm_" + hashlib.sha1(
        value.encode("utf-8")
    ).hexdigest()[:12]

matched["review_id"] = matched.apply(stable_review_id, axis=1)

matched["document"] = (
    matched["vehicle_year"].astype(str)
    + " " + matched["manufacturer"]
    + " " + matched["model_family"]
    + ". " + matched["review_title"]
    + ". " + matched["review_text"].str.slice(0, 2500)
)

columns = [
    "review_id", "manufacturer", "vehicle_year",
    "model", "model_family", "rating",
    "review_title", "review_text", "document",
]

output = root / "output/reviews_rebuilt.parquet"
matched[columns].to_parquet(
    output, index=False, compression="zstd"
)

del matched

print("===== FULL NINE-COLUMN COMPARISON =====", flush=True)

con = duckdb.connect()
con.execute("SET threads=1")
con.execute("SET memory_limit='768MB'")

reference = root / "reference/review_documents.parquet"

# Compare schema and all records, preserving duplicate frequencies.
rebuilt_schema = con.execute(
    "DESCRIBE SELECT * FROM read_parquet(?)",
    [str(output)]
).fetchall()

reference_schema = con.execute(
    "DESCRIBE SELECT * FROM read_parquet(?)",
    [str(reference)]
).fetchall()

schema_matches = (
    [(r[0], r[1]) for r in rebuilt_schema]
    == [(r[0], r[1]) for r in reference_schema]
)

comparison = con.execute("""
WITH missing_from_production AS (
    SELECT * FROM read_parquet(?)
    EXCEPT ALL
    SELECT * FROM read_parquet(?)
),
missing_from_rebuild AS (
    SELECT * FROM read_parquet(?)
    EXCEPT ALL
    SELECT * FROM read_parquet(?)
)
SELECT
    (SELECT COUNT(*) FROM read_parquet(?)),
    (SELECT COUNT(*) FROM read_parquet(?)),
    (SELECT COUNT(*) FROM missing_from_production),
    (SELECT COUNT(*) FROM missing_from_rebuild)
""", [
    str(output), str(reference),
    str(reference), str(output),
    str(output), str(reference),
]).fetchone()

print("Rebuilt rows:", comparison[0])
print("Production rows:", comparison[1])
print("Missing from production:", comparison[2])
print("Missing from rebuild:", comparison[3])
print("Schema matches:", schema_matches)
print("Output:", output)
print("Output bytes:", output.stat().st_size)

passed = (
    comparison == (70665, 70665, 0, 0)
    and schema_matches
)

print(
    "\nFULL REVIEW PARQUET:",
    "PASS" if passed else "REVIEW REQUIRED"
)

con.close()

if not passed:
    raise SystemExit(1)
