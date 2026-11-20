
"""AeroSafe - TSB Integration and Keyword Analysis."""

from pathlib import Path
import json
import re
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "Data" / "Cleaned"
OUT = ROOT / "Data" / "processed" / "tsb_integration"

OUT.mkdir(parents=True, exist_ok=True)

CADORS_PATH = (
    CLEAN / "CADORS_Occurrence_Information_clean.csv"
)

TSB_PATH = (
    CLEAN / "TSB_ASIS_Occurrence_2018-2025_clean.csv"
)



THEMES = {
    "icing": [
        r"\bicing\b",
        r"\bice accumulation\b",
        r"\bgivrage\b",
        r"\bgivre\b",
    ],
    "loss_of_control": [
        r"\bloss of control\b",
        r"\bperte de contr[oô]le\b",
    ],
    "engine_power": [
        r"\bengine failure\b",
        r"\bengine power\b",
        r"\bperte de puissance\b",
        r"\bpanne moteur\b",
    ],
    "visibility": [
        r"\bpoor visibility\b",
        r"\breduced visibility\b",
        r"\bvisibilit[eé] r[eé]duite\b",
    ],
    "bird_strike": [
        r"\bbird strike\b",
        r"\bbirdstrike\b",
        r"\bimpact d.oiseau\b",
        r"\bcollision aviaire\b",
    ],
    "runway_excursion": [
        r"\brunway excursion\b",
        r"\bsortie de piste\b",
    ],
    "turbulence": [
        r"\bturbulence\b",
        r"\bturbulences\b",
    ],
    "wind": [
        r"\bcrosswind\b",
        r"\bwind shear\b",
        r"\bcisaillement du vent\b",
        r"\bvent de travers\b",
    ],
}


def normalize_ids(series):
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )



def main():

    print("\n===== AEROSAFE TSB INTEGRATION =====")

    for path in [CADORS_PATH, TSB_PATH]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing input file: {path}"
            )

    # Load cleaned data
    cad = pd.read_csv(
        CADORS_PATH,
        dtype={
            "cadorsnumber": "string",
            "tsboccurrencenumber": "string",
        },
        low_memory=False,
    )

    tsb = pd.read_csv(
        TSB_PATH,
        dtype={
            "OccID": "string",
            "OccNo": "string",
        },
        low_memory=False,
    )



    cad_required = {
        "cadorsnumber",
        "country_enm",
        "occurrencedate",
        "tsboccurrencenumber",
    }

    tsb_required = {
        "OccID",
        "OccNo",
        "OccDate",
        "Summary",
    }

    missing_cad = cad_required - set(cad.columns)
    missing_tsb = tsb_required - set(tsb.columns)

    if missing_cad or missing_tsb:
        raise ValueError(
            f"Missing CADORS: {missing_cad}; "
            f"Missing TSB: {missing_tsb}"
        )


    date = pd.to_datetime(
        cad["occurrencedate"],
        errors="coerce",
        format="mixed",
    )

    in_range = date.between(
        "2018-01-01",
        "2025-12-31 23:59:59",
    )

    canada = (
        cad["country_enm"].eq("Canada")
        | cad["country_enm"].isna()
    )

    cad = cad.loc[
        in_range & canada,
        ["cadorsnumber", "tsboccurrencenumber"],
    ].copy()

    cad["cadorsnumber"] = normalize_ids(
        cad["cadorsnumber"]
    )

    cad["tsboccurrencenumber"] = normalize_ids(
        cad["tsboccurrencenumber"]
    )

    tsb["OccNo"] = normalize_ids(tsb["OccNo"])
    tsb["OccID"] = normalize_ids(tsb["OccID"])

    tsb["Summary"] = (
        tsb["Summary"]
        .fillna("")
        .astype("string")
        .str.strip()
    )

    tsb["OccDate"] = pd.to_datetime(
        tsb["OccDate"],
        errors="coerce",
        format="mixed",
    )

    tsb = tsb.loc[
        tsb["OccDate"].between(
            "2018-01-01",
            "2025-12-31 23:59:59",
        )
    ].copy()


    if (
        cad["cadorsnumber"].isna().any()
        or cad["cadorsnumber"].duplicated().any()
    ):
        raise ValueError(
            "Missing or duplicate CADORS IDs"
        )

    if (
        tsb["OccNo"].isna().any()
        or tsb["OccNo"].duplicated().any()
    ):
        raise ValueError(
            "Missing or duplicate TSB OccNo values"
        )

    

    tsb_reports = tsb.rename(
        columns={
            "OccNo": "tsb_occurrence_no",
            "Summary": "summary_text",
        }
    ).copy()

    tsb_reports["OccDate"] = (
        tsb_reports["OccDate"]
        .dt.strftime("%Y-%m-%d")
    )

    tsb_reports.to_csv(
        OUT / "tsb_reports.csv",
        index=False,
    )


    lookup = tsb[
        ["OccNo", "OccID"]
    ].rename(
        columns={
            "OccNo": "tsb_occurrence_no",
            "OccID": "tsb_occ_id",
        }
    )

    links = cad.merge(
        lookup,
        how="left",
        left_on="tsboccurrencenumber",
        right_on="tsb_occurrence_no",
        validate="many_to_one",
        indicator=True,
    )

    links["link_status"] = "matched"

    links.loc[
        links["tsboccurrencenumber"].isna(),
        "link_status",
    ] = "no_tsb_number"

    links.loc[
        links["tsboccurrencenumber"].notna()
        & links["_merge"].eq("left_only"),
        "link_status",
    ] = "tsb_number_unmatched"

    links = links.drop(columns=["_merge"])

    # Check that no CADORS occurrence was lost.
    if (
        len(links) != len(cad)
        or links["cadorsnumber"].duplicated().any()
    ):
        raise ValueError(
            "CADORS occurrence reconciliation failed"
        )

    links.to_csv(
        OUT / "occurrence_tsb_links.csv",
        index=False,
    )



    tags = []

    for theme, patterns in THEMES.items():

        regex = re.compile(
            "|".join(
                f"(?:{pattern})"
                for pattern in patterns
            ),
            re.IGNORECASE,
        )

        has_theme = (
            tsb_reports["summary_text"]
            .str.contains(regex, na=False)
        )

        matching_reports = tsb_reports.loc[
            has_theme,
            "tsb_occurrence_no",
        ]

        for occ_no in matching_reports:
            tags.append({
                "tsb_occurrence_no": occ_no,
                "theme": theme,
            })

    tag_df = pd.DataFrame(
        tags,
        columns=["tsb_occurrence_no", "theme"],
    ).drop_duplicates()

    tag_df.to_csv(
        OUT / "tsb_keyword_tags.csv",
        index=False,
    )



    theme_counts = (
        tag_df.groupby("theme")["tsb_occurrence_no"]
        .nunique()
        .reindex(THEMES, fill_value=0)
        .rename("report_count")
        .reset_index()
    )

    theme_counts.to_csv(
        OUT / "tsb_keyword_counts.csv",
        index=False,
    )


    unmatched = links.loc[
        links["link_status"].eq(
            "tsb_number_unmatched"
        ),
        ["cadorsnumber", "tsboccurrencenumber"],
    ]

    unmatched.to_csv(
        OUT / "unmatched_tsb_numbers.csv",
        index=False,
    )



    statuses = {
        str(k): int(v)
        for k, v in (
            links["link_status"]
            .value_counts()
            .items()
        )
    }

    report = {
        "valid_cadors_occurrences": int(len(cad)),
        "unique_tsb_reports": int(len(tsb_reports)),
        "link_status": statuses,
        "tagged_tsb_reports": int(
            tag_df["tsb_occurrence_no"].nunique()
        ),
        "theme_tags": int(len(tag_df)),
        "preserved_all_cadors": len(links) == len(cad),
        "unique_cadors_ids": (
            links["cadorsnumber"].is_unique
        ),
        "note": (
            "Keyword mentions are descriptive "
            "and do not establish causation."
        ),
    }

    with open(
        OUT / "integration_report.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(report, f, indent=4)



    print(
        f"CADORS occurrences: {len(cad):,}"
    )

    print(
        f"TSB reports: {len(tsb_reports):,}"
    )

    print("TSB link statuses:", statuses)

    print(
        "TSB reports with at least one theme:",
        f"{report['tagged_tsb_reports']:,}",
    )

    print(f"Output folder: {OUT}")

    print("\nSTEP 07 TSB INTEGRATION COMPLETE")


if __name__ == "__main__":
    main()
