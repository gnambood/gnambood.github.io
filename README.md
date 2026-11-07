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

**Restored coffee-themed direction (November 6, 2026).** The original September portfolio used an espresso (#34241f), coffee (#6f4e37), rust (#b55435) and cream (#f5ebdd) palette, plus a personalized coffee-and-laptop portrait illustration. That exact original image is recovered from the earlier GitHub history and stored once as `assets/gayathri-coffee-portrait.png` (~2.17 MB), instead of embedding multiple base64 copies in the homepage.

- `styles/coffee.css`: warm personal design with a responsive portrait-led hero, project story cards, and calm typography.
- `scripts/coffee-motion.js`: staggered entrance, scroll reveals, decorative steam, floating note and restrained desktop pointer parallax. Motion is disabled through `prefers-reduced-motion`.
- `index.html`: personal narrative, photography/design/coffee interests, and current evidence-backed project descriptions.
- The Auto Market Assistant case study retains its separate, tested browser-only saved-result demo, with no AWS runtime requirement.

We kept the engineering/evidence clarity from the [unslop](https://github.com/heydamir/unslop) design review (Damir Sokolovsky, CC BY 4.0) while restoring the user's own visual identity. This is not a recreation of outdated metrics or old cloud status; verified results and links supersede the September source.

## Changes and deployment

Propose future changes through pull requests and check the GitHub Pages publish result. The optional manual AWS deployment workflow remains separate and is **not** invoked by the static demo. AWS resources other than paused ECS tasks can still incur costs; this feature does not modify their lifecycle.
