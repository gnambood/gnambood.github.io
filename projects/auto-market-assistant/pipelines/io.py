import json
from pathlib import Path


def write_partitioned_parquet(df, path, partition_cols):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, partition_cols=partition_cols)
    return path


def write_json(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def publish_directory_to_s3(local_root, bucket, prefix=""):
    import boto3

    local_root = Path(local_root)
    s3 = boto3.client("s3")
    uploaded = []

    for path in sorted(local_root.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(local_root).as_posix()
        key = "/".join(
            part.strip("/")
            for part in [prefix, relative]
            if part.strip("/")
        )

        s3.upload_file(str(path), bucket, key)
        uploaded.append(
            {
                "local_path": str(path),
                "s3_uri": f"s3://{bucket}/{key}",
            }
        )

    return uploaded
