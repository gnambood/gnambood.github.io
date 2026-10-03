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

### Owner-review retrieval and answerability
- 70,665 matched reviews
- MiniLM embeddings + FAISS retrieval
- Hit@5: 81.67%
- MRR@10: 0.6256
- median retrieval latency: 17.56 ms
- p95 retrieval latency: 21.11 ms
- calibrated multi-signal evidence gate: max similarity 0.38, mean top-3 0.36, support threshold 0.34, minimum 2 supporting sources
- held-out weakly supervised answerability benchmark: 80.95% accuracy, 90.0% precision, 84.38% recall, 87.10% F1
- scope-guard regression suite: 100% pass rate
- Qwen 2.5 1.5B used in the final notebook run with source-alias citation mapping and validation
- deterministic evidence fallback retained for production safety

The answerability benchmark is intentionally described as a **held-out weakly supervised benchmark across unseen vehicle families**, not as universal “RAG accuracy.”

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

The cloud service intentionally runs with `ENABLE_GENERATION=false`, so the live `/ask` endpoint returns deterministic retrieval-backed evidence. The final notebook separately validates Qwen generation with short source aliases, citation mapping, and fallback.

The production RAG path is now:

```text
scope/capability guard
        ↓
vehicle-family/year filtering
        ↓
question-only MiniLM retrieval
        ↓
calibrated multi-signal evidence gate
        ↓
grounded evidence response
        ↓
citation validation
```

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
- Retrieval Hit@k/MRR metrics evaluate vehicle-identity retrieval behavior, not universal semantic answer quality.
- The answerability metrics come from a weakly supervised held-out benchmark and should not be treated as a universal RAG score.
- Owner reviews are anecdotal and may disagree.

## Future work

The next research-oriented improvements would be:

- build a manually labelled gold set of question-review pairs for direct relevance grading,
- compare MiniLM dense retrieval with cross-encoder reranking on the same labels,
- test passage/sentence chunking instead of whole-review embeddings,
- compare newer retrieval embeddings such as BGE or E5 using the same benchmark,
- add claim-level faithfulness/entailment evaluation for generated answers,
- evaluate whether a managed or larger production generator improves synthesis enough to justify additional latency and infrastructure cost.

These are intentionally left as future work because the current portfolio goal is an end-to-end, production-oriented ML system rather than a RAG research benchmark.
