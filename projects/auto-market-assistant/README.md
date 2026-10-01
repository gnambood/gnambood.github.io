# Auto Market Assistant

End-to-end used-car intelligence system combining a CatBoost price model, grounded owner-review retrieval, a FastAPI inference layer, Docker, and a live AWS deployment.

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
- median retrieval latency: 19.59 ms
- p95 retrieval latency: 21.35 ms
- Qwen 2.5 1.5B used in the final notebook run
- citation validation + evidence-backed fallback

## Live production deployment

The current deployment uses:

- GitHub Pages for the portfolio UI
- FastAPI for inference endpoints
- Docker for the application image
- Amazon ECR for image storage
- Amazon ECS Express Mode / Fargate for serving
- an AWS-managed HTTPS ingress/load-balancing layer
- Amazon S3 for model, FAISS, metrics and processed-data artifacts
- IAM task roles for least-privilege S3 access

Live API:

`https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws`

Endpoints:
- `POST /predict-price`
- `POST /ask`
- `GET /health`
- `GET /metrics`

The cloud service intentionally runs with `ENABLE_GENERATION=false`, so the live `/ask` endpoint returns deterministic retrieval-backed evidence. The final notebook separately evaluates Qwen generation with citation validation and fallback.

## S3 layout

```text
raw/
  craigslist/
  edmunds/
processed/
  vehicles_clean.parquet
  review_documents.parquet
artifacts/
  price_model.cbm
  model_improvement_metrics.json
  review_index.faiss
  rag_metrics.json
validation/
```

## Website behavior

The portfolio tries the live AWS API first. If the cloud request is unavailable or times out, it falls back to verified static output, so the demo remains usable even when compute is offline.

## Reproducing the portfolio data

1. Run the final Part 1 notebook and save `part1_artifacts.zip`.
2. Run the final Part 2 notebook using that fresh Part 1 bundle and save `part2_artifacts.zip`.
3. Upload the six deployment artifacts to the expected S3 paths.
4. Use `src/build_demo_json_from_artifacts.py` when a larger precomputed fallback set is needed.
5. Deploy the Docker API through ECR + ECS Express Mode.

## Large artifacts

Large Parquet files, FAISS indexes, embeddings, model binaries and ZIP bundles are intentionally excluded from Git. The live API loads its artifacts from S3.

## Scope and limitations

- Price outputs represent 2021 Craigslist asking-price context.
- Asking price is not a completed transaction price.
- Results should not be interpreted as current vehicle valuations.
- Retrieval metrics evaluate vehicle-identity retrieval behavior, not universal semantic answer quality.
- Owner reviews are anecdotal and may disagree.
