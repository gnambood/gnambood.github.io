# Verified raw-to-Parquet reconstruction (2026-10-10)

These five scripts are archived **exactly as used** in the independently validated CloudShell run `rebuild-20261010T061542Z`. They are historical reproduction evidence, not a portable command-line ETL package: they use fixed paths under `/tmp/auto-market-etl`, require input downloads and Python dependencies, and expect production Parquet references for the final equality assertions. Run them in an isolated workspace; do not overwrite production S3 objects.

## Verified data

| Artifact | Rows | Columns | SHA-256 |
| --- | ---: | ---: | --- |
| `vehicles_rebuilt.parquet` | 238,959 | 27 | `38507b957972da2b992ff298d94b69f0004f95cbbf31c0a04a9e65cf8d69dd72` |
| `reviews_rebuilt.parquet` | 70,665 | 9 | `793f54d8d0a3854e4da9f49a35b3f68e4245e11311d7ac7bb06a61997e0c9d20` |

The reconstruction passed bidirectional `EXCEPT ALL` comparison against the production Parquet references for **every column**, with zero missing records in either direction. Independently, Athena engine 3 confirmed production and staging counts, unique IDs, 10 manufacturers, and identical counts per manufacturer on both datasets.

AWS region: `ca-central-1`; Glue DB: `auto_market_curated`; Athena workgroup: `auto-market-analytics`.

The canonical, versioned evidence is in:

```
s3://auto-market-assistant-gayathri-2026/staging/etl-runs/rebuild-20261010T061542Z/
```

It contains rebuilt Parquet files, a manifest, validation logs, and the archived scripts under `scripts/`. Athena validation data is isolated in `athena-validation/vehicles/` and `athena-validation/reviews/`. Tables `vehicles_rebuild_validation` and `reviews_rebuild_validation` are separate from production tables.

Original inputs:

```
s3://auto-market-assistant-gayathri-2026/raw/snapshots/2026-10-08/craigslist/vehicles.csv.zip
s3://auto-market-assistant-gayathri-2026/raw/snapshots/2026-10-08/edmunds/edmunds_reviews.zip
```

The original Craigslist CSV SHA-256 was `54c60e20aa494a73f7f9170bff1e38b4800472b767cab8f9dab7da5dcc261a5c`. The Edmunds ZIP SHA-256 was `038cc10422112e99bcf9a037e9600fbd977007483d383698d59ffc694a828884`.

## Execution order and preconditions

1. Obtain the raw Craigslist ZIP and Edmunds ZIP; extract `vehicles.csv` and 50 Edmunds CSV files to the paths expected under `/tmp/auto-market-etl/raw/`.
2. Place production reference Parquet files under `/tmp/auto-market-etl/reference/`.
3. Install compatible `duckdb`, `pandas`, `numpy`, and `pyarrow`. Put the matching `pipelines/common.py`, `pipelines/transform_reviews.py`, and `pipelines/__init__.py` in `work/pipelines/`. These are also in the S3 scripts backup.
4. Execute `rebuild_vehicle_features.py`, `compare_remaining_vehicle_columns.py`, `package_vehicles.py`, and `package_reviews.py` in order.
5. Set `BUCKET` and `RUN_ID`, then run `create_lineage_manifest.py`. Recheck local SHA-256 hashes and upload to a **new** staging prefix.
6. Verify remote SHA-256 and run Athena comparisons. Do not replace `processed/` or `curated/` without separate deployment approval.

The original run calculated the price-extreme thresholds at the 1st and 99th percentiles ($1,600 and $64,999) *before* odometer filtering. A warning while parsing optional review dates did not affect the validated nine output columns.

## Scope

The scripts here prove reproducibility of the **data content**, not a new deployment of the price model, RAG system, or container. See the parent README, architecture, deployment, and data-pipeline documentation for those parts.
