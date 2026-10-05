-- Indexes chosen for the analytical queries (the primary key is already indexed)

-- Monthly trends and date-range filters
CREATE INDEX IF NOT EXISTS idx_bookings_booking_date
    ON bookings (booking_date);

-- Revenue by category for confirmed bookings.
-- INCLUDE (price) lets Postgres answer from the index alone (index-only scan).
CREATE INDEX IF NOT EXISTS idx_bookings_status_category_price
    ON bookings (status, category) INCLUDE (price);

-- Average rating by country. Partial index: rows without a rating are skipped,
-- which keeps the index smaller.
CREATE INDEX IF NOT EXISTS idx_bookings_country_rating
    ON bookings (country) INCLUDE (rating)
    WHERE rating IS NOT NULL;