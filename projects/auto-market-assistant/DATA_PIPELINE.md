# Data Engineering Layer

The data-engineering layer exists because the same cleaned data now feeds four consumers: CatBoost training, FAISS/RAG, the FastAPI service, and Tableau/Athena analytics. Keeping those transformations only inside notebooks would make the consumers easy to drift apart.

## Architecture

```text
Craigslist CSVs            Edmunds review CSVs
      |                            |
      +-------------+--------------+
                    |
             reusable batch ETL
                    |
          schema + quality gates
             /              \
            /                \
   curated vehicles     curated reviews
            \                /
             \-- scope match /
                    |
          matched review dataset
                    |
      +-------------+-------------+
      |             |             |
   CatBoost      FAISS/RAG      Analytics
                                  |
                            Glue Data Catalog
                                  |
                                Athena
                                  |
                         Tableau / QA extracts
```

## Reused notebook logic

The pipeline intentionally reproduces the rules that produced the validated project artifacts rather than creating a second cleaning definition.

Vehicle processing includes text normalization, listing-ID deduplication, required-field checks, historical-year validation, the $1K-$100K price scope, the 0-300K mileage scope, optional-field missing flags, input-quality bands, model-family normalization, and the top-10-make modeling boundary.

The validated run moved from **426,880 raw listings → 348,506 clean listings → 238,959 modeling rows**.

Review processing loads only supported makes, uses the same fallback parser for malformed long-text CSVs, canonicalizes review columns, removes missing/short/duplicate reviews, parses year/model family, and measures the match to the price-model scope.

The validated RAG run moved from **137,660 raw reviews → 102,546 clean reviews → 70,665 matched reviews**.

## Curated layout

```text
curated/
  vehicles/manufacturer=.../
  reviews/manufacturer=.../
  vehicle_review_matches/manufacturer=.../

quality/
  vehicle_cleaning_audit.csv
  vehicle_quality.json
  review_quality.json
  quality_gate.json

manifests/
  pipeline_<source-fingerprint>.json
  latest.json
```

Outputs are Parquet and partitioned by manufacturer because manufacturer is low-cardinality and frequently used in model-error, review-coverage, and dashboard queries.

## Data-quality gates

The run fails before publishing when it falls below:

| Check | Minimum |
|---|---:|
| Vehicle clean-row retention | 75% |
| Review clean-row retention | 65% |
| Review-to-price-scope match rate | 60% |

These are operational drift checks, not model thresholds.

## Lineage

Every input file is SHA-256 hashed. The combined fingerprint becomes the run ID and is written to a manifest with row counts, selected makes, gate results, output paths, and generation time. That makes it possible to trace a curated dataset back to the exact source snapshot.

## Run

```bash
pip install -r requirements-data.txt

python -m pipelines.run_pipeline \
  --vehicles-csv /path/to/vehicles.csv \
  --reviews-dir /path/to/edmunds_reviews \
  --output-dir ./data-platform-output
```

S3 publication is opt-in:

```bash
python -m pipelines.run_pipeline \
  --vehicles-csv /path/to/vehicles.csv \
  --reviews-dir /path/to/edmunds_reviews \
  --output-dir ./data-platform-output \
  --s3-bucket <artifact-bucket>
```

The publisher uploads deterministic keys and does not delete existing S3 prefixes. S3 versioning already preserves prior object versions.

## Glue + Athena

`infra/data-catalog-template.yaml` defines a Glue database, three external Parquet tables, partition projection for the supported manufacturers, and an Athena workgroup with CloudWatch metrics plus a 1 GiB scan cutoff.

Reusable queries in `sql/` cover vehicle quality, matched-review coverage, and pipeline row-count reconciliation.

The catalog stack is intentionally separate from application CI/CD because creating/querying analytics resources can incur AWS charges.

## Why this design

- **Pandas, not Spark:** hundreds of thousands of rows do not justify a distributed cluster.
- **Glue as catalog, not ETL engine:** the validated transformation logic stays portable and testable Python.
- **Batch, not streaming:** both source datasets are snapshots rather than real-time event streams.
- **Manufacturer partitioning:** useful pruning without a small-file explosion.
