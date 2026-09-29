# Auto Market Assistant

End-to-end used-car intelligence system combining a CatBoost price model with grounded owner-review retrieval, a FastAPI inference layer, and an AWS deployment path.

## What it does

The system separates two questions that should not be mixed:

- How much is this vehicle worth in the historical listing market?
- What do owners actually report about the vehicle?

Price estimates come from a structured CatBoost model. Owner-experience answers come from retrieved Edmunds reviews with citation validation and a safe evidence fallback.

## Final measured results

### Price model
- 238,959 modeling rows
- chronological holdout
- test MAE: $2,866
- test R²: 0.883
- 84.9% of held-out predictions within ±$5,000

### Owner-review retrieval
- 70,665 matched reviews
- MiniLM embeddings
- FAISS retrieval
- Hit@5: 81.67%
- MRR@10: 0.6256
- median retrieval latency: 21.15 ms
- Qwen 2.5 1.5B used in the final notebook run
- citation validation + evidence-backed fallback

## Production extension

The repository now includes:

- FastAPI endpoints:
  - POST /predict-price
  - POST /ask
  - GET /health
  - GET /metrics
- Docker container definition
- S3 artifact loading
- S3 raw-data validation Lambda
- AWS SAM template for the data bucket + validator
- AWS App Runner / ECR deployment template
- GitHub Actions CI
- GitHub Actions deployment workflow
- model card and architecture documentation
- static verified JSON fallback for GitHub Pages

## S3 layout

raw/
- craigslist/
- edmunds/

processed/
- vehicles_clean.parquet
- review_documents.parquet

artifacts/
- price_model.cbm
- model_improvement_metrics.json
- review_index.faiss
- rag_metrics.json

validation/
- raw-upload validation reports

## Website architecture

The portfolio supports two modes:

1. verified static demo data generated from the trained pipeline;
2. live API calls after the AWS App Runner service is deployed.

The static fallback prevents the portfolio from breaking if the cloud service is unavailable.

## Reproducing the exact portfolio data

1. Restore the Part 1 artifact bundle.
2. Restore the Part 2 artifact bundle.
3. Run src/build_demo_json_from_artifacts.py in Colab or the project runtime.
4. Commit the generated auto-market-demo-data.json to the Pages root.
5. The portfolio automatically loads the exact exported presets.

## Large artifacts

Large Parquet files, FAISS indexes, embeddings, model binaries and ZIP bundles are intentionally excluded from Git. The deployment service loads them from S3.

## Scope and limitations

- Price outputs represent 2021 Craigslist asking-price context.
- Asking price is not a completed transaction price.
- Results should not be interpreted as current vehicle valuations.
- Retrieval metrics evaluate vehicle-identity retrieval behavior, not universal semantic answer quality.
- Owner reviews are anecdotal and may disagree.
