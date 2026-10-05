-- Q1: Top 10 categories/destinations by revenue (confirmed bookings only)
SELECT category, destination,
       COUNT(*)        AS bookings,
       SUM(price)      AS revenue
FROM bookings
WHERE status = 'Confirmed'
GROUP BY category, destination
ORDER BY revenue DESC
LIMIT 10;

-- Q2: Monthly revenue and month-over-month growth
WITH monthly AS (
    SELECT date_trunc('month', booking_date)::date AS month,
           SUM(price) AS revenue
    FROM bookings
    WHERE status = 'Confirmed'
    GROUP BY 1
)
SELECT month,
       revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS growth_pct
FROM monthly
ORDER BY month;

-- Q3: Average rating and booking count by country
SELECT country,
       ROUND(AVG(rating), 2) AS avg_rating,
       COUNT(rating)         AS rated_bookings
FROM bookings
WHERE rating IS NOT NULL
GROUP BY country
ORDER BY avg_rating DESC;

-- Q4: Date-range filter (used for the index before/after demo)
SELECT COUNT(*), SUM(price)
FROM bookings
WHERE booking_date BETWEEN '2025-03-01' AND '2025-03-31';

-- Q1b: Revenue by category (confirmed bookings only)
SELECT category,
       COUNT(*)   AS bookings,
       SUM(price) AS revenue
FROM bookings
WHERE status = 'Confirmed'
GROUP BY category
ORDER BY revenue DESC;