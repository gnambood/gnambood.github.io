import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas
import pyarrow

root = Path("/tmp/auto-market-etl")
out = root / "output"
work = root / "work"

sources = {
    "craigslist": (
        "raw/snapshots/2026-10-08/craigslist/vehicles.csv.zip"
    ),
    "edmunds": (
        "raw/snapshots/2026-10-08/edmunds/edmunds_reviews.zip"
    ),
}

files = {
    "vehicles": out / "vehicles_rebuilt.parquet",
    "reviews": out / "reviews_rebuilt.parquet",
}

logs = {
    "vehicles": work / "vehicle_package.log",
    "reviews": work / "review_package.log",
}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

expected = {
    "vehicles": (238959, 27),
    "reviews": (70665, 9),
}

con = duckdb.connect()
artifacts = {}

for name, path in files.items():
    if not path.exists():
        raise SystemExit(f"Missing output: {path}")

    expected_rows, expected_cols = expected[name]
    rows = con.execute(
        "SELECT COUNT(*) FROM read_parquet(?)",
        [str(path)]
    ).fetchone()[0]
    schema = con.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)",
        [str(path)]
    ).fetchall()

    if rows != expected_rows or len(schema) != expected_cols:
        raise SystemExit(f"Invalid {name} schema or row count")

    log = logs[name]
    marker = (
        "FULL VEHICLE PARQUET CONTENT: PASS"
        if name == "vehicles"
        else "FULL REVIEW PARQUET: PASS"
    )

    if not log.exists() or marker not in log.read_text():
        raise SystemExit(f"Missing validation evidence: {name}")

    artifacts[name] = {
        "filename": path.name,
        "rows": rows,
        "columns": len(schema),
        "schema": [
            {"name": col[0], "type": col[1]}
            for col in schema
        ],
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "validation": "PASS",
        "validation_log": log.name,
    }

con.close()

repo = (
    "https://github.com/gnambood/"
    "gnambood.github.io"
)

try:
    git_commit = subprocess.check_output(
        ["git", "ls-remote", repo + ".git", "refs/heads/main"],
        text=True, timeout=20
    ).split()[0]
except Exception:
    git_commit = None

manifest = {
    "run_id": os.environ["RUN_ID"],
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "validated_staging",
    "source_snapshot": "2026-10-08",
    "sources": {
        key: f"s3://{os.environ['BUCKET']}/{value}"
        for key, value in sources.items()
    },
    "craigslist_csv_sha256": (
        "54c60e20aa494a73f7f9170bff1e38b4800472b767cab8f9dab7da5dcc261a5c"
    ),
    "edmunds_zip_sha256": (
        "038cc10422112e99bcf9a037e9600fbd977007483d383698d59ffc694a828884"
    ),
    "repository": repo,
    "repository_main_commit_at_packaging": git_commit,
    "transformation_code_sha256": {
        p.name: sha256(p)
        for p in (work / "pipelines").glob("*.py")
    },
    "python_version": platform.python_version(),
    "pandas_version": pandas.__version__,
    "pyarrow_version": pyarrow.__version__,
    "duckdb_version": duckdb.__version__,
    "artifacts": artifacts,
    "validation_method": (
        "Bidirectional EXCEPT ALL multiset comparison "
        "against existing production Parquet references"
    ),
    "production_modified": False,
}

path = out / "lineage_manifest.json"
path.write_text(json.dumps(manifest, indent=2) + "\n")

print("Run ID:", manifest["run_id"])
for name, item in artifacts.items():
    print(name, item["rows"], "rows", item["sha256"])

print("Repository commit:", git_commit or "unavailable")
print("Manifest:", path)
print("PACKAGE VALIDATION: PASS")
