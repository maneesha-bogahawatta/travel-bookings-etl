-- Schema for the travel bookings table (PostgreSQL 11+)
CREATE TABLE IF NOT EXISTS bookings (
    booking_id      VARCHAR(10)    PRIMARY KEY,
    customer_name   VARCHAR(150)   NOT NULL,
    customer_email  VARCHAR(255),
    country         VARCHAR(60)    NOT NULL,
    destination     VARCHAR(60)    NOT NULL,
    category        VARCHAR(30)    NOT NULL,
    status          VARCHAR(20)    NOT NULL,
    price           NUMERIC(10,2)  NOT NULL,
    rating          NUMERIC(2,1),
    booking_date    DATE           NOT NULL,
    loaded_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT chk_booking_id_format CHECK (booking_id ~ '^BK[0-9]{6}$'),
    CONSTRAINT chk_price_positive    CHECK (price > 0),
    CONSTRAINT chk_rating_range      CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    CONSTRAINT chk_status            CHECK (status IN ('Confirmed', 'Cancelled', 'Pending')),
    CONSTRAINT chk_category          CHECK (category IN
        ('Hotel', 'Resort', 'Villa', 'Tour Package', 'Cruise', 'Flight + Hotel'))
);