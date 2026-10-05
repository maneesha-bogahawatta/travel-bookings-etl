"""Validate: enforce business rules, split rows into valid and rejected."""
import pandas as pd

from src.logger import get_logger
from src.transform import VALID_CATEGORIES, VALID_COUNTRIES, VALID_STATUSES

logger = get_logger(__name__)

BOOKING_ID_PATTERN = r"^BK\d{6}$"


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    today = pd.Timestamp.today().normalize()

    # rule name -> boolean mask of rows that FAIL the rule
    checks = {
        "booking_id missing or invalid": ~df["booking_id"].str.match(BOOKING_ID_PATTERN, na=False),
        "country missing or unknown": ~df["country"].isin(VALID_COUNTRIES),
        "category missing or unknown": ~df["category"].isin(VALID_CATEGORIES),
        "status missing or unknown": ~df["status"].isin(VALID_STATUSES),
        "price missing or not positive": df["price"].isna() | (df["price"] <= 0),
        "rating outside 1-5": df["rating"].notna() & ~df["rating"].between(1, 5),
        "booking_date missing or invalid": df["booking_date"].isna(),
        "booking_date in the future": df["booking_date"] > today,
    }

    reasons = pd.Series("", index=df.index)
    for message, failed in checks.items():
        logger.info("Rule failed: %-34s %s rows", message, int(failed.sum()))
        reasons = reasons.where(~failed, reasons + message + "; ")

    is_rejected = reasons != ""
    valid = df[~is_rejected].reset_index(drop=True)
    rejected = df[is_rejected].copy()
    rejected["reject_reason"] = reasons[is_rejected].str.rstrip("; ")

    logger.info("Validation: %s valid, %s rejected", len(valid), len(rejected))
    return valid, rejected


if __name__ == "__main__":
    from src.extract import extract
    from src.transform import transform

    valid_df, rejected_df = validate(transform(extract()))
    print(valid_df.dtypes)
    print(valid_df.head(8).to_string())
    print(rejected_df[["booking_id", "price", "booking_date", "reject_reason"]].head(10).to_string())