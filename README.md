# Gayathri Namboodiri — portfolio website

This is the **GitHub Pages presentation layer**, not an ML application repository.

- `index.html`: lightweight professional homepage.
- `auto-market-assistant.html`: interactive, browser-only case study showing *saved* price estimates and cited owner-review evidence. The site does not execute a model or contact AWS.
- `data/auto-market-snapshots.v1.json`: small, published snapshot of prior verified inference and project-level evaluation. One 2004 Ford F-150 scenario is currently included; other vehicles must not be invented.
- `scripts/auto-market-demo.js`: same-origin JSON loader and browser interactions (quartile/median comparisons, review-source inspection, and evaluation views).
- `scripts/check_portfolio.py` and `tests/auto-market-offline.mjs`: data, website and browser tests that reject AWS requests.
- `.github/workflows/auto-market-deploy.yml`: a **manual** AWS deployment bridge. It checks out the actual canonical application repository; it does not contain application source.

**Canonical engineering project:** https://github.com/gnambood/auto-market-assistant

That repository owns the API, models, data pipeline, Vehicle Market Intelligence implementation and viewer, evaluation artifacts, tests, and technical documentation. Do not reintroduce `projects/auto-market-assistant/` or duplicate technical implementation here.

**Research:** Driver impairment code is private. The portfolio summarizes the research without implying that unpublished data or private code can be accessed publicly.

**GitHub profile README:** `PROFILE_README.md` is a prepared draft. GitHub displays a profile README only after the file is copied as `README.md` to a *public* repository named exactly `gnambood`.

## How the no-AWS demonstration works

GitHub Pages serves the HTML, JavaScript, and JSON as static files. When a visitor clicks **Explore saved result**, JavaScript reads only the precomputed local snapshot. Benchmark comparisons are arithmetic on saved numbers; citations show saved review IDs and titles. Unsupported questions are clearly labelled as **not in the saved snapshot**. No live model, external script, paid compute, or external API is required for this website.

The existing evidence currently supports **one** published F-150 example with a saved CatBoost estimate, comparable quartiles and three citation IDs. Raw review excerpts, original artifact hashes, and additional genuine model scenarios have not been recovered from the public repository and therefore are not supplied or synthesized. The project-level evaluation figures are saved separately from the one vehicle's response.

## Add more actual examples later

1. Recover the original trained artifacts securely, outside the public site. The canonical [saved-result exporter](https://github.com/gnambood/auto-market-assistant/blob/main/src/build_demo_json_from_artifacts.py) expects vehicle Parquet, the trained CatBoost model, price metrics, review documents and FAISS index in its configured local runtime. It does **not** need to run as a web service.
2. Export a small set of real model outputs and evidence, inspect their citation IDs, scope and disclosure limits, and remove sensitive or unlicensed raw text. Prefer saved deterministic evidence where optional generation is not checked.
3. Review the exported vehicle/model/year/mileage/condition grid, preserve the existing JSON schema, and add **real** entries into `data/auto-market-snapshots.v1.json`. Keep the independently sourced project-level `evaluation` section. Never invent examples or extrapolate a prediction to unexported inputs.
4. Run the portfolio validation and browser tests. They check input availability, value consistency, unsupported-question behavior, mobile sizing and zero external network requests. Publish the reviewed JSON by merging a PR into `main`.

Static output can be regenerated locally without ongoing AWS charges, but generation from the original models still requires having those saved artifacts available. GitHub Pages is a presentation layer only.


## Visual design

The portfolio uses an evidence-led editorial direction inspired by Damir Sokolovsky's [unslop](https://github.com/heydamir/unslop) design method (CC BY 4.0).

- **Product:** A technical portfolio for ML and data science hiring teams.
- **Character:** Measured, precise, approachable.
- **World:** Research field notes and model evaluation records, rather than speculative AI imagery.
- **Moments:** A real CatBoost holdout-evaluation panel on the homepage; an inspectable saved-result demonstration in the case study.
- **Signature:** Numbered case notes, quiet monospace provenance, and linked evidence.

The design removes decorative gradient washes, glow effects, pill-heavy labels and redundant card chrome. It keeps the existing project facts, research limitations, page hierarchy, source links, and browser-only functionality. The source repository linked above remains authoritative for ML implementation and evaluation. No assets or code from `unslop` are bundled; its design methodology informed the refactor.

## Changes and deployment

Propose future changes through pull requests and check the GitHub Pages publish result. The optional manual AWS deployment workflow remains separate and is **not** invoked by the static demo. AWS resources other than paused ECS tasks can still incur costs; this feature does not modify their lifecycle.
