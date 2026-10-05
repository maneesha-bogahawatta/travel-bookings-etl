# Travel Bookings ETL Pipeline

A small, production-minded ETL pipeline for the Luxury Explorers Associate Data Engineer assessment. It generates a deliberately dirty travel-bookings dataset, then **extracts, cleans, validates and loads** it into PostgreSQL, with raw and processed files stored in S3.

```
python run_pipeline.py
```

## Architecture

```
generate_data.py ──► data/raw/*.csv ──► (upload to S3: raw/)
                          │
                      extract.py        read everything as text
                          │
                     transform.py       clean, standardize, deduplicate
                          │
                      validate.py       business rules, split valid / rejected
                       │       │
        data/rejected/*.csv    data/processed/*.csv ──► (upload to S3: processed/, rejected/)
        (with reject_reason)           │
                                   load.py          staging table + upsert, one transaction
                                       │
                                  PostgreSQL        schema, constraints, indexes
```

| Module | Responsibility |
|---|---|
| `scripts/generate_data.py` | Creates ~12,480 raw rows with planted data-quality problems |
| `src/config.py` | Reads `.env`, defines paths and DB/S3 settings |
| `src/logger.py` | Logging to console and `logs/pipeline.log` |
| `src/extract.py` | Reads the raw CSV as text, untouched |
| `src/transform.py` | Cleans and standardizes, removes duplicates |
| `src/validate.py` | Enforces business rules, logs rejected rows with reasons |
| `src/load.py` | Loads into PostgreSQL (staging + upsert, transactional) |
| `src/s3_utils.py` | Uploads files to S3 under date-partitioned keys |
| `run_pipeline.py` | Single entry point that orchestrates all stages |

## Project structure

```
travel-bookings-etl/
├── data/{raw,processed,rejected}/   # CSVs (git-ignored)
├── logs/                            # pipeline.log (git-ignored)
├── sql/
│   ├── 01_schema.sql                # table, primary key, constraints
│   ├── 02_indexes.sql               # indexes
│   ├── 03_analytical_queries.sql    # analytical queries
│   └── 04_index_demo.sql            # EXPLAIN ANALYZE before/after demo
├── src/                             # pipeline modules
├── scripts/generate_data.py         # dirty dataset generator
├── docs/iam_policy.json             # least-privilege S3 policy
├── run_pipeline.py
├── requirements.txt
├── requirements-local-s3.txt        # optional: local S3 server for testing
├── .env.example
└── README.md
```

## Setup

Requirements: Python 3.10+, PostgreSQL 14+.

```bash
git clone https://github.com/maneesha-bogahawatta/travel-bookings-etl.git
cd travel-bookings-etl
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

createdb travel_bookings
cp .env.example .env        # then edit .env with your values
```

### Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL connection (password may be empty for local trust auth) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | AWS credentials, read by boto3 from the environment |
| `S3_BUCKET_NAME` | Target bucket. If unset, S3 uploads are skipped with a warning |
| `S3_ENDPOINT_URL` | Optional. Set only for an S3-compatible server (see below). Leave empty for real AWS |

No secrets are hardcoded. `.env` is git-ignored, and `.env.example` documents every variable.

## Run it

```bash
python scripts/generate_data.py     # 1. create the raw dataset
python run_pipeline.py              # 2. run the ETL pipeline
python -m src.s3_utils              # 3. list files stored in S3
psql -d travel_bookings -f sql/03_analytical_queries.sql   # 4. analytical queries
psql -d travel_bookings -f sql/04_index_demo.sql           # 5. index performance demo
```

Example run (12,480 raw rows):

```
Transform: 12480 rows in, 12000 rows out     (480 duplicates removed)
Validation: 10997 valid, 1003 rejected
Loaded 10997 rows; bookings table now has 10997 rows
Pipeline finished in ~1s
```

## The dataset

12,480 rows, 10 columns of mixed types: `booking_id`, `customer_name`, `customer_email`, `country`, `destination`, `category`, `status` (strings), `price`, `rating` (numeric), `booking_date` (date).

Planted problems: missing values in most columns, exact and near-duplicate rows, five different date formats plus invalid and future dates, inconsistent casing and whitespace, country aliases (`USA`, `UAE`), prices stored as text (`$1,234.50`, `USD 800.0`), negative prices, out-of-range and text ratings (`N/A`), and malformed emails.

## Cleaning and validation rules

| Problem | Decision | Reason |
|---|---|---|
| Casing and whitespace | Trim, collapse spaces, title-case only fully upper/lower values | Keeps `DDS`, `McDonald` intact |
| Country aliases | `USA`/`US`/`UAE` mapped to full names | Consistent grouping |
| Missing `country` | Inferred from destination (Phuket → Thailand) | Recoverable without guessing |
| Missing `customer_name` | Filled with `Unknown` | Not essential for analytics |
| Missing or invalid `customer_email` | Set to NULL, keep booking | Not essential |
| Missing `rating` | Kept as NULL | Imputing would distort average-rating analytics |
| Price text | Strip `$`, `USD`, commas, then convert to number | Recoverable |
| Dates | Five formats parsed into one type; ambiguous dates are **day-first (DD/MM/YYYY)** | Documented assumption |
| Duplicates | Drop exact duplicates after standardizing, then keep the first row per `booking_id` | Near-duplicates become exact once standardized |
| Missing or invalid `booking_id`, `price`, `booking_date` | **Rejected** | Essential fields |
| Price ≤ 0, rating outside 1-5, future date | **Rejected** | Violates business rules |

Rejected rows are written to `data/rejected/travel_bookings_rejected.csv` with a `reject_reason` column (a row can fail several rules), and per-rule counts are logged.

## Database design

One `bookings` table. This is an analytics dataset with no update-heavy relationships, so splitting it into many tables would add joins without adding value.

- **Primary key:** `booking_id` (also gives a unique index)
- **Constraints:** `NOT NULL` on essential columns, `CHECK` constraints for ID format, `price > 0`, rating 1-5, and allowed status and category values. The database enforces the same rules as the pipeline, so bad data is blocked even if the pipeline is bypassed.
- **Types:** `NUMERIC(10,2)` for money (exact, unlike `FLOAT`), `DATE` for dates, `TIMESTAMPTZ` for `loaded_at`.
- **Idempotent load:** rows go into a staging table, then `INSERT ... ON CONFLICT (booking_id) DO UPDATE` inside **one transaction**. Re-running never creates duplicates, and a failure never leaves a half-loaded table.

## Indexes and performance

Each index exists for a specific query. Not every column is indexed, because every index slows writes and uses disk.

| Index | Serves |
|---|---|
| `idx_bookings_booking_date` | Date-range filters and monthly trend |
| `idx_bookings_status_category_price` on `(status, category) INCLUDE (price)` | Revenue by category for confirmed bookings (can use an index-only scan) |
| `idx_bookings_country_rating` on `(country) INCLUDE (rating) WHERE rating IS NOT NULL` | Average rating by country (partial index: smaller) |

`ANALYZE` runs after each load so the planner has fresh statistics.

### Analytical queries (`sql/03_analytical_queries.sql`)

1. Top 10 category/destination combinations by revenue
2. Revenue by category
3. Monthly revenue with month-over-month growth (window function `LAG`)
4. Average rating and rated-booking count by country

### Index demonstration (`sql/04_index_demo.sql`)

The real table has only ~11k rows, where a sequential scan takes milliseconds, so the script builds a temporary 1.1M-row copy and runs the same date-range query before and after adding an index:

| | Plan | Execution time |
|---|---|---|
| Before | Seq Scan (1,076,500 rows removed by filter) | **48.9 ms** |
| After | Bitmap Index Scan + Bitmap Heap Scan | **13.1 ms** (about 3.7x faster) |

The page reads dropped by only ~15%, because the benchmark rows are in random order, so a month's rows are scattered across most of the table's pages. With date-ordered data (typical for time-based inserts) the same index reads far fewer pages. That is the case for partitioning or a BRIN index at larger scale (see below).

## S3 integration

- Raw file is uploaded **before** processing, and the processed and rejected files **after** validation.
- Keys are date-partitioned: `raw/run_date=YYYY-MM-DD/file.csv`. Re-running on the same day overwrites rather than duplicating, and the layout can grow into a data lake.
- Credentials come from environment variables (`.env`), never from code.
- Server-side encryption (`AES256`) is requested when using real AWS.
- If `S3_BUCKET_NAME` is not set, uploads are skipped with a warning. If S3 is configured and an upload fails, the pipeline fails loudly.

### Least-privilege IAM (`docs/iam_policy.json`)

The pipeline user can only `PutObject`/`GetObject` under `raw/`, `processed/` and `rejected/` in one bucket, and list only those prefixes. There is no delete permission, no `s3:*`, and no access to other buckets. Replace `YOUR-BUCKET-NAME` and attach the policy to a dedicated IAM user with no console access.

### Note on how S3 was tested

AWS account signup requires a card verification that I could not complete in time for this submission. To still demonstrate the integration, I ran the pipeline against **Moto**, a local S3-compatible server, using standard `boto3` code.

```bash
pip install -r requirements-local-s3.txt
moto_server -p 9000        # keep running in a separate terminal
# create the bucket once (Moto is in-memory):
python -c "import boto3; boto3.client('s3', endpoint_url='http://localhost:9000', region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test').create_bucket(Bucket='travel-etl-bucket')"
```

with these `.env` values: `S3_ENDPOINT_URL=http://localhost:9000`, dummy keys, and `S3_BUCKET_NAME=travel-etl-bucket`.

**To use real AWS, nothing in the code changes:** leave `S3_ENDPOINT_URL` empty, add real credentials and a bucket name, and apply the IAM policy. Moto does not enforce IAM policies, so least privilege is documented in the policy file but could not be demonstrated locally.

## Scalability: from 12k to 1M+ records

**Extract and transform.** Today the pipeline reads the whole file into memory, which is fine at this size. For 1M+ rows I would read the CSV in chunks (`pd.read_csv(chunksize=...)`) and process chunk by chunk, with Parquet instead of CSV for the processed layer (smaller, typed, columnar). Beyond a few tens of millions of rows, I would move the transform to Spark, AWS Glue or a SQL-based tool (dbt), keeping the same module boundaries. Cross-chunk duplicate removal would move into the database via the primary key and upsert.

**Load.** Replace `to_sql` with PostgreSQL `COPY` into the staging table, which is typically an order of magnitude faster. Keep the staging table + upsert pattern, and commit per batch (for example 100k rows) with an idempotent key so a failed run can resume.

**Partitioning and indexing.** Partition `bookings` by month on `booking_date` (declarative range partitioning). Queries on date ranges prune partitions, old partitions can be archived or dropped cheaply, and indexes stay small. Consider a **BRIN index** on `booking_date` for time-ordered data (tiny, cheap to maintain). Keep the composite and partial indexes only if the query patterns still justify them. For heavier reporting, add materialized views or a read replica.

**Scheduling.** For a single daily job, **cron** is enough:

```
0 2 * * *  cd /path/to/travel-bookings-etl && venv/bin/python run_pipeline.py >> logs/cron.log 2>&1
```

For dependencies, retries and visibility, use **Airflow**: one DAG with tasks `extract → transform → validate → upload_s3 → load → notify`, each retried with backoff, run daily, with SLAs and alerts. The module boundaries here map directly onto those tasks.

**Failure handling.**
- **Atomic loads:** the load is one transaction, so a failure leaves the table unchanged.
- **Idempotency:** upserts and date-partitioned S3 keys mean re-running is always safe.
- **Bad data does not stop the run:** invalid rows are rejected with reasons rather than crashing the pipeline, and counts are logged. At scale, add a threshold (for example, fail if more than 10% of rows are rejected).
- **Hard failures:** the pipeline logs the full traceback and exits non-zero, so cron or Airflow detects it. Add retries with exponential backoff for transient S3 and DB errors.
- **Observability:** per-stage row counts, rejected counts by rule, and run duration are already logged. At scale, ship them to CloudWatch or Prometheus and alert on anomalies.
- **Recovery:** the untouched raw file in S3 makes any run reproducible.

## Assumptions and limitations

- Ambiguous dates are treated as day-first (DD/MM/YYYY).
- The currency is assumed to be USD.
- Data is generated, so the dirt patterns are known. Real data would need profiling first.
- Rejected rows are written to a CSV and logged, not retried automatically.
- A single process loads the data. There is no concurrency control for overlapping runs (an orchestrator or lock would handle that).