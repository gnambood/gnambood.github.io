# Production Architecture

GitHub -> GitHub Actions -> Docker -> Amazon ECR -> AWS App Runner

App Runner exposes:
- POST /predict-price -> CatBoost
- POST /ask -> MiniLM + FAISS -> optional Qwen -> citation validation -> safe fallback
- GET /health
- GET /metrics

S3 layout:
- raw/craigslist/
- raw/edmunds/
- processed/vehicles_clean.parquet
- processed/review_documents.parquet
- artifacts/price_model.cbm
- artifacts/model_improvement_metrics.json
- artifacts/review_index.faiss
- artifacts/rag_metrics.json
- validation/

Raw S3 uploads trigger a Lambda schema/range validator.

The static GitHub Pages demo keeps auto-market-demo-data.json as a verified fallback, so the portfolio remains usable if the cloud API is unavailable.
