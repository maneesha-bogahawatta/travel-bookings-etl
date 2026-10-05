"""Entry point for the ETL pipeline.

Run:  python run_pipeline.py
"""
import sys
import time

from src.config import PROCESSED_FILE, RAW_FILE, REJECTED_FILE
from src.extract import extract
from src.load import load
from src.logger import get_logger
from src.s3_utils import upload_file
from src.transform import transform
from src.validate import validate

logger = get_logger("pipeline")


def main() -> int:
    start = time.perf_counter()
    logger.info("=== Pipeline started ===")

    try:
        upload_file(RAW_FILE, "raw")  # keep an untouched copy of the source in S3

        raw = extract()
        clean = transform(raw)
        valid, rejected = validate(clean)

        PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
        REJECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        valid.to_csv(PROCESSED_FILE, index=False)
        rejected.to_csv(REJECTED_FILE, index=False)
        logger.info("Saved %s clean rows to %s", len(valid), PROCESSED_FILE)
        logger.info("Saved %s rejected rows to %s", len(rejected), REJECTED_FILE)

        upload_file(PROCESSED_FILE, "processed")
        upload_file(REJECTED_FILE, "rejected")

        total = load(valid)
    except Exception:
        logger.exception("Pipeline FAILED")
        return 1

    elapsed = time.perf_counter() - start
    logger.info(
        "=== Pipeline finished in %.1fs | raw=%s clean=%s rejected=%s db_total=%s ===",
        elapsed, len(raw), len(valid), len(rejected), total,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
