from pathlib import Path
from urllib.request import urlretrieve
import json
import pandas as pd



ROOT = Path(__file__).resolve().parents[1]

CLEAN_DIR = ROOT / "Data" / "Cleaned"
RAW_DIR = ROOT / "Data" / "Raw"
OUTPUT_DIR = (
    ROOT / "Data" / "processed" / "airport_integration"
)

RAW_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CADORS_FILE = (
    CLEAN_DIR /
    "CADORS_Occurrence_Information_clean.csv"
)

WEATHER_FILE = (
    CLEAN_DIR /
    "weather_all_airports_2018-2025_clean.csv"
)

AIRPORTS_FILE = RAW_DIR / "ourairports_airports.csv"
REGIONS_FILE = RAW_DIR / "ourairports_regions.csv"

AIRPORTS_URL = (
    "https://davidmegginson.github.io/"
    "ourairports-data/airports.csv"
)

REGIONS_URL = (
    "https://davidmegginson.github.io/"
    "ourairports-data/regions.csv"
)

START_DATE = pd.Timestamp("2018-01-01")
END_DATE = pd.Timestamp("2025-12-31")




def download_if_missing(url, destination):

    if destination.exists():
        print(f"Using existing: {destination.name}")
        return

    print(f"Downloading {destination.name}...")

    urlretrieve(url, destination)

    print("Download completed")



def normalize_codes(series):

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )



def main():

    print("\n===== AEROSAFE AIRPORT INTEGRATION =====")

    # Check cleaned inputs.
    for file in [CADORS_FILE, WEATHER_FILE]:

        if not file.exists():
            raise FileNotFoundError(
                f"Missing cleaned dataset: {file}"
            )

    # Download OurAirports only when missing.
    download_if_missing(
        AIRPORTS_URL,
        AIRPORTS_FILE
    )

    download_if_missing(
        REGIONS_URL,
        REGIONS_FILE
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

    airports = pd.read_csv(
        AIRPORTS_FILE,
        low_memory=False
    )

    regions = pd.read_csv(
        REGIONS_FILE,
        low_memory=False
    )

    print(f"CADORS loaded: {len(cadors):,}")
    print(f"Weather loaded: {len(weather):,}")
    print(f"OurAirports loaded: {len(airports):,}")


    required_cadors = {
        "cadorsnumber",
        "occurrencedate",
        "country_enm",
        "aerodromeid"
    }

    required_weather = {
        "airport_code",
        "weather_date"
    }

    missing_cadors = (
        required_cadors - set(cadors.columns)
    )

    missing_weather = (
        required_weather - set(weather.columns)
    )

    if missing_cadors:
        raise ValueError(
            f"Missing CADORS columns: {missing_cadors}"
        )

    if missing_weather:
        raise ValueError(
            f"Missing weather columns: {missing_weather}"
        )



    cadors["occurrencedate"] = pd.to_datetime(
        cadors["occurrencedate"],
        errors="coerce",
        format="mixed"
    )

    canada_mask = (
        cadors["country_enm"].eq("Canada")
        | cadors["country_enm"].isna()
    ).fillna(False)

    date_mask = (
        cadors["occurrencedate"]
        .dt.normalize()
        .between(START_DATE, END_DATE)
    )

    cadors = cadors.loc[
        canada_mask & date_mask
    ].copy()

    cadors["aerodromeid"] = normalize_codes(
        cadors["aerodromeid"]
    )

    cadors["cadorsnumber"] = (
        cadors["cadorsnumber"]
        .astype("string")
        .str.strip()
    )

    if cadors["cadorsnumber"].isna().any():
        raise ValueError(
            "CADORS contains missing occurrence IDs"
        )

    if cadors["cadorsnumber"].duplicated().any():
        raise ValueError(
            "CADORS contains duplicate occurrence IDs"
        )

    original_count = len(cadors)

    print(
        f"Valid CADORS occurrences: "
        f"{original_count:,}"
    )


    for col in ["ident", "gps_code", "icao_code"]:
        if col not in airports.columns:
            airports[col] = pd.NA

    required_airport_columns = [
        "ident",
        "gps_code",
        "icao_code",
        "name",
        "latitude_deg",
        "longitude_deg",
        "iso_region",
        "iso_country"
    ]

    missing_airport_columns = (
        set(required_airport_columns)
        - set(airports.columns)
    )

    if missing_airport_columns:
        raise ValueError(
            f"Missing OurAirports columns: "
            f"{missing_airport_columns}"
        )

    airports = airports[
        required_airport_columns
    ].copy()

    # Retain Canadian airports.
    airports = airports[
        airports["iso_country"].eq("CA")
    ].copy()

    for col in ["ident", "gps_code", "icao_code"]:

        airports[col] = normalize_codes(
            airports[col]
        )

 

    region_reference = regions[
        ["code", "name"]
    ].copy()

    region_reference = region_reference.rename(
        columns={
            "code": "iso_region",
            "name": "province"
        }
    )

    region_reference = (
        region_reference
        .drop_duplicates("iso_region")
    )

    airports = airports.merge(
        region_reference,
        on="iso_region",
        how="left",
        validate="many_to_one"
    )

    print(
        f"Canadian airport reference rows: "
        f"{len(airports):,}"
    )



    # Matching priority:
    # 1. ICAO code
    # 2. OurAirports ident
    # 3. GPS code
    #
    # Ambiguous references will not be guessed.

    lookup_parts = []

    for priority, column in enumerate(
        ["icao_code", "ident", "gps_code"]
    ):

        part = airports.copy()

        part["airport_id"] = part[column]

        part["match_source"] = column

        part["priority"] = priority

        part = part.dropna(
            subset=["airport_id", "ident"]
        )

        lookup_parts.append(part)

    lookup = pd.concat(
        lookup_parts,
        ignore_index=True
    )

    lookup = lookup.drop_duplicates(
        subset=["airport_id", "ident"]
    )

    # Identify ambiguous airport codes.
    code_counts = (
        lookup.groupby("airport_id")["ident"]
        .nunique()
    )

    ambiguous_codes = set(
        code_counts[code_counts > 1].index
    )

    lookup = lookup[
        ~lookup["airport_id"].isin(
            ambiguous_codes
        )
    ].copy()

    lookup = (
        lookup.sort_values("priority")
        .drop_duplicates("airport_id")
    )

    lookup = lookup.rename(
        columns={
            "name": "airport_name",
            "latitude_deg": "latitude",
            "longitude_deg": "longitude"
        }
    )

    lookup = lookup[
        [
            "airport_id",
            "airport_name",
            "province",
            "latitude",
            "longitude",
            "iso_region",
            "match_source"
        ]
    ].copy()


    weather["airport_code"] = normalize_codes(
        weather["airport_code"]
    )

    cadors_codes = set(
        cadors["aerodromeid"]
        .dropna()
        .unique()
    )

    weather_codes = set(
        weather["airport_code"]
        .dropna()
        .unique()
    )

    all_codes = sorted(
        cadors_codes | weather_codes
    )

    required_airports = pd.DataFrame({
        "airport_id": all_codes
    })

    print(
        f"Required unique airport codes: "
        f"{len(required_airports):,}"
    )



    final_airports = required_airports.merge(
        lookup,
        how="left",
        on="airport_id",
        validate="one_to_one"
    )

    final_airports["reference_matched"] = (
        final_airports["airport_name"].notna()
    )

    final_airports["ambiguous_reference"] = (
        final_airports["airport_id"]
        .isin(ambiguous_codes)
    )

    # Validate coordinates.
    final_airports["latitude"] = pd.to_numeric(
        final_airports["latitude"],
        errors="coerce"
    )

    final_airports["longitude"] = pd.to_numeric(
        final_airports["longitude"],
        errors="coerce"
    )

    final_airports["has_coordinates"] = (
        final_airports["latitude"].between(-90, 90)
        &
        final_airports["longitude"].between(-180, 180)
    )

    if final_airports["airport_id"].duplicated().any():
        raise ValueError(
            "Duplicate airport IDs detected"
        )

    

    occurrences = cadors[
        ["cadorsnumber", "aerodromeid"]
    ].copy()

    occurrences = occurrences.merge(
        final_airports,
        left_on="aerodromeid",
        right_on="airport_id",
        how="left",
        validate="many_to_one"
    )

    # IMPORTANT FIX:
    # Determine matches using actual airport data,
    # not nullable/object Boolean inversion.

    missing_airport_mask = (
        occurrences["aerodromeid"].isna()
    )

    matched_airport_mask = (
        occurrences["aerodromeid"].notna()
        & occurrences["airport_name"].notna()
    )

    unmatched_airport_mask = (
        occurrences["aerodromeid"].notna()
        & occurrences["airport_name"].isna()
    )

    occurrences["airport_match_status"] = (
        "unmatched_reference"
    )

    occurrences.loc[
        matched_airport_mask,
        "airport_match_status"
    ] = "matched"

    occurrences.loc[
        missing_airport_mask,
        "airport_match_status"
    ] = "missing_airport_code"


    if len(occurrences) != original_count:
        raise ValueError(
            "CADORS occurrence count changed!"
        )

    if occurrences["cadorsnumber"].duplicated().any():
        raise ValueError(
            "Duplicate CADORS IDs after airport join!"
        )

    matched_records = int(
        matched_airport_mask.sum()
    )

    unmatched_records = int(
        unmatched_airport_mask.sum()
    )

    missing_airport_records = int(
        missing_airport_mask.sum()
    )

    records_with_code = (
        matched_records + unmatched_records
    )

    record_match_rate = (
        round(
            100 * matched_records / records_with_code,
            2
        )
        if records_with_code > 0
        else 0
    )

    if (
        matched_records
        + unmatched_records
        + missing_airport_records
        != original_count
    ):
        raise ValueError(
            "Airport match statuses do not reconcile"
        )

    print("\n===== AIRPORT MATCH STATUS =====")

    print(
        occurrences[
            "airport_match_status"
        ].value_counts()
    )

    print(
        f"Occurrence-level match rate: "
        f"{record_match_rate:.2f}%"
    )



    airport_counts = (
        occurrences[
            occurrences["aerodromeid"].notna()
        ]
        .groupby("aerodromeid")["cadorsnumber"]
        .nunique()
        .reset_index(name="occurrence_count")
    )

    airport_counts = airport_counts.rename(
        columns={
            "aerodromeid": "airport_id"
        }
    )

    airport_summary = final_airports.merge(
        airport_counts,
        on="airport_id",
        how="left",
        validate="one_to_one"
    )

    airport_summary["occurrence_count"] = (
        airport_summary["occurrence_count"]
        .fillna(0)
        .astype(int)
    )

    airport_summary = airport_summary.sort_values(
        "occurrence_count",
        ascending=False
    )



    unmatched_airports = final_airports.loc[
        final_airports["airport_name"].isna()
    ].copy()

    unmatched_airports = unmatched_airports.merge(
        airport_counts,
        how="left",
        on="airport_id",
        validate="one_to_one"
    )

    unmatched_airports["occurrence_count"] = (
        unmatched_airports["occurrence_count"]
        .fillna(0)
        .astype(int)
    )

    unmatched_airports = (
        unmatched_airports.sort_values(
            "occurrence_count",
            ascending=False
        )
    )


    sql_airports = final_airports[
        [
            "airport_id",
            "airport_name",
            "province",
            "latitude",
            "longitude"
        ]
    ].copy()



    sql_airports.to_csv(
        OUTPUT_DIR / "airports.csv",
        index=False
    )

    occurrences.to_csv(
        OUTPUT_DIR /
        "occurrences_airport_reference.csv",
        index=False
    )

    airport_summary.to_csv(
        OUTPUT_DIR /
        "airport_occurrence_summary.csv",
        index=False
    )

    unmatched_airports.to_csv(
        OUTPUT_DIR / "unmatched_airports.csv",
        index=False
    )


    matched_codes = int(
        final_airports["reference_matched"].sum()
    )

    unmatched_codes = int(
        (~final_airports["reference_matched"]).sum()
    )

    code_match_rate = (
        round(
            100 * matched_codes / len(final_airports),
            2
        )
        if len(final_airports)
        else 0
    )

    report = {
        "stage": "09_airport_reference_integration",
        "date_range": "2018-01-01 to 2025-12-31",

        "cadors_occurrences": int(original_count),
        "occurrences_after_join": int(
            len(occurrences)
        ),

        "required_airport_codes": int(
            len(final_airports)
        ),

        "matched_airport_codes": matched_codes,
        "unmatched_airport_codes": unmatched_codes,
        "ambiguous_airport_codes": int(
            final_airports["ambiguous_reference"].sum()
        ),

        "airport_code_match_rate_pct": (
            code_match_rate
        ),

        "records_with_airport_code": int(
            records_with_code
        ),

        "records_with_matched_airport": (
            matched_records
        ),

        "records_with_unmatched_airport": (
            unmatched_records
        ),

        "records_without_airport_code": (
            missing_airport_records
        ),

        "record_match_rate_pct": (
            record_match_rate
        ),

        "weather_airports": int(
            len(weather_codes)
        ),

        "validation": {
            "occurrence_count_unchanged": (
                len(occurrences) == original_count
            ),

            "unique_cadors_ids": bool(
                occurrences["cadorsnumber"].is_unique
            ),

            "unique_airport_ids": bool(
                final_airports["airport_id"].is_unique
            ),

            "weather_codes_preserved": bool(
                weather_codes.issubset(
                    set(final_airports["airport_id"])
                )
            ),

            "status_counts_reconciled": bool(
                matched_records
                + unmatched_records
                + missing_airport_records
                == original_count
            )
        }
    }

    with open(
        OUTPUT_DIR / "integration_report.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            report,
            file,
            indent=4
        )


    print("\n===== AIRPORT INTEGRATION RESULTS =====")

    print(
        f"CADORS occurrences: {original_count:,}"
    )

    print(
        f"Required airport codes: "
        f"{len(final_airports):,}"
    )

    print(
        f"Matched airport codes: {matched_codes:,}"
    )

    print(
        f"Unmatched airport codes: {unmatched_codes:,}"
    )

    print(
        f"Airport code match rate: "
        f"{code_match_rate:.2f}%"
    )

    print(
        f"Records with airport code: "
        f"{records_with_code:,}"
    )

    print(
        f"Records with matched airport: "
        f"{matched_records:,}"
    )

    print(
        f"Records with unmatched airport: "
        f"{unmatched_records:,}"
    )

    print(
        f"Records missing airport code: "
        f"{missing_airport_records:,}"
    )

    print(
        f"Occurrence-level match rate: "
        f"{record_match_rate:.2f}%"
    )

    print("\n===== TOP 10 AIRPORTS =====")

    print(
        airport_summary[
            [
                "airport_id",
                "airport_name",
                "occurrence_count"
            ]
        ].head(10).to_string(index=False)
    )

    print("\n===== UNMATCHED AIRPORTS =====")

    print(
        unmatched_airports[
            ["airport_id", "occurrence_count"]
        ].to_string(index=False)
    )

    print(
        f"\nOutput folder: {OUTPUT_DIR}"
    )

    print("\nSTEP 09 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
