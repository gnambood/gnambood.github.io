import argparse
from pathlib import Path
import boto3

FILES = {
    "vehicles_clean.parquet": "processed/vehicles_clean.parquet",
    "review_documents.parquet": "processed/review_documents.parquet",
    "price_model.cbm": "artifacts/price_model.cbm",
    "model_improvement_metrics.json": "artifacts/model_improvement_metrics.json",
    "review_index.faiss": "artifacts/review_index.faiss",
    "rag_metrics.json": "artifacts/rag_metrics.json",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()
    root = Path(args.root)
    prefix = args.prefix.strip("/")
    s3 = boto3.client("s3")

    for filename, relative_key in FILES.items():
        source = root / filename
        if not source.exists():
            raise FileNotFoundError(source)
        key = f"{prefix}/{relative_key}" if prefix else relative_key
        print(f"{source} -> s3://{args.bucket}/{key}")
        s3.upload_file(str(source), args.bucket, key)

if __name__ == "__main__":
    main()
