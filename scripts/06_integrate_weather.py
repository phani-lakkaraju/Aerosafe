from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import pandas as pd


# =====================================================
# 1. PROJECT PATHS
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

CLEAN_DIR = ROOT / "Data" / "Cleaned"
PROCESSED_DIR = ROOT / "Data" / "processed"
OUTPUT_DIR = PROCESSED_DIR / "weather_integration"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CADORS_FILE = (
    CLEAN_DIR / "CADORS_Occurrence_Information_clean.csv"
)

WEATHER_FILE = (
    CLEAN_DIR / "weather_all_airports_2018-2025_clean.csv"
)

METADATA_FILE = (
    PROCESSED_DIR / "weather_source_metadata.csv"
)

START_DATE = pd.Timestamp("2018-01-01")
END_DATE = pd.Timestamp("2025-12-31")


# Actual geographical timezones for the 13 airports.
# Used to audit source timezone settings.
AIRPORT_TIMEZONES = {
    "CYEG": "America/Edmonton",
    "CYHZ": "America/Halifax",
    "CYOW": "America/Toronto",
    "CYQB": "America/Toronto",
    "CYUL": "America/Toronto",
    "CYVR": "America/Vancouver",
    "CYWG": "America/Winnipeg",
    "CYXY": "America/Whitehorse",
    "CYYC": "America/Edmonton",
    "CYYJ": "America/Vancouver",
    "CYYT": "America/St_Johns",
    "CYYZ": "America/Toronto",
    "CYZF": "America/Yellowknife",
}


# =====================================================
# 2. LOAD CLEANED DATA
# =====================================================

print("\n===== AEROSAFE WEATHER INTEGRATION =====")

for file in [CADORS_FILE, WEATHER_FILE, METADATA_FILE]:
    if not file.exists():
        raise FileNotFoundError(
            f"Required file not found: {file}"
        )

cadors = pd.read_csv(
    CADORS_FILE,
    low_memory=False,
    dtype={"cadorsnumber": "string"}
)

weather = pd.read_csv(
    WEATHER_FILE,
    low_memory=False
)

metadata = pd.read_csv(METADATA_FILE)

print(f"CADORS records loaded: {len(cadors):,}")
print(f"Weather records loaded: {len(weather):,}")


# =====================================================
# 3. VALIDATE INPUTS
# =====================================================

required_cadors = [
    "cadorsnumber",
    "occurrencedate",
    "occurrencetime",
    "aerodromeid",
    "country_enm",
]

required_weather = [
    "airport_code",
    "weather_date",
    "precipitation_mm",
    "rain_mm",
    "snowfall_cm",
    "wind_speed_max_kmh",
]

for col in required_cadors:
    if col not in cadors.columns:
        raise ValueError(f"Missing CADORS column: {col}")

for col in required_weather:
    if col not in weather.columns:
        raise ValueError(f"Missing weather column: {col}")

if not {"airport_code", "timezone"}.issubset(
    metadata.columns
):
    raise ValueError("Missing weather timezone metadata")

cadors["occurrencedate"] = pd.to_datetime(
    cadors["occurrencedate"],
    errors="coerce"
).dt.normalize()

weather["weather_date"] = pd.to_datetime(
    weather["weather_date"],
    errors="coerce"
).dt.normalize()

cadors["aerodromeid"] = (
    cadors["aerodromeid"]
    .astype("string")
    .str.strip()
    .str.upper()
    .replace("", pd.NA)
)

weather["airport_code"] = (
    weather["airport_code"]
    .astype("string")
    .str.strip()
    .str.upper()
)

metadata["airport_code"] = (
    metadata["airport_code"]
    .astype("string")
    .str.strip()
    .str.upper()
)

# Keep the project scope: Canada or blank country.
cadors = cadors[
    cadors["country_enm"].eq("Canada")
    | cadors["country_enm"].isna()
].copy()

cadors = cadors[
    cadors["occurrencedate"].between(
        START_DATE, END_DATE
    )
].copy()

weather = weather[
    weather["weather_date"].between(
        START_DATE, END_DATE
    )
].copy()

if cadors["cadorsnumber"].isna().any():
    raise ValueError("Missing CADORS occurrence IDs")

if cadors["cadorsnumber"].duplicated().any():
    raise ValueError("Duplicate CADORS occurrence IDs")

if weather[["airport_code", "weather_date"]].isna().any().any():
    raise ValueError("Missing weather airport/date keys")

if weather.duplicated(
    ["airport_code", "weather_date"]
).any():
    raise ValueError("Duplicate weather airport-date keys")

if metadata["airport_code"].duplicated().any():
    raise ValueError("Duplicate airport metadata entries")

original_count = len(cadors)

print(f"Valid CADORS occurrences: {original_count:,}")
print(f"Weather airports: {weather['airport_code'].nunique()}")


# =====================================================
# 4. TIMEZONE AUDIT
# =====================================================

metadata = metadata[
    ["airport_code", "timezone"]
].copy()

metadata = metadata.rename(
    columns={"timezone": "source_timezone"}
)

metadata["expected_timezone"] = (
    metadata["airport_code"]
    .map(AIRPORT_TIMEZONES)
)

metadata["timezone_mismatch"] = (
    metadata["source_timezone"]
    != metadata["expected_timezone"]
)

timezone_issues = metadata[
    metadata["timezone_mismatch"]
].copy()

timezone_issues.to_csv(
    OUTPUT_DIR / "timezone_audit.csv",
    index=False
)

print(
    "Airports with timezone configuration differences:",
    len(timezone_issues)
)

# IMPORTANT:
# Weather dates reflect the timezone used when
# Open-Meteo generated that source file.
#
# We therefore match timestamps using the SOURCE
# timezone, not an assumed geographical timezone.
#
# Any mismatched timezone is flagged for review.
# Accurate geographical-local weather comparisons
# may require re-downloading those weather files.


# =====================================================
# 5. PARSE UTC OCCURRENCE TIMESTAMPS
# =====================================================

def parse_utc_timestamp(date_value, time_value):
    """
    CADORS time example: '1615 Z' or '0100 Z'.
    A missing/invalid time returns NaT.
    """

    if pd.isna(date_value) or pd.isna(time_value):
        return pd.NaT

    value = str(time_value).strip().upper()

    match = re.fullmatch(
        r"(\d{2}):?(\d{2})\s*Z?",
        value
    )

    if match is None:
        return pd.NaT

    hour = int(match.group(1))
    minute = int(match.group(2))

    if hour > 23 or minute > 59:
        return pd.NaT

    stamp = pd.Timestamp(date_value)

    return datetime(
        stamp.year,
        stamp.month,
        stamp.day,
        hour,
        minute,
        tzinfo=timezone.utc
    )


cadors["occurrence_datetime_utc"] = [
    parse_utc_timestamp(date, time)
    for date, time in zip(
        cadors["occurrencedate"],
        cadors["occurrencetime"]
    )
]

cadors = cadors.merge(
    metadata,
    how="left",
    left_on="aerodromeid",
    right_on="airport_code",
    validate="many_to_one"
)

cadors = cadors.drop(columns=["airport_code"])


# =====================================================
# 6. CONVERT UTC TO WEATHER SOURCE DATE
# =====================================================

def get_weather_match_date(row):
    """
    Convert UTC timestamp into the weather file's
    configured timezone.

    If time is unavailable, use the occurrence date,
    as specified in the design document.
    """

    dt = row["occurrence_datetime_utc"]
    tz_name = row["source_timezone"]

    if pd.isna(dt):
        return row["occurrencedate"]

    if pd.isna(tz_name):
        return row["occurrencedate"]

    try:
        return pd.Timestamp(
            dt.astimezone(ZoneInfo(str(tz_name))).date()
        )
    except (KeyError, ValueError):
        return row["occurrencedate"]


cadors["weather_match_date"] = cadors.apply(
    get_weather_match_date,
    axis=1
)

cadors["weather_match_date"] = pd.to_datetime(
    cadors["weather_match_date"]
)

cadors["missing_occurrence_time"] = (
    cadors["occurrence_datetime_utc"].isna()
)

cadors["missing_airport"] = (
    cadors["aerodromeid"].isna()
)

cadors["timezone_review_required"] = (
    cadors["timezone_mismatch"]
    .fillna(False)
    .astype(bool)
)

print("UTC timestamp processing completed")


# =====================================================
# 7. LEFT JOIN CADORS WITH DAILY WEATHER
# =====================================================

weather_airports = set(
    weather["airport_code"].dropna()
)

cadors["has_weather_coverage"] = (
    cadors["aerodromeid"].isin(weather_airports)
)

integrated = cadors.merge(
    weather,
    how="left",
    left_on=["aerodromeid", "weather_match_date"],
    right_on=["airport_code", "weather_date"],
    validate="many_to_one",
    indicator=True
)

integrated["weather_matched"] = (
    integrated["_merge"].eq("both")
)

integrated["weather_match_status"] = "matched"

integrated.loc[
    integrated["missing_airport"],
    "weather_match_status"
] = "missing_airport"

integrated.loc[
    ~integrated["missing_airport"]
    & ~integrated["has_weather_coverage"],
    "weather_match_status"
] = "no_weather_coverage"

integrated.loc[
    integrated["has_weather_coverage"]
    & ~integrated["weather_matched"],
    "weather_match_status"
] = "missing_weather_day"

integrated = integrated.drop(columns=["_merge"])

if len(integrated) != original_count:
    raise ValueError(
        "Occurrence count changed during weather integration!"
    )

if integrated["cadorsnumber"].duplicated().any():
    raise ValueError(
        "Duplicate occurrence IDs after weather integration!"
    )

print(
    f"Matched weather occurrences: "
    f"{integrated['weather_matched'].sum():,}"
)

print(
    integrated["weather_match_status"].value_counts()
)


# =====================================================
# 8. WEATHER CATEGORIES (ALGORITHM 3)
# =====================================================

# Exploratory thresholds; document these in the report.
RAIN_THRESHOLD_MM = 0.1
SNOW_THRESHOLD_CM = 0.1
STRONG_WIND_THRESHOLD_KMH = 40.0

def classify_weather(df):
    df = df.copy()

    df["rain_flag"] = (
        df["rain_mm"] >= RAIN_THRESHOLD_MM
    )

    df["snow_flag"] = (
        df["snowfall_cm"] >= SNOW_THRESHOLD_CM
    )

    df["strong_wind_flag"] = (
        df["wind_speed_max_kmh"]
        >= STRONG_WIND_THRESHOLD_KMH
    )

    # Multiple conditions can occur on the same day.
    df["weather_category"] = "none"

    df.loc[
        df["rain_flag"], "weather_category"
    ] = "rain"

    df.loc[
        df["snow_flag"], "weather_category"
    ] = "snow"

    df.loc[
        df["strong_wind_flag"], "weather_category"
    ] = "strong_wind"

    return df


weather = classify_weather(weather)


# =====================================================
# 9. DAILY OCCURRENCE COUNTS INCLUDING ZERO DAYS
# =====================================================

# Every weather airport/date already exists in the
# cleaned combined weather file.
# Start from this complete calendar so zero days remain.

matched = integrated[
    integrated["weather_matched"]
].copy()

daily_counts = (
    matched.groupby(
        ["aerodromeid", "weather_match_date"]
    )["cadorsnumber"]
    .nunique()
    .reset_index(name="occurrence_count")
)

airport_daily = weather.merge(
    daily_counts,
    how="left",
    left_on=["airport_code", "weather_date"],
    right_on=["aerodromeid", "weather_match_date"],
    validate="one_to_one"
)

airport_daily["occurrence_count"] = (
    airport_daily["occurrence_count"]
    .fillna(0)
    .astype(int)
)

airport_daily = airport_daily.drop(
    columns=["aerodromeid", "weather_match_date"]
)

if len(airport_daily) != len(weather):
    raise ValueError(
        "Weather calendar count changed during aggregation"
    )

if airport_daily["occurrence_count"].sum() != len(matched):
    raise ValueError(
        "Daily occurrence counts do not reconcile"
    )

print(
    "Zero-occurrence airport days:",
    int((airport_daily["occurrence_count"] == 0).sum())
)


# =====================================================
# 10. WEATHER SUMMARY (DESCRIPTIVE ONLY)
# =====================================================

weather_summary = (
    airport_daily.groupby("weather_category")
    .agg(
        total_days=("weather_date", "size"),
        total_occurrences=("occurrence_count", "sum"),
        average_daily_occurrences=(
            "occurrence_count", "mean"
        )
    )
    .reset_index()
)

# This is a descriptive comparison, not causal
# evidence or a flight-adjusted accident rate.


# =====================================================
# 11. SAVE OUTPUT FILES
# =====================================================

integrated.to_csv(
    OUTPUT_DIR / "occurrences_weather.csv",
    index=False
)

weather.to_csv(
    OUTPUT_DIR / "weather_daily.csv",
    index=False
)

airport_daily.to_csv(
    OUTPUT_DIR / "airport_daily_counts_weather.csv",
    index=False
)

weather_summary.to_csv(
    OUTPUT_DIR / "weather_category_summary.csv",
    index=False
)


# =====================================================
# 12. INTEGRATION VALIDATION REPORT
# =====================================================

report = {
    "stage": "07_weather_integration",
    "date_range": "2018-01-01 to 2025-12-31",
    "cadors_occurrences": int(original_count),
    "occurrences_after_join": int(len(integrated)),
    "weather_airports": int(
        weather["airport_code"].nunique()
    ),
    "weather_days": int(len(weather)),
    "matched_occurrences": int(len(matched)),
    "unmatched_occurrences": int(
        len(integrated) - len(matched)
    ),
    "missing_occurrence_times": int(
        integrated["missing_occurrence_time"].sum()
    ),
    "timezone_airports_to_review": (
        timezone_issues["airport_code"].tolist()
    ),
    "zero_occurrence_airport_days": int(
        (airport_daily["occurrence_count"] == 0).sum()
    ),
    "status_counts": {
        str(k): int(v)
        for k, v in integrated[
            "weather_match_status"
        ].value_counts().items()
    },
    "weather_thresholds": {
        "rain_mm": RAIN_THRESHOLD_MM,
        "snowfall_cm": SNOW_THRESHOLD_CM,
        "strong_wind_kmh": STRONG_WIND_THRESHOLD_KMH
    },
    "validation": {
        "occurrence_count_unchanged": (
            len(integrated) == original_count
        ),
        "no_duplicate_occurrence_ids": (
            not integrated["cadorsnumber"]
            .duplicated().any()
        ),
        "daily_counts_reconciled": (
            int(airport_daily["occurrence_count"].sum())
            == len(matched)
        )
    }
}

with open(
    OUTPUT_DIR / "integration_report.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(report, f, indent=4)


print("\n===== INTEGRATION COMPLETED =====")
print(f"Original occurrences: {original_count:,}")
print(f"Retained occurrences: {len(integrated):,}")
print(f"Weather matches: {len(matched):,}")
print(f"Weather airport-days: {len(airport_daily):,}")
print(f"Output folder: {OUTPUT_DIR}")

if len(timezone_issues):
    print(
        "\nWARNING: Source timezone differences found."
        "\nReview timezone_audit.csv before final analysis."
    )

print("\nSTEP 07 COMPLETED SUCCESSFULLY")
