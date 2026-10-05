"""Central configuration: reads .env and defines project paths."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Paths
RAW_FILE = BASE_DIR / "data" / "raw" / "travel_bookings_raw.csv"
PROCESSED_FILE = BASE_DIR / "data" / "processed" / "travel_bookings_clean.csv"
REJECTED_FILE = BASE_DIR / "data" / "rejected" / "travel_bookings_rejected.csv"
LOG_DIR = BASE_DIR / "logs"
SQL_DIR = BASE_DIR / "sql"

# PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "travel_bookings")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") or None  # empty string -> None

DB_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

# AWS (credentials are read by boto3 from the environment automatically)
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None
