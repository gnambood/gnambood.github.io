# Auto Market Assistant

End-to-end used-car intelligence project combining a CatBoost price model with grounded owner-review retrieval.

## How the portfolio demo stays exact

GitHub Pages does **not** run CatBoost, FAISS, or Qwen in the browser. The trained pipeline exports a compact `auto-market-demo-data.json` containing real, precomputed outputs. The website reads that JSON directly.

```text
trained CatBoost + cleaned listings
              |
MiniLM + FAISS + Qwen + citation validation
              |
              v
   auto-market-demo-data.json
              |
              v
   GitHub Pages interactive demo
```

## Final measured results

**Price model**
- Test MAE: $2,866
- Test R²: 0.883
- 84.9% within ±$5,000
- Chronological holdout evaluation

**Owner-review retrieval**
- 70,665 matched review documents
- Vehicle Hit@5: 81.67%
- MRR@10: 0.6256
- Median retrieval latency: 21.15 ms
- Qwen 2.5 1.5B on CUDA
- Citation validation with evidence-backed fallback

## Reproduce the website data

1. Run or restore the final Part 1 artifacts.
2. Run the final Part 2 pipeline.
3. Run `src/export_demo_data.py` in the Part 2 notebook/runtime.
4. Commit the generated `auto-market-demo-data.json` to the root of the Pages repo.
5. `auto-market-assistant.html` loads those exact presets automatically.

## Large artifacts

Parquet datasets, FAISS indexes, embeddings, CatBoost binaries, and ZIP bundles are intentionally excluded from the Pages repository. They are build/runtime artifacts and would unnecessarily bloat a static website repository.

Price outputs are historical **2021 Craigslist asking-price context**, not current valuations or transaction sale prices.
