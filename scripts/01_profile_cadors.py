
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "data" / "processed"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

files = [
    "CADORS_Occurrence_Information.csv",
    "CADORS_Occurrence_Category.csv",
    "CADORS_Occurrence_Event_Information.csv",
    "CADORS_Aircraft_Information.csv",
    "CADORS_Aircraft_Event_Information.csv",
]

# Candidate keys for checking record uniqueness
keys = {
    "CADORS_Occurrence_Information.csv":
        ["cadorsnumber"],

    "CADORS_Occurrence_Category.csv":
        ["cadorsnumber", "occurrence_category_etxt"],

    "CADORS_Occurrence_Event_Information.csv":
        ["cadorsnumber", "event_name_enm"],

    "CADORS_Aircraft_Information.csv":
        ["cadorsnumber", "aircraftnumber"],

    "CADORS_Aircraft_Event_Information.csv":
        ["cadorsnumber", "aircraftnumber", "event_seq_num"],
}

summary = []
missing_reports = []
empty_reports = []
duplicate_reports = []
dtype_reports = []

for file in files:
    path = RAW_DIR / file

    if not path.exists():
        print(f"\nFILE NOT FOUND: {path}")
        continue

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        low_memory=False
    )

    missing = df.isna().sum()
    empty_counts = df.apply(
        lambda col: col.map(
            lambda x: isinstance(x, str) and x.strip() == ""
        ).sum()
    )

    key_columns = keys[file]
    duplicate_keys = df.duplicated(
        subset=key_columns,
        keep=False
    )

    summary.append({
        "file": file,
        "rows": len(df),
        "columns": len(df.columns),
        "missing_cells": int(missing.sum()),
        "fully_duplicate_rows": int(df.duplicated().sum()),
        "empty_string_cells": int(empty_counts.sum()),
        "duplicate_key_rows": int(duplicate_keys.sum()),
        "key_columns": ", ".join(key_columns),
    })

    for column in df.columns:
        if missing[column] > 0:
            missing_reports.append({
                "file": file,
                "column": column,
                "missing_count": int(missing[column]),
                "missing_percent": round(
                    missing[column] / len(df) * 100, 2
                ),
            })

        if empty_counts[column] > 0:
            empty_reports.append({
                "file": file,
                "column": column,
                "empty_string_count": int(empty_counts[column]),
            })

    dtype_reports.extend([
        {
            "file": file,
            "column": column,
            "data_type": str(df[column].dtype),
        }
        for column in df.columns
    ])

    duplicate_reports.append({
        "file": file,
        "duplicate_key_rows": int(duplicate_keys.sum()),
        "key_columns": ", ".join(key_columns),
    })

    print(f"\n{'=' * 60}")
    print(f"FILE: {file}")
    print(f"Rows: {len(df):,} | Columns: {len(df.columns)}")
    print(f"Missing cells: {missing.sum():,}")
    print(f"Fully duplicate rows: {df.duplicated().sum():,}")
    print(f"Empty-string cells: {empty_counts.sum():,}")
    print(f"Duplicate key rows: {duplicate_keys.sum():,}")
    print(f"Candidate key: {key_columns}")

# Save all reports
pd.DataFrame(summary).to_csv(
    REPORT_DIR / "cadors_quality_summary.csv", index=False
)
pd.DataFrame(missing_reports).to_csv(
    REPORT_DIR / "cadors_missing_values.csv", index=False
)
pd.DataFrame(empty_reports).to_csv(
    REPORT_DIR / "cadors_empty_strings.csv", index=False
)
pd.DataFrame(duplicate_reports).to_csv(
    REPORT_DIR / "cadors_duplicate_keys.csv", index=False
)
pd.DataFrame(dtype_reports).to_csv(
    REPORT_DIR / "cadors_data_types.csv", index=False
)

print("\n" + "=" * 60)
print("ALL CHECKS COMPLETED")
print(f"Reports saved to: {REPORT_DIR}")
print("1. cadors_quality_summary.csv")
print("2. cadors_missing_values.csv")
print("3. cadors_empty_strings.csv")
print("4. cadors_duplicate_keys.csv")
print("5. cadors_data_types.csv")
