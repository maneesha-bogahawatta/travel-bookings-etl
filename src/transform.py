"""Transform: clean and standardize raw data, then drop duplicates.

Nothing is rejected here. Values that cannot be fixed become NaN/NaT and are
judged by validate.py.
"""
import pandas as pd

from src.logger import get_logger

logger = get_logger(__name__)

CITY_TO_COUNTRY = {
    "Colombo": "Sri Lanka", "Galle": "Sri Lanka", "Kandy": "Sri Lanka",
    "Ella": "Sri Lanka", "Sigiriya": "Sri Lanka",
    "Male": "Maldives", "Maafushi": "Maldives", "Hulhumale": "Maldives",
    "Goa": "India", "Jaipur": "India", "Kerala": "India", "Mumbai": "India",
    "Bangkok": "Thailand", "Phuket": "Thailand", "Chiang Mai": "Thailand",
    "Tokyo": "Japan", "Kyoto": "Japan", "Osaka": "Japan",
    "Paris": "France", "Nice": "France", "Lyon": "France",
    "Rome": "Italy", "Venice": "Italy", "Florence": "Italy",
    "Dubai": "United Arab Emirates", "Abu Dhabi": "United Arab Emirates",
    "New York": "United States", "Los Angeles": "United States", "Miami": "United States",
    "Sydney": "Australia", "Melbourne": "Australia", "Cairns": "Australia",
}
VALID_COUNTRIES = set(CITY_TO_COUNTRY.values())
VALID_CATEGORIES = {"Hotel", "Resort", "Villa", "Tour Package", "Cruise", "Flight + Hotel"}
VALID_STATUSES = {"Confirmed", "Cancelled", "Pending"}

COUNTRY_ALIASES = {
    "usa": "United States", "u.s.a": "United States", "us": "United States",
    "uae": "United Arab Emirates", "u.a.e": "United Arab Emirates",
}

# Dates are day-first (DD/MM/YYYY) when ambiguous
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%b %d, %Y", "%Y/%m/%d"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _clean_text(s: pd.Series) -> pd.Series:
    """Trim, collapse repeated spaces, turn empty strings into NaN."""
    s = s.str.strip().str.replace(r"\s+", " ", regex=True)
    return s.mask(s == "")


def _smart_title(value):
    """Title-case only if the text is ALL UPPER or all lower (keeps 'DDS', 'McDonald')."""
    if not isinstance(value, str):
        return value
    return value.title() if value.isupper() or value.islower() else value


def _standardize_country(s: pd.Series) -> pd.Series:
    s = _clean_text(s)
    aliased = s.str.lower().map(COUNTRY_ALIASES)
    s = aliased.fillna(s.map(_smart_title))
    return s.where(s.isin(VALID_COUNTRIES))  # unknown values -> NaN


def _parse_dates(s: pd.Series) -> pd.Series:
    s = _clean_text(s)
    parsed = pd.to_datetime(s, format=DATE_FORMATS[0], errors="coerce")
    for fmt in DATE_FORMATS[1:]:
        parsed = parsed.fillna(pd.to_datetime(s, format=fmt, errors="coerce"))
    return parsed


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rows_in = len(df)

    # Text columns
    df["booking_id"] = _clean_text(df["booking_id"]).str.upper()
    df["customer_name"] = _clean_text(df["customer_name"]).map(_smart_title)
    df["destination"] = _clean_text(df["destination"]).map(_smart_title)
    df["category"] = _clean_text(df["category"]).map(_smart_title)
    df["status"] = _clean_text(df["status"]).map(_smart_title)

    # Email: lowercase, invalid format -> NaN
    email = _clean_text(df["customer_email"]).str.lower()
    df["customer_email"] = email.where(email.str.match(EMAIL_PATTERN, na=False))

    # Missing names -> "Unknown"
    missing_names = int(df["customer_name"].isna().sum())
    df["customer_name"] = df["customer_name"].fillna("Unknown")

    # Country: standardize aliases/casing, then infer missing from destination
    df["country"] = _standardize_country(df["country"])
    missing_country = int(df["country"].isna().sum())
    df["country"] = df["country"].fillna(df["destination"].map(CITY_TO_COUNTRY))
    inferred = missing_country - int(df["country"].isna().sum())

    # Numbers: strip "$", "USD", commas; invalid text -> NaN
    price = _clean_text(df["price"]).str.replace(r"[^0-9.\-]", "", regex=True)
    df["price"] = pd.to_numeric(price, errors="coerce").round(2)
    df["rating"] = pd.to_numeric(_clean_text(df["rating"]), errors="coerce")

    # Dates: five mixed formats -> one datetime column
    df["booking_date"] = _parse_dates(df["booking_date"])

    # Duplicates: exact copies first, then repeated booking_ids (keep first)
    before = len(df)
    df = df.drop_duplicates()
    exact_dupes = before - len(df)

    repeated_id = df["booking_id"].notna() & df["booking_id"].duplicated(keep="first")
    id_dupes = int(repeated_id.sum())
    df = df[~repeated_id].reset_index(drop=True)

    logger.info("Transform: %s rows in, %s rows out", rows_in, len(df))
    logger.info("Names filled with 'Unknown': %s", missing_names)
    logger.info("Countries inferred from destination: %s", inferred)
    logger.info("Duplicates removed: %s exact, %s repeated booking_id", exact_dupes, id_dupes)
    return df