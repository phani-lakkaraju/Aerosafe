"""Stage 05: rank airports by CADORS occurrence count and show weather coverage.

Usage:
    python scripts/05_rank_airports.py

Counts distinct cadorsnumber per aerodrome (2018-2025, Canada or blank country) from the
cleaned CADORS occurrence table and marks the airports that have daily weather files.
Writes Data/processed/airport_occurrence_ranking.csv.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / 'Data' / 'Cleaned'
REPORT_DIR = ROOT / 'Data' / 'processed'
WEATHER_AIRPORTS = ['CYEG', 'CYHZ', 'CYOW', 'CYQB', 'CYUL', 'CYVR', 'CYWG', 'CYXY', 'CYYC', 'CYYJ', 'CYYT', 'CYYZ', 'CYZF']

def main():
    occ = pd.read_csv(CLEAN_DIR / 'CADORS_Occurrence_Information_clean.csv', low_memory=False,
                      usecols=['cadorsnumber', 'country_enm', 'aerodromeid'])
    occ = occ[(occ['country_enm'] == 'Canada') | occ['country_enm'].isna()].drop_duplicates('cadorsnumber')
    total = len(occ)
    counts = occ['aerodromeid'].value_counts().rename_axis('airport_code').reset_index(name='occurrences')
    counts['rank'] = counts.index + 1
    counts['share_pct'] = (100 * counts['occurrences'] / total).round(2)
    counts['has_weather'] = counts['airport_code'].isin(WEATHER_AIRPORTS)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    counts.to_csv(REPORT_DIR / 'airport_occurrence_ranking.csv', index=False)
    covered = counts.loc[counts['has_weather'], 'occurrences'].sum()
    print(f'Valid occurrences: {total:,}; without airport code: {occ["aerodromeid"].isna().sum():,}')
    print(f'Occurrences at the {len(WEATHER_AIRPORTS)} weather airports: {covered:,} ({100 * covered / total:.1f}%)')
    print(counts.head(15).to_string(index=False))

if __name__ == '__main__':
    main()
