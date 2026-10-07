import csv
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .common import canonical_column, normalize_model


def _clean_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def make_from_filename(path, supported_makes):
    stem = _clean_name(Path(path).stem)
    for make in supported_makes:
        if _clean_name(make) in stem:
            return make
    return None


def load_review_directory(review_dir, supported_makes):
    """Load supported Edmunds CSVs with the notebook's fallback parser."""
    csv.field_size_limit(sys.maxsize)
    paths = sorted(Path(review_dir).rglob("*.csv"))
    selected = [
        (path, make_from_filename(path, supported_makes)) for path in paths
    ]
    selected = [(path, make) for path, make in selected if make is not None]

    frames = []
    fallback_files = []

    for path, make in selected:
        try:
            part = pd.read_csv(path, low_memory=False)
        except pd.errors.ParserError:
            fallback_files.append(path.name)
            part = pd.read_csv(
                path,
                engine="python",
                on_bad_lines="skip",
                encoding_errors="replace",
            )

        part["manufacturer"] = make
        part["source_file"] = path.name
        frames.append(part)

    if not frames:
        raise ValueError("No supported Edmunds review CSV files were found.")

    return (
        pd.concat(frames, ignore_index=True),
        {
            "selected_files": [p.name for p, _ in selected],
            "fallback_files": fallback_files,
        },
    )


def _pick_column(df, candidates, required=True):
    lookup = {canonical_column(col): col for col in df.columns}
    for candidate in candidates:
        key = canonical_column(candidate)
        if key in lookup:
            return lookup[key]
    if required:
        raise ValueError(
            "Could not find any of the required columns: " + ", ".join(candidates)
        )
    return None


def parse_vehicle_title(title, manufacturer):
    title = normalize_model(title)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title)
    year = int(year_match.group(0)) if year_match else np.nan

    model = title
    if year_match:
        model = re.sub(rf"\b{year_match.group(0)}\b", " ", model)

    normalized_make = normalize_model(manufacturer)
    model = re.sub(rf"\b{re.escape(normalized_make)}\b", " ", model)
    model = re.sub(r"\s+", " ", model).strip()
    family = " ".join(model.split()[:2])

    return year, model, family


def clean_reviews(reviews_raw):
    """Normalize, deduplicate and parse the Edmunds review corpus."""
    vehicle_title_col = _pick_column(
        reviews_raw,
        ["Vehicle_Title", "vehicle title", "car_model", "vehicle"],
    )
    review_text_col = _pick_column(
        reviews_raw,
        ["Review", "review_text", "review body", "comments"],
    )
    review_title_col = _pick_column(
        reviews_raw,
        ["Review_Title", "review title", "title"],
        required=False,
    )
    rating_col = _pick_column(
        reviews_raw,
        ["Rating", "rating", "stars"],
        required=False,
    )
    date_col = _pick_column(
        reviews_raw,
        ["Review_Date", "review date", "date"],
        required=False,
    )

    if "manufacturer" not in reviews_raw or "source_file" not in reviews_raw:
        raise ValueError(
            "Review input must include manufacturer and source_file metadata."
        )

    reviews = pd.DataFrame(
        {
            "manufacturer": (
                reviews_raw["manufacturer"]
                .astype(str)
                .str.lower()
                .str.strip()
            ),
            "vehicle_title": reviews_raw[vehicle_title_col].astype("string"),
            "review_text": reviews_raw[review_text_col].astype("string"),
            "source_file": reviews_raw["source_file"],
        }
    )

    if review_title_col:
        reviews["review_title"] = reviews_raw[review_title_col].astype("string")
    else:
        reviews["review_title"] = ""

    if rating_col:
        reviews["rating"] = pd.to_numeric(
            reviews_raw[rating_col], errors="coerce"
        )
    else:
        reviews["rating"] = np.nan

    if date_col:
        reviews["review_date"] = pd.to_datetime(
            reviews_raw[date_col], errors="coerce", utc=True
        ).dt.tz_localize(None)
    else:
        reviews["review_date"] = pd.NaT

    reviews = reviews.dropna(subset=["vehicle_title", "review_text"]).copy()
    reviews["review_text"] = (
        reviews["review_text"]
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    reviews["review_title"] = (
        reviews["review_title"]
        .fillna("")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    reviews = reviews[reviews["review_text"].str.len() >= 40].copy()
    reviews = reviews.drop_duplicates(
        subset=["manufacturer", "vehicle_title", "review_text"]
    ).reset_index(drop=True)

    parsed = reviews.apply(
        lambda row: parse_vehicle_title(
            row["vehicle_title"], row["manufacturer"]
        ),
        axis=1,
    )
    reviews[["vehicle_year", "model", "model_family"]] = pd.DataFrame(
        parsed.tolist(), index=reviews.index
    )

    reviews["vehicle_year"] = pd.to_numeric(
        reviews["vehicle_year"], errors="coerce"
    ).astype("Int64")
    reviews = reviews[reviews["model_family"].str.len() > 0].copy()

    return reviews.reset_index(drop=True)


def match_reviews_to_vehicle_scope(reviews, vehicles):
    vehicle_pairs = set(
        zip(
            vehicles["manufacturer"].astype(str),
            vehicles["model_family"].astype(str),
        )
    )

    with_match = reviews.copy()
    with_match["matched_price_scope"] = [
        (make, family) in vehicle_pairs
        for make, family in zip(
            reviews["manufacturer"], reviews["model_family"]
        )
    ]
    matched_reviews = with_match[with_match["matched_price_scope"]].copy()

    return with_match.reset_index(drop=True), matched_reviews.reset_index(drop=True)
