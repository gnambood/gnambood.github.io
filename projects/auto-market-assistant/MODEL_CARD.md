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
- Median retrieval latency: 17.56 ms
- p95 retrieval latency: 21.11 ms
- Answerability policy: max 0.38, mean top-3 0.36, support 0.34, minimum 2 supporting sources
- Held-out weakly supervised answerability: 80.95% accuracy, 90.0% precision, 84.38% recall, 87.10% F1
- Scope-guard regression suite: 100% pass rate
- Generator in the final notebook run: Qwen/Qwen2.5-1.5B-Instruct

The final notebook uses short source aliases for Qwen, maps them back to real review IDs, and validates the mapped citations. The deployed CPU service keeps generation disabled and returns deterministic evidence-backed retrieval output.

## Limitations

- Price data reflects 2021 Craigslist asking prices, not current values.
- Asking price is not the same as final transaction price.
- Retrieval Hit@k/MRR metrics measure vehicle-identity retrieval behavior, not universal answer quality.
- Answerability metrics are from a weakly supervised held-out benchmark across unseen vehicle families and are not a universal RAG score.
- Owner reviews are anecdotal and may disagree.
- The deployed AWS ECS API currently runs in retrieval-only fallback mode with ENABLE_GENERATION=false.
- The live service is intended as a portfolio deployment, not a continuously available commercial SLA.
