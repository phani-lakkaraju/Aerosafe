
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "cleaned"

files = [
    "CADORS_Occurrence_Information_clean.csv",
    "CADORS_Occurrence_Category_clean.csv",
    "CADORS_Occurrence_Event_Information_clean.csv",
    "CADORS_Aircraft_Information_clean.csv",
    "CADORS_Aircraft_Event_Information_clean.csv",
]

for file in files:
    path = CLEAN_DIR / file
    df = pd.read_csv(path, low_memory=False)

    print("\n" + "=" * 60)
    print(f"FILE: {file}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Duplicate rows: {df.duplicated().sum():,}")
    print(f"Missing cells: {df.isna().sum().sum():,}")

    if "cadorsnumber" in df.columns:
        print("Missing occurrence IDs:", df["cadorsnumber"].isna().sum())

    if "occurrencedate" in df.columns:
        dates = pd.to_datetime(df["occurrencedate"], errors="coerce")
        print("Unparseable dates:", dates.isna().sum())
        print("Earliest date:", dates.min())
        print("Latest date:", dates.max())

print("\nVALIDATION COMPLETED")
