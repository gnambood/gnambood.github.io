import json
import os
import re
from functools import lru_cache
from pathlib import Path

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts"))
ARTIFACT_BUCKET = os.getenv("ARTIFACT_BUCKET", "")
ARTIFACT_PREFIX = os.getenv("ARTIFACT_PREFIX", "").strip("/")
ENABLE_GENERATION = os.getenv("ENABLE_GENERATION", "false").lower() == "true"
RAG_MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.45"))

ARTIFACTS = {
    "vehicles_clean.parquet": "processed/vehicles_clean.parquet",
    "review_documents.parquet": "processed/review_documents.parquet",
    "price_model.cbm": "artifacts/price_model.cbm",
    "model_improvement_metrics.json": "artifacts/model_improvement_metrics.json",
    "review_index.faiss": "artifacts/review_index.faiss",
    "rag_metrics.json": "artifacts/rag_metrics.json",
}

def _s3_key(relative_key):
    return f"{ARTIFACT_PREFIX}/{relative_key}" if ARTIFACT_PREFIX else relative_key

def ensure_artifacts():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {name: ARTIFACT_DIR / name for name in ARTIFACTS}
    missing = [name for name, path in paths.items() if not path.exists()]
    if not missing:
        return paths
    if not ARTIFACT_BUCKET:
        raise RuntimeError("Missing local artifacts and ARTIFACT_BUCKET is not configured: " + ", ".join(missing))

    import boto3
    s3 = boto3.client("s3")
    for name in missing:
        try:
            s3.download_file(ARTIFACT_BUCKET, _s3_key(ARTIFACTS[name]), str(paths[name]))
        except Exception:
            if name == "rag_metrics.json":
                continue
            raise
    return paths

def normalize_model(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

class PriceEngine:
    def __init__(self):
        import pandas as pd
        from catboost import CatBoostRegressor
        self.pd = pd
        paths = ensure_artifacts()
        self.vehicles = pd.read_parquet(paths["vehicles_clean.parquet"])

        # The Part 1 export stores the cleaned modeling table before the
        # V2 model_family experiment column is added. Reconstruct that
        # deterministic feature at serving time so market-comparable lookup
        # uses the same two-token family convention as the trained model.
        self.vehicles["model_family"] = self.vehicles["model"].map(
            lambda value: " ".join(normalize_model(value).split()[:2])
        )

        with open(paths["model_improvement_metrics.json"]) as f:
            self.metrics = json.load(f)
        self.model = CatBoostRegressor()
        self.model.load_model(paths["price_model.cbm"])
        self.features = self.metrics["selected_features"]
        self.use_bias = bool(self.metrics.get("bias_correction_used", False))
        self.bias = float(self.metrics.get("bias_correction", 0.0))
        self.market_year = int(self.vehicles["posting_year"].mode().iloc[0]) if "posting_year" in self.vehicles.columns else 2021

    @staticmethod
    def _text(value):
        return "unknown" if value is None else str(value).lower().strip()

    def _row(self, payload):
        age = max(self.market_year - int(payload.year), 0)
        model_norm = normalize_model(payload.model)
        family = " ".join(model_norm.split()[:2])
        row = {
            "manufacturer": payload.manufacturer.lower().strip(),
            "model": model_norm,
            "vehicle_age": age,
            "odometer": float(payload.mileage),
            "condition": self._text(payload.condition),
            "fuel": self._text(payload.fuel),
            "title_status": self._text(payload.title_status),
            "transmission": self._text(payload.transmission),
            "drive": self._text(payload.drive),
            "type": self._text(payload.vehicle_type),
            "state": self._text(payload.state),
            "vehicle_year": int(payload.year),
            "miles_per_year": float(payload.mileage) / max(age, 1),
            "condition_missing": int(payload.condition is None),
            "fuel_missing": int(payload.fuel is None),
            "title_status_missing": int(payload.title_status is None),
            "transmission_missing": int(payload.transmission is None),
            "drive_missing": int(payload.drive is None),
            "type_missing": int(payload.vehicle_type is None),
            "model_family": family,
        }
        return self.pd.DataFrame([row])[self.features], family, age

    def predict(self, payload):
        X, family, age = self._row(payload)
        prediction = float(self.model.predict(X)[0])
        if self.use_bias:
            prediction += self.bias

        make = payload.manufacturer.lower().strip()
        same = self.vehicles["manufacturer"].eq(make) & self.vehicles["model_family"].eq(family)
        window = max(25000.0, float(payload.mileage) * 0.30)
        narrow = self.vehicles[
            same
            & self.vehicles["vehicle_age"].between(max(age - 2, 0), age + 2)
            & self.vehicles["odometer"].between(max(float(payload.mileage) - window, 0), float(payload.mileage) + window)
        ]

        if len(narrow) >= 10:
            comps, scope = narrow, "same model family + similar age/mileage"
        else:
            comps, scope = self.vehicles[same], "same model family"

        if len(comps) < 10:
            comps = self.vehicles[self.vehicles["manufacturer"].eq(make)]
            scope = "same manufacturer"

        return {
            "predicted_price": round(prediction, 0),
            "comparable_count": int(len(comps)),
            "comparable_median": round(float(comps["price"].median()), 0),
            "comparable_q25": round(float(comps["price"].quantile(0.25)), 0),
            "comparable_q75": round(float(comps["price"].quantile(0.75)), 0),
            "comparable_scope": scope,
            "market_year": self.market_year,
        }

class RagEngine:
    def __init__(self):
        import faiss
        import numpy as np
        import pandas as pd
        from sentence_transformers import SentenceTransformer
        self.faiss, self.np, self.pd = faiss, np, pd
        paths = ensure_artifacts()
        self.docs = pd.read_parquet(paths["review_documents.parquet"])
        self.index = faiss.read_index(str(paths["review_index.faiss"]))
        if self.index.ntotal != len(self.docs):
            raise RuntimeError(f"FAISS/doc mismatch: {self.index.ntotal} != {len(self.docs)}")
        self.embeddings = np.asarray(self.index.reconstruct_n(0, self.index.ntotal), dtype="float32")
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.tokenizer = None
        self.generator = None
        self.generator_name = None

    def _retrieve(self, payload):
        make = payload.manufacturer.lower().strip()
        family = " ".join(normalize_model(payload.model).split()[:2])
        make_mask = self.docs["manufacturer"].eq(make)
        family_mask = make_mask & self.docs["model_family"].eq(family)
        near_year = family_mask if payload.year is None else family_mask & self.docs["vehicle_year"].between(payload.year - 1, payload.year + 1)

        if payload.year is not None and int(near_year.sum()) >= payload.k:
            mask, scope = near_year, "same model family, year ±1"
        elif int(family_mask.sum()) >= payload.k:
            mask, scope = family_mask, "same model family"
        else:
            mask, scope = make_mask, "same manufacturer"

        candidate_idx = self.np.flatnonzero(mask.to_numpy())
        if not len(candidate_idx):
            return self.docs.iloc[0:0].copy(), scope

        query = f"{payload.year or ''} {make} {family}. {payload.question}".strip()
        q = self.embedder.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        local = self.faiss.IndexFlatIP(self.embeddings.shape[1])
        local.add(self.embeddings[candidate_idx])
        n = min(payload.k, len(candidate_idx))
        scores, ids = local.search(q, n)
        result = self.docs.iloc[candidate_idx[ids[0]]].copy()
        result["similarity"] = scores[0]
        return result.reset_index(drop=True), scope

    @staticmethod
    def _extract_citations(text, valid_ids):
        cited = set(re.findall(r"\[(edm_[a-f0-9]+)\]", text))
        return cited, bool(cited) and cited.issubset(valid_ids)

    @staticmethod
    def _scope_guard(question):
        """Reject questions that require evidence this corpus does not contain."""
        q = re.sub(r"\s+", " ", str(question).lower()).strip()

        specific_vehicle = re.search(r"\b(this|the|my)\s+(vehicle|car|truck|suv)\b", q)
        inspection_terms = re.search(
            r"\b(dent|dented|scratch|scratched|damage|damaged|accident|collision|"
            r"windshield|tire tread|flat tire|paint chip|paint damage|body damage|"
            r"rust spot|current condition|inspection)\b",
            q,
        )
        record_terms = re.search(
            r"\b(vin|carfax|accident history|service history|maintenance history|"
            r"previous owner|number of owners|odometer rollback|registration|"
            r"license plate|where is this|current location)\b",
            q,
        )

        if record_terms:
            return {
                "reason": (
                    "This question needs a vehicle-specific record such as a VIN, "
                    "history report, inspection, or listing record. The available "
                    "corpus only contains model-level owner reviews."
                ),
                "suggested_question": (
                    "What problems do owners commonly report for this model and year?"
                ),
            }

        if specific_vehicle and inspection_terms:
            return {
                "reason": (
                    "I cannot inspect this specific vehicle from owner-review data. "
                    "Dents, scratches, accident damage, and current physical condition "
                    "require photos, an inspection, or listing-specific evidence."
                ),
                "suggested_question": (
                    "Do owners report body-panel, paint, door, or corrosion problems "
                    "with this model?"
                ),
            }

        return None

    @staticmethod
    def _fallback(retrieved):
        if retrieved.empty:
            return "Not enough review evidence for this vehicle."
        ids = [f"[{review_id}]" for review_id in retrieved["review_id"].head(3)]
        cited = ", ".join(ids[:-1]) + (" and " + ids[-1] if len(ids) > 1 else ids[0])
        return (
            f"Relevant owner-review evidence was found in {cited}. "
            "Live generation is disabled, so the strongest matching excerpts are "
            "shown below instead of being synthesized into a new claim."
        )

    def _load_generator(self):
        if self.generator is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        device = "cuda" if torch.cuda.is_available() else "cpu"
        name = "Qwen/Qwen2.5-1.5B-Instruct" if device == "cuda" else "Qwen/Qwen2.5-0.5B-Instruct"
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.generator = AutoModelForCausalLM.from_pretrained(
            name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
        )
        if device == "cpu":
            self.generator.to("cpu")
        self.generator_name = name

    def _generate(self, question, retrieved):
        if not ENABLE_GENERATION:
            answer = self._fallback(retrieved)
            _, valid = self._extract_citations(answer, set(retrieved["review_id"]))
            return answer, valid, True, "retrieval-fallback"

        self._load_generator()
        evidence = []
        for _, row in retrieved.iterrows():
            excerpt = re.sub(r"\s+", " ", str(row["review_text"])).strip()[:850]
            evidence.append(
                f"SOURCE [{row['review_id']}]\nVehicle year: {row['vehicle_year']}\n"
                f"Rating: {row['rating']}\nTitle: {row['review_title']}\nReview: {excerpt}"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "Use only supplied owner-review sources. Every factual bullet must end with a source ID exactly as written. "
                    "If reviews disagree, say so. Return 2 to 4 concise bullets."
                ),
            },
            {"role": "user", "content": f"Question: {question}\n\n" + "\n\n".join(evidence)},
        ]

        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3500).to(self.generator.device)
        output = self.generator.generate(**inputs, max_new_tokens=220, do_sample=False, pad_token_id=self.tokenizer.eos_token_id)
        generated = output[0, inputs["input_ids"].shape[1]:]
        answer = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        valid_ids = set(retrieved["review_id"])
        _, valid = self._extract_citations(answer, valid_ids)
        fallback_used = False

        if not valid:
            answer = self._fallback(retrieved)
            _, valid = self._extract_citations(answer, valid_ids)
            fallback_used = True

        return answer, valid, fallback_used, self.generator_name or "qwen"

    def ask(self, payload):
        guard = self._scope_guard(payload.question)
        if guard:
            return {
                "answer": guard["reason"],
                "scope": "outside available owner-review evidence",
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "abstained-out-of-scope",
                "sources": [],
                "answerable": False,
                "reason": guard["reason"],
                "suggested_question": guard["suggested_question"],
                "max_similarity": None,
            }

        retrieved, scope = self._retrieve(payload)
        if retrieved.empty:
            reason = "No owner-review evidence was available for this vehicle selection."
            return {
                "answer": reason,
                "scope": scope,
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "no-evidence",
                "sources": [],
                "answerable": False,
                "reason": reason,
                "suggested_question": "What do owners mention about reliability and common problems?",
                "max_similarity": None,
            }

        max_similarity = float(retrieved["similarity"].max())
        if max_similarity < RAG_MIN_SIMILARITY:
            reason = (
                "The retrieved owner reviews were not similar enough to this question "
                "to support a grounded answer."
            )
            return {
                "answer": reason,
                "scope": scope,
                "citation_valid": False,
                "fallback_used": False,
                "generation_mode": "abstained-low-relevance",
                "sources": [],
                "answerable": False,
                "reason": reason,
                "suggested_question": "Try asking about reliability, maintenance, comfort, fuel economy, or common problems.",
                "max_similarity": max_similarity,
            }

        answer, valid, fallback_used, mode = self._generate(payload.question, retrieved)
        sources = []
        for _, row in retrieved.iterrows():
            sources.append({
                "review_id": str(row["review_id"]),
                "vehicle_year": int(row["vehicle_year"]) if self.pd.notna(row["vehicle_year"]) else None,
                "rating": float(row["rating"]) if self.pd.notna(row["rating"]) else None,
                "review_title": str(row["review_title"]),
                "excerpt": re.sub(r"\s+", " ", str(row["review_text"])).strip()[:260],
                "similarity": float(row["similarity"]),
            })

        return {
            "answer": answer,
            "scope": scope,
            "citation_valid": bool(valid),
            "fallback_used": bool(fallback_used),
            "generation_mode": mode,
            "sources": sources,
            "answerable": True,
            "reason": None,
            "suggested_question": None,
            "max_similarity": max_similarity,
        }


@lru_cache(maxsize=1)
def load_vehicle_catalog():
    import pandas as pd

    paths = ensure_artifacts()
    vehicles = pd.read_parquet(paths["vehicles_clean.parquet"])
    reviews = pd.read_parquet(paths["review_documents.parquet"])

    vehicles = vehicles.copy()
    vehicles["manufacturer"] = vehicles["manufacturer"].astype(str).str.lower().str.strip()
    vehicles["model_family"] = vehicles["model"].map(
        lambda value: " ".join(normalize_model(value).split()[:2])
    )

    # Fresh Part 1 exports can omit an explicit vehicle_year column.
    # Reconstruct it for catalog browsing from the persisted feature columns
    # instead of failing the whole /catalog request.
    market_year = (
        int(vehicles["posting_year"].mode().iloc[0])
        if "posting_year" in vehicles.columns and not vehicles["posting_year"].dropna().empty
        else 2021
    )
    if "vehicle_year" in vehicles.columns:
        vehicles["vehicle_year"] = pd.to_numeric(vehicles["vehicle_year"], errors="coerce")
    elif "year" in vehicles.columns:
        vehicles["vehicle_year"] = pd.to_numeric(vehicles["year"], errors="coerce")
    elif "vehicle_age" in vehicles.columns:
        vehicles["vehicle_year"] = market_year - pd.to_numeric(
            vehicles["vehicle_age"], errors="coerce"
        )
    else:
        raise RuntimeError(
            "Vehicle artifact is missing vehicle_year/year/vehicle_age; cannot build catalog"
        )

    reviews = reviews.copy()
    reviews["manufacturer"] = reviews["manufacturer"].astype(str).str.lower().str.strip()
    reviews["model_family"] = reviews["model_family"].astype(str).str.lower().str.strip()

    review_counts = (
        reviews.groupby(["manufacturer", "model_family"])
        .size()
        .rename("review_count")
    )
    listing_counts = (
        vehicles.groupby(["manufacturer", "model_family"])
        .size()
        .rename("listing_count")
    )

    supported = listing_counts.to_frame().join(review_counts, how="inner").reset_index()
    supported = supported[(supported["listing_count"] >= 20) & (supported["review_count"] >= 5)]

    if supported.empty:
        raise RuntimeError("No vehicle families have both listing and review support")

    top_makes = (
        supported.groupby("manufacturer")["listing_count"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index
        .tolist()
    )

    def clean_mode(frame, column):
        if column not in frame.columns:
            return None
        values = frame[column].dropna().astype(str).str.lower().str.strip()
        values = values[~values.isin(["", "nan", "none", "unknown"])]
        if values.empty:
            return None
        return str(values.mode().iloc[0])

    manufacturers = []
    for make in top_makes:
        make_supported = supported[supported["manufacturer"].eq(make)]
        families = (
            make_supported.sort_values(["listing_count", "review_count"], ascending=False)
            .head(6)
            .to_dict("records")
        )

        models = []
        for family_row in families:
            family = family_row["model_family"]
            segment = vehicles[
                vehicles["manufacturer"].eq(make)
                & vehicles["model_family"].eq(family)
            ].copy()
            if segment.empty:
                continue

            raw_models = segment["model"].dropna().astype(str).str.strip()
            representative = str(raw_models.mode().iloc[0]) if not raw_models.empty else family

            years_series = pd.to_numeric(segment["vehicle_year"], errors="coerce").dropna()
            years_series = years_series[(years_series >= 1990) & (years_series <= 2030)]
            years = sorted({int(x) for x in years_series.tolist()}, reverse=True)[:12]
            if not years:
                continue

            mileage_series = pd.to_numeric(segment["odometer"], errors="coerce").dropna()
            mileage_series = mileage_series[(mileage_series >= 0) & (mileage_series <= 300000)]
            mileages = []
            if not mileage_series.empty:
                for value in mileage_series.quantile([0.25, 0.5, 0.75]).tolist():
                    rounded = int(round(float(value) / 5000.0) * 5000)
                    mileages.append(max(0, min(300000, rounded)))
                mileages = sorted(set(mileages))
            if not mileages:
                mileages = [50000, 100000, 150000]

            condition_values = []
            if "condition" in segment.columns:
                condition_values = (
                    segment["condition"].dropna().astype(str).str.lower().str.strip()
                    .value_counts().head(5).index.tolist()
                )
                condition_values = [x for x in condition_values if x not in {"", "nan", "none", "unknown"}]
            if not condition_values:
                condition_values = ["good"]

            defaults = {
                "fuel": clean_mode(segment, "fuel"),
                "title_status": clean_mode(segment, "title_status"),
                "transmission": clean_mode(segment, "transmission"),
                "drive": clean_mode(segment, "drive"),
                "vehicle_type": clean_mode(segment, "type"),
                "state": clean_mode(segment, "state"),
            }

            models.append({
                "value": representative.lower(),
                "label": representative.title(),
                "family": family,
                "years": years,
                "mileages": mileages,
                "conditions": condition_values,
                "defaults": defaults,
                "listing_count": int(family_row["listing_count"]),
                "review_count": int(family_row["review_count"]),
            })

        if models:
            manufacturers.append({
                "value": make,
                "label": make.title(),
                "models": models,
            })

    return {
        "market_year": market_year,
        "manufacturer_count": len(manufacturers),
        "model_count": sum(len(item["models"]) for item in manufacturers),
        "manufacturers": manufacturers,
    }

@lru_cache(maxsize=1)
def get_price_engine():
    return PriceEngine()

@lru_cache(maxsize=1)
def get_rag_engine():
    return RagEngine()

def load_public_metrics():
    paths = ensure_artifacts()
    output = {}
    for name in ["model_improvement_metrics.json", "rag_metrics.json"]:
        path = paths.get(name)
        if path and path.exists():
            with open(path) as f:
                output[name] = json.load(f)
    return output
