import hashlib
import re
from pathlib import Path

TOP_MAKES = [
    "ford",
    "chevrolet",
    "toyota",
    "honda",
    "nissan",
    "jeep",
    "ram",
    "gmc",
    "bmw",
    "dodge",
]

OPTIONAL_VEHICLE_CATEGORIES = [
    "condition",
    "fuel",
    "title_status",
    "transmission",
    "drive",
    "type",
]

VEHICLE_TEXT_COLUMNS = [
    "manufacturer",
    "model",
    "condition",
    "fuel",
    "title_status",
    "transmission",
    "drive",
    "type",
    "region",
    "state",
]


def normalize_model(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def model_family(value):
    return " ".join(normalize_model(value).split()[:2])


def canonical_column(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def file_sha256(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_fingerprint(paths):
    digest = hashlib.sha256()
    for path in sorted(Path(p) for p in paths):
        digest.update(str(path.name).encode("utf-8"))
        digest.update(file_sha256(path).encode("utf-8"))
    return digest.hexdigest()
