-- Index performance demo on a 1.1M-row benchmark table.
-- Run:  psql -d travel_bookings -f sql/04_index_demo.sql

\echo '=== Building benchmark table (about 1.1M rows) ==='
DROP TABLE IF EXISTS bookings_bench;
CREATE TABLE bookings_bench AS
SELECT b.booking_id || '-' || g AS booking_id,
       b.category, b.destination, b.country, b.status,
       b.price, b.rating, b.booking_date
FROM bookings b
CROSS JOIN generate_series(1, 100) AS g;

ANALYZE bookings_bench;

-- Disable parallel workers so the plans are easy to read
SET max_parallel_workers_per_gather = 0;

\echo ''
\echo '=== BEFORE: no index on booking_date ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(price)
FROM bookings_bench
WHERE booking_date BETWEEN '2025-03-01' AND '2025-03-31';

\echo ''
\echo '=== Creating index ==='
CREATE INDEX idx_bench_booking_date ON bookings_bench (booking_date);
ANALYZE bookings_bench;

\echo ''
\echo '=== AFTER: with index on booking_date ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(price)
FROM bookings_bench
WHERE booking_date BETWEEN '2025-03-01' AND '2025-03-31';

-- Clean up
DROP TABLE bookings_bench;
\echo ''
\echo '=== Benchmark table dropped ==='