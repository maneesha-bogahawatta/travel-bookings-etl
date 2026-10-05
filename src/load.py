"""Load: write validated rows into PostgreSQL using a staging table + upsert.

Re-running the pipeline is safe: existing booking_ids are updated, new ones inserted.
"""
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.types import Date, Numeric

from src.config import DB_URL, SQL_DIR
from src.logger import get_logger

logger = get_logger(__name__)

STAGING_TABLE = "bookings_staging"
COLUMNS = [
    "booking_id", "customer_name", "customer_email", "country", "destination",
    "category", "status", "price", "rating", "booking_date",
]
STAGING_TYPES = {
    "price": Numeric(10, 2),
    "rating": Numeric(2, 1),
    "booking_date": Date(),
}

_cols = ", ".join(COLUMNS)
_updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS if c != "booking_id")
UPSERT_SQL = f"""
INSERT INTO bookings ({_cols})
SELECT {_cols} FROM {STAGING_TABLE}
ON CONFLICT (booking_id) DO UPDATE SET {_updates}, loaded_at = now()
"""


def load(df: pd.DataFrame) -> int:
    """Load valid rows into PostgreSQL. Returns the total row count in the table."""
    data = df[COLUMNS].copy()
    data["booking_date"] = data["booking_date"].dt.date

    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:  # one transaction: all or nothing
            conn.exec_driver_sql((SQL_DIR / "01_schema.sql").read_text())

            data.to_sql(
                STAGING_TABLE, conn, if_exists="replace", index=False,
                dtype=STAGING_TYPES, chunksize=1000, method="multi",
            )
            logger.info("Staged %s rows", len(data))

            conn.exec_driver_sql(UPSERT_SQL)
            conn.exec_driver_sql(f"DROP TABLE {STAGING_TABLE}")

            conn.exec_driver_sql((SQL_DIR / "02_indexes.sql").read_text())
            conn.exec_driver_sql("ANALYZE bookings")

            total = conn.exec_driver_sql("SELECT COUNT(*) FROM bookings").scalar()
    finally:
        engine.dispose()

    logger.info("Loaded %s rows; bookings table now has %s rows", len(data), total)
    return total


if __name__ == "__main__":
    from src.extract import extract
    from src.transform import transform
    from src.validate import validate

    valid_df, _ = validate(transform(extract()))
    load(valid_df)