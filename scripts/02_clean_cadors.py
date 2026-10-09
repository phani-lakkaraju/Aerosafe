
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "cleaned"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

files = [
    "CADORS_Occurrence_Information.csv",
    "CADORS_Occurrence_Category.csv",
    "CADORS_Occurrence_Event_Information.csv",
    "CADORS_Aircraft_Information.csv",
    "CADORS_Aircraft_Event_Information.csv",
]

def clean_column_name(name):
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    return name.strip("_").lower()

for file in files:
    source = RAW_DIR / file

    df = pd.read_csv(
        source,
        encoding="utf-8-sig",
        low_memory=False
    )

    original_rows = len(df)

    # Standardize column names
    df.columns = [clean_column_name(c) for c in df.columns]

    # Remove leading/trailing whitespace from text cells
    for col in df.select_dtypes(include="str").columns:
        df[col] = df[col].str.strip()

    # Convert known numeric fields without deleting invalid values
    for col in ["fatalities", "injuries", "aircraftyearbuilt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert aircraft number only if all values are whole numbers
    if "aircraftnumber" in df.columns:
        values = pd.to_numeric(df["aircraftnumber"], errors="coerce")
        valid = values.dropna()

        if (valid % 1 == 0).all():
            df["aircraftnumber"] = values.astype("Int64")

    # Parse occurrence dates and report failures
    if "occurrencedate" in df.columns:
        original_dates = df["occurrencedate"].copy()
        parsed_dates = pd.to_datetime(
            original_dates,
            format="mixed",
            errors="coerce"
        )

        failed = original_dates.notna() & parsed_dates.isna()

        print(f"\n{file}")
        print(f"Rows before cleaning: {original_rows:,}")
        print(f"Date parsing failures: {failed.sum():,}")

        if failed.any():
            print("Examples of unparsed dates:")
            print(original_dates[failed].head(10).to_list())

        df["occurrencedate"] = parsed_dates

    output = CLEAN_DIR / file.replace(".csv", "_clean.csv")
    df.to_csv(output, index=False, date_format="%Y-%m-%d")

    print(f"Rows after cleaning: {len(df):,}")
    print(f"Saved: {output}")

print("\nCLEANING COMPLETED")
