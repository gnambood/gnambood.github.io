# Production Architecture

## Request path

```text
GitHub Pages
    |
    | HTTPS
    v
AWS ECS Express Mode
    |
    +--> FastAPI /predict-price --> CatBoost
    |
    +--> FastAPI /ask --> MiniLM --> FAISS --> citation-safe retrieval fallback
    |
    +--> FastAPI /health
    |
    +--> FastAPI /metrics
            |
            v
          Amazon S3
```

The deployed ECS service runs on Fargate behind AWS-managed HTTPS ingress/load-balancing infrastructure.

## Deployment path

```text
GitHub
  -> GitHub Actions
  -> Docker build
  -> Amazon ECR
  -> ECS Express Mode service revision
```

## Artifact storage

S3 layout:

- `raw/craigslist/`
- `raw/edmunds/`
- `processed/vehicles_clean.parquet`
- `processed/review_documents.parquet`
- `artifacts/price_model.cbm`
- `artifacts/model_improvement_metrics.json`
- `artifacts/review_index.faiss`
- `artifacts/rag_metrics.json`
- `validation/`

The ECS task role has read-only access to the processed/model artifact prefixes.

## Data validation

Raw S3 uploads can trigger the Lambda schema/range validator defined in `infra/data-pipeline-template.yaml`.

## Portfolio resilience

The browser calls the live AWS API first. If the API is unavailable, the GitHub Pages demo falls back to verified static output. This keeps the portfolio usable without fabricating browser-side predictions.

## Generation policy

The production service currently sets `ENABLE_GENERATION=false` to keep the cloud deployment CPU-friendly and predictable. The final notebook evaluates Qwen 2.5 generation separately and validates cited review IDs before accepting generated text.
