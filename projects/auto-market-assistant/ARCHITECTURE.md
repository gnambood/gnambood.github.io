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
    +--> FastAPI /ask
              --> capability/scope guard
              --> vehicle-family/year candidate filter
              --> question-only MiniLM retrieval
              --> calibrated multi-signal evidence gate
              --> citation-safe retrieval response
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

The production service currently sets `ENABLE_GENERATION=false` to keep the cloud deployment CPU-friendly and predictable. The final notebook separately validates Qwen 2.5 generation using short source aliases that are mapped back to real `edm_*` IDs before final citation validation.

## Answerability policy

The deployed retrieval gate uses the validated operating point:

- max similarity ≥ 0.38
- mean top-3 similarity ≥ 0.36 **or** at least 2 sources with similarity ≥ 0.34

The scope guard handles exact-vehicle condition/history, current transactional data and authoritative specifications before retrieval relevance is considered.

The policy came from a held-out weakly supervised benchmark across unseen vehicle families. It is not described as universal RAG accuracy.
