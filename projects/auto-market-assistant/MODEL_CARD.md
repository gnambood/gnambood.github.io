# Model Card — Auto Market Assistant

## Intended use

The system provides historical Craigslist asking-price context from structured vehicle attributes and owner-review evidence retrieved from matched Edmunds consumer reviews.

It is a portfolio/research system, not a current appraisal or transaction-price service.

## Price model

- Model: CatBoost regression
- Modeling rows: 238,959
- Evaluation: chronological holdout
- Test MAE: $2,866
- Test RMSE: $5,020
- Test R²: 0.883
- Predictions within ±$5,000: 84.9%

## Retrieval system

- Matched review documents: 70,665
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Index: FAISS IndexFlatIP over normalized embeddings
- Vehicle Hit@5: 81.67%
- MRR@10: 0.6256
- Median retrieval latency: 19.59 ms
- p95 retrieval latency: 21.35 ms
- Generator in the final notebook run: Qwen/Qwen2.5-1.5B-Instruct

Generated source IDs are checked against retrieved reviews. If citation validation fails, the pipeline returns evidence-backed retrieved excerpts.

## Limitations

- Price data reflects 2021 Craigslist asking prices, not current values.
- Asking price is not the same as final transaction price.
- Retrieval metrics measure vehicle-identity retrieval behavior, not universal answer quality.
- Owner reviews are anecdotal and may disagree.
- The deployed AWS ECS API currently runs in retrieval-only fallback mode with ENABLE_GENERATION=false.
- The live service is intended as a portfolio deployment, not a continuously available commercial SLA.
