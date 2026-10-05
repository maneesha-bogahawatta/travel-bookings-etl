"""S3 helpers: upload pipeline files to S3 (real AWS or an S3-compatible server like Moto).

Credentials are never in code: boto3 reads AWS_ACCESS_KEY_ID and
AWS_SECRET_ACCESS_KEY from the environment (loaded from .env by src.config).
"""
from datetime import date
from pathlib import Path

import boto3

from src.config import AWS_REGION, S3_BUCKET_NAME, S3_ENDPOINT_URL
from src.logger import get_logger

logger = get_logger(__name__)


def s3_enabled() -> bool:
    return bool(S3_BUCKET_NAME) and S3_BUCKET_NAME != "your-bucket-name"


def _client():
    # endpoint_url is None for real AWS, or e.g. http://localhost:9000 for a local server
    return boto3.client("s3", region_name=AWS_REGION, endpoint_url=S3_ENDPOINT_URL)


def upload_file(local_path: Path, prefix: str) -> str | None:
    """Upload a file to s3://<bucket>/<prefix>/run_date=YYYY-MM-DD/<filename>."""
    if not s3_enabled():
        logger.warning("S3_BUCKET_NAME not set; skipping upload of %s", Path(local_path).name)
        return None

    local_path = Path(local_path)
    key = f"{prefix}/run_date={date.today().isoformat()}/{local_path.name}"

    # Server-side encryption header is for real AWS only
    extra_args = None if S3_ENDPOINT_URL else {"ServerSideEncryption": "AES256"}

    _client().upload_file(str(local_path), S3_BUCKET_NAME, key, ExtraArgs=extra_args)
    uri = f"s3://{S3_BUCKET_NAME}/{key}"
    logger.info("Uploaded %s -> %s", local_path.name, uri)
    return uri


def list_objects(prefix: str) -> list[str]:
    response = _client().list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]


if __name__ == "__main__":
    for p in ("raw/", "processed/", "rejected/"):
        print(p, list_objects(p))
