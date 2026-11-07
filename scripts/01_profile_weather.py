"""Profile the best historical file for each of the 13 airports (no cleaning yet)."""
import pandas as pd
from weather_config import AIRPORTS, REPORT_DIR, START_DATE, END_DATE, find_source

REPORT_DIR.mkdir(parents=True, exist_ok=True)
summary, missing_rows, metadata_rows = [], [], []
for code, city in AIRPORTS.items():
    path, df, metadata, issues = find_source(code, city)
    if path is None:
        summary.append({'airport_code': code, 'city': city, 'status': 'SOURCE_NOT_READY',
                        'source_file': '', 'issues': ' | '.join(issues)})
        print(f'{code}: SOURCE_NOT_READY: {issues}')
        continue
    dates = pd.to_datetime(df['time'], errors='coerce')
    in_range = dates.between(START_DATE, END_DATE)
    selection = df.loc[in_range]
    summary.append({'airport_code': code, 'city': city, 'status': 'READY',
                    'source_file': path.name, 'raw_rows': len(df),
                    'rows_2018_2025': len(selection),
                    'first_date': dates.min().date(), 'last_date': dates.max().date(),
                    'invalid_source_dates': int(dates.isna().sum()),
                    'missing_measurements_2018_2025': int(selection.isna().sum().sum()),
                    'other_candidate_issues': ' | '.join(issues)})
    missing_rows.extend({'airport_code': code, 'column': col, 'missing': int(count)}
                        for col, count in selection.isna().sum().items())
    metadata_rows.append({'airport_code': code, 'source_file': path.name, **metadata})
    print(f'{code}: READY ({len(selection):,} historical days) using {path.name}')

pd.DataFrame(summary).to_csv(REPORT_DIR / 'weather_raw_profile.csv', index=False)
pd.DataFrame(missing_rows, columns=['airport_code', 'column', 'missing']).to_csv(
    REPORT_DIR / 'weather_raw_missing_values.csv', index=False)
pd.DataFrame(metadata_rows).to_csv(REPORT_DIR / 'weather_source_metadata.csv', index=False)
print('Profiling reports saved to', REPORT_DIR)
