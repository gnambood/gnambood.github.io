"""Validate portfolio files and links without the deleted app source tree."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if fields.get("id"):
            self.ids.add(fields["id"])
        if tag == "a" and fields.get("href"):
            self.hrefs.append(fields["href"])


def validate(path):
    parser = Links()
    parser.feed(path.read_text(encoding="utf-8"))
    for href in parser.hrefs:
        url = urlsplit(href)
        if url.scheme or url.netloc:
            continue
        target = (
            ROOT / (url.path.lstrip("/") or "index.html")
            if url.path.startswith("/")
            else path.parent / url.path
            if url.path
            else path
        )
        if not target.exists():
            raise AssertionError(f"Broken local link in {path.name}: {href}")
        if url.fragment and (not url.path or target.resolve() == path.resolve()):
            if url.fragment not in parser.ids:
                raise AssertionError(f"Broken anchor in {path.name}: {href}")
    return parser


def main():
    index = ROOT / "index.html"
    case_study = ROOT / "auto-market-assistant.html"
    assert index.stat().st_size < 100_000, "Homepage has excessive embedded assets"
    assert not (ROOT / "projects/auto-market-assistant").exists(), "Duplicate app source remains"
    assert (ROOT / "PROFILE_README.md").exists(), "Prepared GitHub profile README missing"
    assert (ROOT / "assets/gayathri-coffee-portrait.png").stat().st_size > 100_000, "Restored portrait missing"
    assert (ROOT / "styles/coffee.css").exists(), "Coffee design stylesheet missing"
    assert (ROOT / "scripts/coffee-motion.js").exists(), "Accessible motion script missing"
    homepage_html = index.read_text(encoding="utf-8")
    assert "ideas into insights" in homepage_html and "gayathri-coffee-portrait.png" in homepage_html
    assert 'class="atom-orbit"' in homepage_html, "Portrait orbital decoration missing"
    assert all(f'class="orbit-dot orbit-dot-{part}"' in homepage_html for part in "abc"), "Independent orbiting dots missing"
    assert 'class="atom-core"' not in homepage_html and 'class="portrait-ring"' not in homepage_html, "Old nucleus or rotating backdrop remains"
    assert "PYTORCH" in homepage_html and "ML ENGINEERING" in homepage_html, "Relevant skills ticker missing"
    ticker = homepage_html.split('<div class="ticker"', 1)[1].split('</div></div>', 1)[0]
    assert "COFFEE" not in ticker, "Personal hobbies should not appear in the skills ticker"
    assert "76.02%" in homepage_html and "99.04%" in homepage_html, "Verified research metrics changed"
    assert all(anchor in homepage_html for anchor in ['id="research"', 'id="market"', 'id="security"']), "Long-form project stories missing"
    assert 'href="/styles/coffee.css"' in homepage_html and 'src="/scripts/coffee-motion.js"' in homepage_html
    assert homepage_html.count('class="chapter ') >= 10, "Research and engineering story chapters missing"
    assert homepage_html.count('class="pipeline-track"') == 2, "Expected two distinct ML workflows"
    assert homepage_html.count('<li><span>') == 6, "Expected three steps per workflow"
    assert 'class="path-diagram"' not in homepage_html, "Old wrapping pipeline remains"
    assert "Asking-price estimate" in homepage_html and "Cited evidence" in homepage_html



    snapshot = json.loads((ROOT / "data/auto-market-snapshots.v1.json").read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 1
    assert snapshot["market_year"] == 2021
    assert snapshot["vehicles"], "No saved model scenarios"
    for vehicle in snapshot["vehicles"].values():
        assert vehicle.get("price_grid"), "No precomputed model output"
        for price in vehicle["price_grid"].values():
            assert 0 < price["comparable_q25"] <= price["comparable_median"] <= price["comparable_q75"]
            assert price["predicted_price"] > 0 and price["comparable_count"] > 0
        for review in vehicle.get("reviews", {}).values():
            ids = [source["review_id"] for source in review.get("sources", [])]
            assert len(ids) == len(set(ids)), "Duplicate review citation IDs"
            assert all(identifier.startswith("edm_") for identifier in ids), "Unexpected citation scheme"
    js = (ROOT / "scripts/auto-market-demo.js").read_text(encoding="utf-8")
    assert "data/auto-market-snapshots.v1.json" in js
    assert "ecs.ca-central-1.on.aws" not in js
    assert "ENABLE_CLOUD_DEMO" not in js
    assert "ecs.ca-central-1.on.aws" not in case_study.read_text(encoding="utf-8")

    homepage = validate(index)
    case = validate(case_study)
    assert {"work", "about", "experience", "contact"} <= homepage.ids
    assert "demo" in case.ids and "runDemo" in case.ids
    assert any("/auto-market-assistant.html" in href for href in homepage.hrefs)
    assert any("github.com/gnambood/auto-market-assistant" in href for href in homepage.hrefs)
    print("Portfolio markup, saved output bundle, no-AWS JavaScript, and internal links OK")


if __name__ == "__main__":
    main()
