"""Extract: read the raw CSV into a DataFrame, untouched."""
from pathlib import Path

import pandas as pd

from src.config import RAW_FILE
from src.logger import get_logger

logger = get_logger(__name__)


def extract(path: Path = RAW_FILE) -> pd.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(
            f"Raw file not found: {path}. Run: python scripts/generate_data.py"
        )

    # Read everything as text. Cleaning and type conversion happen in transform.
    # Only empty cells become NaN, so values like "N/A" and "TBD" are kept
    # and handled explicitly during cleaning.
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])

    logger.info("Extracted %s rows and %s columns from %s", len(df), df.shape[1], path)
    return df


if __name__ == "__main__":
    data = extract()
    print(data.head(10).to_string())
    print(data.dtypes)