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
    assert "gayathri-coffee-portrait.png" in homepage_html, "Original portrait missing"
    assert 'class="portrait-stage"' in homepage_html, "Editorial hero portrait missing"
    assert 'class="portrait-caption"' in homepage_html, "Portrait caption missing"
    assert "colourful data plots" in homepage_html, "Original plots not described"
    assert 'class="atom-orbit"' not in homepage_html and 'class="coffee-note"' not in homepage_html, "Unnecessary overlays returned"
    assert "PYTORCH" in homepage_html and "ML ENGINEERING" in homepage_html, "Relevant skills ticker missing"
    ticker = homepage_html.split('<div class="ticker"', 1)[1].split('</div></div>', 1)[0]
    assert "COFFEE" not in ticker, "Personal hobbies should not appear in the skills ticker"
    research_html = (ROOT / "driver-impairment-research.html").read_text(encoding="utf-8")
    assert "76.05%" in homepage_html and "99.04%" in homepage_html, "Project previews lost measured results"
    assert "76.02%" in research_html and "TimeSformer, Video Swin and ViViT" in research_html, "Research case study lost its methodology or evaluation"
    assert all(anchor in homepage_html for anchor in ['id="research"', 'id="market"', 'id="security"']), "Homepage project anchors missing"
    assert homepage_html.count('class="feature-card') == 3, "Homepage should feature exactly three curated projects"
    assert 'href="/driver-impairment-research.html"' in homepage_html, "Research deep dive must be discoverable"
    assert 'href="/auto-market-assistant.html"' in homepage_html, "Saved-result demo link missing"
    assert "class=\"pipeline-track\"" not in homepage_html, "Technical diagrams belong on detail pages"
    assert 'class="chapter ' not in homepage_html, "Long-form chapters should not overwhelm the homepage"
    assert research_html.count('class="chapter ') >= 5, "Long-form research chapters missing"
    assert "COFFEE" not in ticker, "Skills ticker should show technical capabilities"

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
    research = validate(ROOT / "driver-impairment-research.html")
    assert "research" in research.ids, "Research page chapter anchor missing"
    assert {"work", "about", "experience", "contact"} <= homepage.ids
    assert "demo" in case.ids and "runDemo" in case.ids
    assert any("/auto-market-assistant.html" in href for href in homepage.hrefs)
    assert any("github.com/gnambood/auto-market-assistant" in href for href in homepage.hrefs)
    print("Portfolio markup, saved output bundle, no-AWS JavaScript, and internal links OK")


if __name__ == "__main__":
    main()
