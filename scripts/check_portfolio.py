"""Validate portfolio files and links without the deleted app source tree."""
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

    homepage = validate(index)
    case = validate(case_study)
    assert {"work", "about", "experience", "contact"} <= homepage.ids
    assert "demo" in case.ids and "runDemo" in case.ids
    assert any("/auto-market-assistant.html" in href for href in homepage.hrefs)
    assert any("github.com/gnambood/auto-market-assistant" in href for href in homepage.hrefs)
    print("Portfolio markup, anchors, internal links and source-of-truth boundaries OK")


if __name__ == "__main__":
    main()
