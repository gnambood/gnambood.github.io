import json
import shutil
from pathlib import Path

import pandas as pd


def _hive_partition_value(value):
    if pd.isna(value):
        return "__HIVE_DEFAULT_PARTITION__"
    return str(value)


def write_partitioned_parquet(df, path, partition_cols):
    """Write deterministic Hive-style Parquet partitions.

    Each partition gets a stable part-00000.parquet filename. Re-running the
    same snapshot therefore overwrites the same local/S3 object keys instead of
    accumulating UUID-named Parquet parts.
    """
    path = Path(path)

    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)

    if not partition_cols:
        df.to_parquet(path / "part-00000.parquet", index=False)
        return path

    group_key = partition_cols[0] if len(partition_cols) == 1 else partition_cols

    grouped = df.groupby(
        group_key,
        dropna=False,
        sort=True,
        observed=True,
    )

    for values, group in grouped:
        if len(partition_cols) == 1:
            values = (values,)

        partition_path = path
        for column, value in zip(partition_cols, values):
            partition_path = (
                partition_path
                / f"{column}={_hive_partition_value(value)}"
            )

        partition_path.mkdir(parents=True, exist_ok=True)

        # Partition columns are encoded in the Hive-style directory path and
        # are therefore omitted from each Parquet payload.
        payload = group.drop(columns=partition_cols)
        payload.to_parquet(
            partition_path / "part-00000.parquet",
            index=False,
        )

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
