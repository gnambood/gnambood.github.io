# Gayathri Namboodiri — portfolio website

This is the **GitHub Pages presentation layer**, not an ML application repository.

- `index.html`: lightweight professional homepage.
- `auto-market-assistant.html`: interactive case study with a **verified offline example** while AWS inference compute is paused. It does not present static results as live model predictions.
- `scripts/check_portfolio.py` and `tests/auto-market-offline.mjs`: website and browser checks.
- `.github/workflows/auto-market-deploy.yml`: a **manual** AWS deployment bridge. It checks out the actual canonical application repository; it does not contain application source.

**Canonical engineering project:** https://github.com/gnambood/auto-market-assistant

That repository owns the API, models, data pipeline, Vehicle Market Intelligence implementation and viewer, evaluation artifacts, tests, and technical documentation. Do not reintroduce `projects/auto-market-assistant/` or duplicate technical implementation here.

**Research:** Driver impairment code is private. The portfolio summarizes the research without implying that unpublished data or private code can be accessed publicly.

**GitHub profile README:** `PROFILE_README.md` is a prepared draft. GitHub displays a profile README only after the file is copied as `README.md` to a *public* repository named exactly `gnambood`.

## Changes and deployment

Review proposed site changes through pull requests. The canonical application may need to merge first for new documentation links and tests to resolve. The previous deployment depended on duplicated source; the manual deployment bridge avoids that dependency, but automated cross-repository CD remains a separate infrastructure task. Do not assume AWS resources are zero-cost while ECS tasks are paused.
