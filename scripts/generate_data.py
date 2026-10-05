"""
Generate a deliberately dirty travel-bookings dataset (simulates a raw source).

Output: data/raw/travel_bookings_raw.csv
Run:    python scripts/generate_data.py
"""
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
N_RECORDS = 12_000
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "travel_bookings_raw.csv"

random.seed(SEED)
np.random.seed(SEED)
Faker.seed(SEED)
fake = Faker()

DESTINATIONS = {
    "Sri Lanka": ["Colombo", "Galle", "Kandy", "Ella", "Sigiriya"],
    "Maldives": ["Male", "Maafushi", "Hulhumale"],
    "India": ["Goa", "Jaipur", "Kerala", "Mumbai"],
    "Thailand": ["Bangkok", "Phuket", "Chiang Mai"],
    "Japan": ["Tokyo", "Kyoto", "Osaka"],
    "France": ["Paris", "Nice", "Lyon"],
    "Italy": ["Rome", "Venice", "Florence"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi"],
    "United States": ["New York", "Los Angeles", "Miami"],
    "Australia": ["Sydney", "Melbourne", "Cairns"],
}

# category -> (min price, max price) in USD
CATEGORY_PRICE_RANGE = {
    "Hotel": (80, 400),
    "Resort": (200, 1200),
    "Villa": (300, 1500),
    "Tour Package": (150, 900),
    "Cruise": (500, 3000),
    "Flight + Hotel": (400, 2200),
}

STATUSES = ["Confirmed", "Cancelled", "Pending"]
STATUS_WEIGHTS = [0.80, 0.12, 0.08]

COUNTRY_ALIASES = {
    "United States": ["USA", "U.S.A", "US"],
    "United Arab Emirates": ["UAE", "U.A.E"],
}

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%b %d, %Y", "%Y/%m/%d"]
DATE_WEIGHTS = [0.40, 0.25, 0.15, 0.10, 0.10]

START_DATE = date(2023, 1, 1)
END_DATE = date(2026, 9, 30)


def chance(p):
    return random.random() < p


def messy_text(value):
    """Apply random casing / whitespace noise to a string."""
    style = random.choice(["upper", "lower", "pad", "pad_lower"])
    if style == "upper":
        return value.upper()
    if style == "lower":
        return value.lower()
    if style == "pad":
        return f"  {value} "
    return f" {value.lower()}  "


def format_date(d):
    fmt = random.choices(DATE_FORMATS, weights=DATE_WEIGHTS)[0]
    return d.strftime(fmt)


def generate_clean_record(i):
    country = random.choice(list(DESTINATIONS))
    city = random.choice(DESTINATIONS[country])
    category = random.choice(list(CATEGORY_PRICE_RANGE))
    low, high = CATEGORY_PRICE_RANGE[category]
    rating = round(min(5.0, max(1.0, np.random.normal(4.1, 0.6))), 1)
    booking_date = START_DATE + timedelta(days=random.randint(0, (END_DATE - START_DATE).days))

    return {
        "booking_id": f"BK{100000 + i}",
        "customer_name": fake.name(),
        "customer_email": fake.email(),
        "country": country,
        "destination": city,
        "category": category,
        "status": random.choices(STATUSES, weights=STATUS_WEIGHTS)[0],
        "price": round(random.uniform(low, high), 2),
        "rating": rating,
        "booking_date": booking_date,
    }


def dirty_record(rec):
    r = dict(rec)

    # booking_id: rarely missing
    if chance(0.002):
        r["booking_id"] = None

    # customer_name: missing or messy casing/spacing
    if chance(0.03):
        r["customer_name"] = random.choice([None, ""])
    elif chance(0.10):
        r["customer_name"] = messy_text(r["customer_name"])

    # customer_email: missing, invalid, or uppercase
    if chance(0.04):
        r["customer_email"] = random.choice([None, ""])
    elif chance(0.02):
        r["customer_email"] = r["customer_email"].replace("@", "")
    elif chance(0.05):
        r["customer_email"] = r["customer_email"].upper()

    # country: missing, aliases (USA, UAE), messy casing
    if chance(0.03):
        r["country"] = None
    elif r["country"] in COUNTRY_ALIASES and chance(0.4):
        r["country"] = random.choice(COUNTRY_ALIASES[r["country"]])
    elif chance(0.15):
        r["country"] = messy_text(r["country"])

    # destination, category, status: inconsistent casing/whitespace
    if chance(0.06):
        r["destination"] = messy_text(r["destination"])
    if chance(0.12):
        r["category"] = messy_text(r["category"])
    if chance(0.10):
        r["status"] = messy_text(r["status"])

    # price: missing, negative, or formatted as text
    p = r["price"]
    if chance(0.03):
        r["price"] = None
    elif chance(0.01):
        r["price"] = -abs(p)
    elif chance(0.10):
        r["price"] = random.choice([f"${p:,.2f}", f"USD {p:.1f}", f"{p:,.2f}"])

    # rating: missing, out of range, or text
    if chance(0.06):
        r["rating"] = None
    elif chance(0.015):
        r["rating"] = random.choice([0, -1, 6, 7.5, 10])
    elif chance(0.02):
        r["rating"] = "N/A"

    # booking_date: mixed formats, missing, future, or invalid
    if chance(0.02):
        r["booking_date"] = None
    elif chance(0.005):
        future = END_DATE + timedelta(days=random.randint(30, 400))
        r["booking_date"] = format_date(future)
    elif chance(0.005):
        r["booking_date"] = random.choice(["31/02/2024", "2024-13-45", "00/00/0000", "TBD"])
    else:
        r["booking_date"] = format_date(r["booking_date"])

    return r


def main():
    records = [dirty_record(generate_clean_record(i)) for i in range(1, N_RECORDS + 1)]
    df = pd.DataFrame(records)

    # Exact duplicate rows (3%)
    exact_dupes = df.sample(frac=0.03, random_state=SEED)

    # Near duplicates: same booking_id, slightly different values (1%)
    near_dupes = df.sample(frac=0.01, random_state=SEED + 1).copy()
    near_dupes["customer_name"] = near_dupes["customer_name"].apply(
        lambda v: v.upper() if isinstance(v, str) else v
    )

    df = pd.concat([df, exact_dupes, near_dupes], ignore_index=True)
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(df):,} rows to {OUTPUT_PATH}")
    print(f"Duplicate booking_ids: {df['booking_id'].duplicated().sum():,}")
    print("Missing values per column:")
    print(df.isna().sum().to_string())


if __name__ == "__main__":
    main()
