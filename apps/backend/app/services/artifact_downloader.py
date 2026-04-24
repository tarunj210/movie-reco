from pathlib import Path

import boto3

from app.core.config import (
    AWS_REGION,
    CF_RECS_PATH,
    CONTENT_RECS_PATH,
    S3_ARTIFACT_BUCKET,
    S3_ARTIFACTS_ENABLED,
    S3_CF_RECS_KEY,
    S3_CONTENT_RECS_KEY,
)


def _download_s3_file(bucket: str, key: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=AWS_REGION)

    print(f"Downloading s3://{bucket}/{key} -> {destination}")
    s3.download_file(bucket, key, str(destination))
    print(f"Downloaded {destination}")


def ensure_artifacts_available() -> None:
    """
    Ensures required recommendation artifacts exist locally.

    If S3_ARTIFACTS_ENABLED=false:
        assumes files already exist locally.

    If S3_ARTIFACTS_ENABLED=true:
        downloads missing files from S3.
    """
    required_files = [
        {
            "local_path": Path(CF_RECS_PATH),
            "s3_key": S3_CF_RECS_KEY,
        },
        {
            "local_path": Path(CONTENT_RECS_PATH),
            "s3_key": S3_CONTENT_RECS_KEY,
        },
    ]

    if not S3_ARTIFACTS_ENABLED:
        missing = [str(item["local_path"]) for item in required_files if not item["local_path"].exists()]
        if missing:
            raise FileNotFoundError(
                "Missing local recommendation artifacts. "
                "Either place the files locally or set S3_ARTIFACTS_ENABLED=true. "
                f"Missing: {missing}"
            )
        return

    if not S3_ARTIFACT_BUCKET:
        raise ValueError("S3_ARTIFACT_BUCKET must be set when S3_ARTIFACTS_ENABLED=true")

    for item in required_files:
        local_path = item["local_path"]
        s3_key = item["s3_key"]

        if local_path.exists():
            print(f"Artifact already exists locally: {local_path}")
            continue

        _download_s3_file(
            bucket=S3_ARTIFACT_BUCKET,
            key=s3_key,
            destination=local_path,
        )