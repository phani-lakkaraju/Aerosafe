"""Stage 04: profile and clean the TSB ASIS occurrence table (narrative text source).

Usage:
    python scripts/04_profile_tsb_asis.py <ASISdb_MDOTW_VW_OCCURRENCE_PUBLIC.csv>

Reads the TSB occurrence table, keeps 2018-2025, removes duplicate rows (one row per OccID),
checks how many CADORS occurrences can be linked through the TSB occurrence number
(OccNo = tsboccurrencenumber), converts the unsigned TSB coordinates to signed ones
(longitude west of Greenwich becomes negative) and writes:
    Data/Cleaned/TSB_ASIS_Occurrence_2018-2025_clean.csv
    Data/processed/tsb_asis_summary.csv
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / 'Data' / 'Cleaned'
REPORT_DIR = ROOT / 'Data' / 'processed'
CADORS_CLEAN = CLEAN_DIR / 'CADORS_Occurrence_Information_clean.csv'
START, END = pd.Timestamp('2018-01-01'), pd.Timestamp('2025-12-31')
KEEP = ['OccID', 'OccNo', 'OccDate', 'OccClassID_DisplayEng', 'CountryID_DisplayEng',
        'ProvinceID_DisplayEng', 'Location', 'ICAO', 'Latitude', 'LatEnum_DisplayEng',
        'Longitude', 'LongEnum_DisplayEng', 'Summary']

def read(path):
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding='latin-1', low_memory=False)
    # The TSB files start with a stray byte-order-mark text ("77u/") in the first header.
    df.columns = [str(c).replace('77u/', '').replace('\ufeff', '').strip() for c in df.columns]
    return df

def main(asis_path):
    raw = read(asis_path)
    raw['OccDate'] = pd.to_datetime(raw['OccDate'], errors='coerce')
    in_range = raw[raw['OccDate'].between(START, END)]
    keep = [c for c in KEEP if c in in_range.columns]
    clean = in_range[keep].drop_duplicates(subset='OccID').copy()
    clean['Summary'] = clean['Summary'].astype('string').str.strip()
    # TSB stores coordinates unsigned with a separate N/S and E/W column: make them signed.
    clean['latitude_signed'] = clean['Latitude'].where(clean['LatEnum_DisplayEng'] != 'S', -clean['Latitude'])
    clean['longitude_signed'] = clean['Longitude'].where(clean['LongEnum_DisplayEng'] != 'W', -clean['Longitude'])
    clean['OccDate'] = clean['OccDate'].dt.strftime('%Y-%m-%d')
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(CLEAN_DIR / 'TSB_ASIS_Occurrence_2018-2025_clean.csv', index=False)

    cad = pd.read_csv(CADORS_CLEAN, low_memory=False, usecols=['cadorsnumber', 'country_enm', 'tsboccurrencenumber'])
    cad = cad[(cad['country_enm'] == 'Canada') | cad['country_enm'].isna()]
    with_tsb = cad[cad['tsboccurrencenumber'].notna()]
    linked = with_tsb['tsboccurrencenumber'].isin(set(clean['OccNo']))
    summary = pd.DataFrame([
        ('asis_rows_total', len(raw)),
        ('asis_rows_2018_2025', len(in_range)),
        ('asis_unique_occurrences_2018_2025', len(clean)),
        ('asis_duplicate_rows_removed', len(in_range) - len(clean)),
        ('asis_with_summary_text', int(clean['Summary'].notna().sum())),
        ('cadors_canada_or_blank_country', len(cad)),
        ('cadors_with_tsb_number', len(with_tsb)),
        ('cadors_linked_to_asis_summary', int(linked.sum())),
        ('cadors_tsb_number_not_in_asis', int((~linked).sum())),
        ('share_of_cadors_linked_pct', round(100 * linked.sum() / len(cad), 1)),
    ], columns=['metric', 'value'])
    summary.to_csv(REPORT_DIR / 'tsb_asis_summary.csv', index=False)
    print(summary.to_string(index=False))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
