"""Build auto-market-demo-data.json directly from saved final artifacts.

Designed for Google Colab with a GPU.

Required files in /content:
- vehicles_clean.parquet
- price_model.cbm
- model_improvement_metrics.json
- review_documents.parquet
- review_index.faiss

Optional:
- rag_metrics.json

This does NOT retrain the price model or rebuild the review corpus.
"""

from pathlib import Path
import json
import re

import faiss
import numpy as np
import pandas as pd
import torch

from catboost import CatBoostRegressor
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer


ROOT = Path("/content")
VEHICLE_FILE = ROOT / "vehicles_clean.parquet"
PRICE_MODEL_FILE = ROOT / "price_model.cbm"
PRICE_METRICS_FILE = ROOT / "model_improvement_metrics.json"
REVIEW_DOCS_FILE = ROOT / "review_documents.parquet"
REVIEW_INDEX_FILE = ROOT / "review_index.faiss"
OUT_FILE = ROOT / "auto-market-demo-data.json"

TOP_MAKES = [
    "ford", "chevrolet", "toyota", "honda", "nissan",
    "jeep", "ram", "gmc", "bmw", "dodge",
]

QUESTIONS = {
    "reliability": "What do owners mention about reliability and common problems?",
    "comfort": "What do owners say about comfort and daily driving?",
    "fuel_economy": "What do owners say about fuel economy?",
}

CONDITIONS = ["excellent", "good", "fair"]

required = [
    VEHICLE_FILE,
    PRICE_MODEL_FILE,
    PRICE_METRICS_FILE,
    REVIEW_DOCS_FILE,
    REVIEW_INDEX_FILE,
]

missing = [str(p) for p in required if not p.exists()]
assert not missing, "Missing required files:\n" + "\n".join(missing)


def normalize_model(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


vehicles = pd.read_parquet(VEHICLE_FILE)
review_docs = pd.read_parquet(REVIEW_DOCS_FILE)

with open(PRICE_METRICS_FILE) as f:
    price_metrics = json.load(f)

price_model = CatBoostRegressor()
price_model.load_model(PRICE_MODEL_FILE)

SELECTED_FEATURES = price_metrics["selected_features"]
USE_BIAS_CORRECTION = bool(price_metrics["bias_correction_used"])
BIAS_CORRECTION = float(price_metrics["bias_correction"])
MARKET_YEAR = int(vehicles["posting_year"].mode().iloc[0])

print("Vehicle rows:", f"{len(vehicles):,}")
print("Review documents:", f"{len(review_docs):,}")
print("Market year:", MARKET_YEAR)


# -----------------------------
# Restore final review vectors
# -----------------------------
global_index = faiss.read_index(str(REVIEW_INDEX_FILE))

assert global_index.ntotal == len(review_docs), (
    f"FAISS rows ({global_index.ntotal}) do not match "
    f"review documents ({len(review_docs)})."
)

# IndexFlatIP stores the original vectors, so no 70K-review re-embedding is needed.
embeddings = global_index.reconstruct_n(0, global_index.ntotal)
embeddings = np.asarray(embeddings, dtype="float32")

print("Recovered embedding matrix:", embeddings.shape)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

embedder = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device=DEVICE,
)

GENERATOR_NAME = (
    "Qwen/Qwen2.5-1.5B-Instruct"
    if DEVICE == "cuda"
    else "Qwen/Qwen2.5-0.5B-Instruct"
)

tokenizer = AutoTokenizer.from_pretrained(GENERATOR_NAME)

generator_model = AutoModelForCausalLM.from_pretrained(
    GENERATOR_NAME,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
    device_map="auto" if DEVICE == "cuda" else None,
)

if DEVICE == "cpu":
    generator_model.to("cpu")

print("Generator:", GENERATOR_NAME)
print("Device:", DEVICE)


# -----------------------------
# Price model
# -----------------------------
def build_price_row(
    make,
    model,
    vehicle_year,
    mileage,
    condition=None,
    fuel=None,
    title_status=None,
    transmission=None,
    drive=None,
    vehicle_type=None,
    state=None,
):
    make = str(make).lower().strip()
    model_norm = normalize_model(model)
    family = " ".join(model_norm.split()[:2])
    age = max(MARKET_YEAR - int(vehicle_year), 0)

    def text_or_unknown(value):
        return "unknown" if value is None else str(value).lower().strip()

    row = {
        "manufacturer": make,
        "model": model_norm,
        "vehicle_age": age,
        "odometer": float(mileage),
        "condition": text_or_unknown(condition),
        "fuel": text_or_unknown(fuel),
        "title_status": text_or_unknown(title_status),
        "transmission": text_or_unknown(transmission),
        "drive": text_or_unknown(drive),
        "type": text_or_unknown(vehicle_type),
        "state": text_or_unknown(state),
        "vehicle_year": int(vehicle_year),
        "miles_per_year": float(mileage) / max(age, 1),
        "condition_missing": int(condition is None),
        "fuel_missing": int(fuel is None),
        "title_status_missing": int(title_status is None),
        "transmission_missing": int(transmission is None),
        "drive_missing": int(drive is None),
        "type_missing": int(vehicle_type is None),
        "model_family": family,
    }

    return pd.DataFrame([row])[SELECTED_FEATURES]


def predict_price(**vehicle):
    X = build_price_row(**vehicle)
    prediction = float(price_model.predict(X)[0])

    if USE_BIAS_CORRECTION:
        prediction += BIAS_CORRECTION

    return prediction


def get_market_context(
    make,
    model,
    vehicle_year,
    mileage,
    **vehicle_details,
):
    make = str(make).lower().strip()
    family = " ".join(normalize_model(model).split()[:2])
    age = max(MARKET_YEAR - int(vehicle_year), 0)

    predicted = predict_price(
        make=make,
        model=model,
        vehicle_year=vehicle_year,
        mileage=mileage,
        **vehicle_details,
    )

    same_vehicle = (
        vehicles["manufacturer"].eq(make)
        & vehicles["model_family"].eq(family)
    )

    mileage_window = max(25000, float(mileage) * 0.30)

    narrow = vehicles[
        same_vehicle
        & vehicles["vehicle_age"].between(max(age - 2, 0), age + 2)
        & vehicles["odometer"].between(
            max(float(mileage) - mileage_window, 0),
            float(mileage) + mileage_window,
        )
    ]

    if len(narrow) >= 10:
        comps = narrow
        comp_scope = "same model family + similar age/mileage"
    else:
        comps = vehicles[same_vehicle]
        comp_scope = "same model family"

    if len(comps) < 10:
        comps = vehicles[vehicles["manufacturer"].eq(make)]
        comp_scope = "same manufacturer"

    return {
        "predicted_price": round(predicted, 0),
        "comparable_count": int(len(comps)),
        "comparable_median": round(comps["price"].median(), 0),
        "comparable_q25": round(comps["price"].quantile(0.25), 0),
        "comparable_q75": round(comps["price"].quantile(0.75), 0),
        "comparable_scope": comp_scope,
        "market_year": MARKET_YEAR,
    }


# -----------------------------
# Retrieval + grounded answer
# -----------------------------
def retrieve_reviews(question, make, model, year=None, k=5):
    make = str(make).lower().strip()
    family = " ".join(normalize_model(model).split()[:2])

    make_mask = review_docs["manufacturer"].eq(make)
    family_mask = make_mask & review_docs["model_family"].eq(family)

    if year is not None:
        near_year_mask = (
            family_mask
            & review_docs["vehicle_year"].between(
                int(year) - 1,
                int(year) + 1,
            )
        )
    else:
        near_year_mask = family_mask

    if year is not None and near_year_mask.sum() >= k:
        mask = near_year_mask
        scope = "same model family, year ±1"
    elif family_mask.sum() >= k:
        mask = family_mask
        scope = "same model family"
    else:
        mask = make_mask
        scope = "same manufacturer"

    candidate_idx = np.flatnonzero(mask.to_numpy())

    if len(candidate_idx) == 0:
        return pd.DataFrame(), "no review coverage"

    query_text = f"{year or ''} {make} {family}. {question}".strip()

    query_vector = embedder.encode(
        [query_text],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    local_index = faiss.IndexFlatIP(embeddings.shape[1])
    local_index.add(embeddings[candidate_idx])

    top_k = min(k, len(candidate_idx))
    scores, local_ids = local_index.search(query_vector, top_k)

    result_idx = candidate_idx[local_ids[0]]

    result = review_docs.iloc[result_idx].copy()
    result["similarity"] = scores[0]

    return result.reset_index(drop=True), scope


def extract_valid_citations(text, valid_ids):
    cited = set(re.findall(r"\[(edm_[a-f0-9]+)\]", text))
    return cited, cited.issubset(valid_ids) and len(cited) > 0


def fallback_grounded_answer(question, retrieved, max_sources=3):
    if retrieved.empty:
        return "Not enough review evidence for this vehicle."

    lines = [
        "The generator did not produce a reliably cited answer, "
        "so here are the strongest retrieved owner-review excerpts:"
    ]

    for _, row in retrieved.head(max_sources).iterrows():
        excerpt = re.sub(
            r"\s+",
            " ",
            str(row["review_text"]),
        ).strip()[:280]

        lines.append(f"- [{row['review_id']}] {excerpt}")

    return "\n".join(lines)


def summarize_owner_reviews(question, retrieved):
    if retrieved.empty:
        return {
            "answer": "Not enough review evidence for this vehicle.",
            "citation_valid": False,
            "fallback_used": False,
        }

    evidence = []

    for _, row in retrieved.iterrows():
        excerpt = re.sub(
            r"\s+",
            " ",
            str(row["review_text"]),
        ).strip()[:850]

        evidence.append(
            f"SOURCE [{row['review_id']}]\n"
            f"Vehicle year: {row['vehicle_year']}\n"
            f"Rating: {row['rating']}\n"
            f"Title: {row['review_title']}\n"
            f"Review: {excerpt}"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You summarize owner car reviews using only the supplied sources. "
                "Every factual bullet must end with at least one source ID exactly "
                "as written, for example [edm_123abc]. "
                "Do not use outside knowledge. "
                "Do not invent common problems not explicitly present in the evidence. "
                "If reviews disagree, say that they disagree. "
                "Return 2 to 4 short bullets. "
                "If the evidence does not answer the question, say "
                "'Not enough review evidence.'"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                "Retrieved owner-review evidence:\n\n"
                + "\n\n".join(evidence)
            ),
        },
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=3500,
    ).to(generator_model.device)

    with torch.no_grad():
        output = generator_model.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output[0, inputs["input_ids"].shape[1]:]

    answer = tokenizer.decode(
        generated,
        skip_special_tokens=True,
    ).strip()

    valid_ids = set(retrieved["review_id"])

    _, citation_valid = extract_valid_citations(
        answer,
        valid_ids,
    )

    fallback_used = False

    if not citation_valid:
        answer = fallback_grounded_answer(
            question,
            retrieved,
        )
        fallback_used = True

        _, citation_valid = extract_valid_citations(
            answer,
            valid_ids,
        )

    return {
        "answer": answer,
        "citation_valid": bool(citation_valid),
        "fallback_used": fallback_used,
    }


# -----------------------------
# Demo preset selection/export
# -----------------------------
def mode_or_none(series):
    s = series.dropna().astype(str)
    return None if s.empty else s.mode().iloc[0]


def display_model(model):
    tokens = str(model).split()
    if len(tokens) == 2 and len(tokens[0]) <= 2 and tokens[1].isdigit():
        return f"{tokens[0].upper()}-{tokens[1]}"
    return " ".join(
        t.upper()
        if len(t) <= 3 and any(ch.isalpha() for ch in t)
        else t.title()
        for t in tokens
    )


price_cov = (
    vehicles.groupby(["manufacturer", "model_family"], observed=True)
    .size().rename("price_rows")
)

review_cov = (
    review_docs.groupby(["manufacturer", "model_family"], observed=True)
    .size().rename("review_rows")
)

coverage = pd.concat(
    [price_cov, review_cov],
    axis=1,
).fillna(0).reset_index()

coverage["coverage_score"] = np.sqrt(
    coverage["price_rows"] * coverage["review_rows"]
)

selected = {}

for make in TOP_MAKES:
    candidates = coverage[
        coverage["manufacturer"].eq(make)
        & coverage["price_rows"].ge(50)
        & coverage["review_rows"].ge(25)
    ].sort_values("coverage_score", ascending=False)

    if candidates.empty:
        candidates = coverage[
            coverage["manufacturer"].eq(make)
            & coverage["price_rows"].gt(0)
            & coverage["review_rows"].gt(0)
        ].sort_values("coverage_score", ascending=False)

    if candidates.empty:
        print("Skipping:", make)
        continue

    family = candidates.iloc[0]["model_family"]

    price_group = vehicles[
        vehicles["manufacturer"].eq(make)
        & vehicles["model_family"].eq(family)
    ].copy()

    review_group = review_docs[
        review_docs["manufacturer"].eq(make)
        & review_docs["model_family"].eq(family)
    ].copy()

    exact_model = (
        price_group["model"]
        .dropna().astype(str)
        .value_counts().index[0]
    )

    price_year = (
        price_group.groupby("vehicle_year", observed=True)
        .size().rename("price_rows")
    )

    review_year = (
        review_group.dropna(subset=["vehicle_year"])
        .groupby("vehicle_year", observed=True)
        .size().rename("review_rows")
    )

    year_cov = pd.concat(
        [price_year, review_year],
        axis=1,
    ).fillna(0).reset_index()

    year_cov = year_cov[
        year_cov["price_rows"].gt(0)
        & year_cov["review_rows"].gt(0)
        & year_cov["vehicle_year"].between(1990, MARKET_YEAR)
    ].copy()

    year_cov["score"] = np.sqrt(
        year_cov["price_rows"] * year_cov["review_rows"]
    )

    years = (
        year_cov.sort_values("score", ascending=False)
        .head(3)["vehicle_year"].astype(int).tolist()
    )

    if not years:
        years = [
            int(
                price_group["vehicle_year"]
                .dropna()
                .mode()
                .iloc[0]
            )
        ]

    years = sorted(set(years), reverse=True)

    odom = pd.to_numeric(
        price_group["odometer"],
        errors="coerce",
    ).dropna()

    if odom.empty:
        mileages = [50000, 100000, 150000]
    else:
        mileages = sorted(set(
            int(np.clip(
                round(float(odom.quantile(q)) / 5000) * 5000,
                5000,
                250000,
            ))
            for q in [0.25, 0.50, 0.75]
        ))

    defaults = {
        "fuel": mode_or_none(price_group["fuel"]),
        "title_status": mode_or_none(price_group["title_status"]),
        "transmission": mode_or_none(price_group["transmission"]),
        "drive": mode_or_none(price_group["drive"]),
        "vehicle_type": mode_or_none(price_group["type"]),
        "state": mode_or_none(price_group["state"]),
    }

    key = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{make}-{family}".lower(),
    ).strip("-")

    selected[key] = {
        "display_make": (
            make.title()
            if make != "bmw"
            else "BMW"
        ),
        "display_model": display_model(exact_model),
        "make": make,
        "model": exact_model,
        "model_family": family,
        "years": years,
        "mileages": mileages,
        "conditions": CONDITIONS,
        "defaults": defaults,
        "price_grid": {},
        "reviews": {},
        "coverage": {
            "price_rows": int(len(price_group)),
            "review_rows": int(len(review_group)),
        },
    }


print("\nSelected vehicles:")
for vehicle in selected.values():
    print(
        vehicle["display_make"],
        vehicle["display_model"],
        vehicle["years"],
        vehicle["mileages"],
    )


for vehicle in selected.values():
    d = vehicle["defaults"]

    for year in vehicle["years"]:
        for mileage in vehicle["mileages"]:
            for condition in vehicle["conditions"]:
                context = get_market_context(
                    make=vehicle["make"],
                    model=vehicle["model"],
                    vehicle_year=year,
                    mileage=mileage,
                    condition=condition,
                    fuel=d["fuel"],
                    title_status=d["title_status"],
                    transmission=d["transmission"],
                    drive=d["drive"],
                    vehicle_type=d["vehicle_type"],
                    state=d["state"],
                )

                key = (
                    f"{year}|{mileage}|{condition}"
                )

                selected_price = {
                    k: (
                        v.item()
                        if isinstance(v, np.generic)
                        else v
                    )
                    for k, v in context.items()
                }

                vehicle["price_grid"][key] = selected_price


for vehicle in selected.values():
    for year in vehicle["years"]:
        for qkey, question in QUESTIONS.items():

            retrieved, scope = retrieve_reviews(
                question=question,
                make=vehicle["make"],
                model=vehicle["model"],
                year=year,
                k=5,
            )

            result = summarize_owner_reviews(
                question,
                retrieved,
            )

            sources = []

            for _, row in retrieved.head(5).iterrows():
                sources.append({
                    "review_id": str(row["review_id"]),
                    "vehicle_year": (
                        int(row["vehicle_year"])
                        if pd.notna(row["vehicle_year"])
                        else None
                    ),
                    "rating": (
                        float(row["rating"])
                        if pd.notna(row["rating"])
                        else None
                    ),
                    "review_title": str(row["review_title"]),
                    "excerpt": re.sub(
                        r"\s+",
                        " ",
                        str(row["review_text"]),
                    ).strip()[:260],
                })

            vehicle["reviews"][
                f"{year}|{qkey}"
            ] = {
                "heading": {
                    "reliability": (
                        "Reliability & common problems"
                    ),
                    "comfort": (
                        "Comfort & daily driving"
                    ),
                    "fuel_economy": (
                        "Fuel-economy owner evidence"
                    ),
                }[qkey],
                "question": question,
                "answer": result["answer"],
                "citation_valid": bool(
                    result["citation_valid"]
                ),
                "fallback_used": bool(
                    result["fallback_used"]
                ),
                "scope": scope,
                "sources": sources,
            }


demo_data = {
    "schema_version": 1,
    "generated_at_utc": (
        pd.Timestamp.utcnow().isoformat()
    ),
    "market_year": MARKET_YEAR,
    "source_note": (
        "Precomputed from the trained CatBoost "
        "price model and Edmunds owner-review "
        "retrieval pipeline."
    ),
    "questions": QUESTIONS,
    "vehicles": selected,
}


with open(OUT_FILE, "w") as f:
    json.dump(
        demo_data,
        f,
        indent=2,
    )


print("\nCreated:", OUT_FILE)
print("Vehicle presets:", len(selected))
print(
    "Size:",
    f"{OUT_FILE.stat().st_size / 1024:.1f} KB",
)
