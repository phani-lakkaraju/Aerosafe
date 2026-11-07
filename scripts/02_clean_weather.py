import pandas as pd
from weather_config import (AIRPORTS, CLEAN_DIR, REPORT_DIR, START_DATE, END_DATE,
                            COLUMN_MAP, MEASUREMENT_COLUMNS, NONNEGATIVE_COLUMNS,
                            EXPECTED_DATES, find_source, cleaned_path)

CLEAN_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
reports = []
frames = []
# Remove old outputs to avoid mixing data from previous runs.
for old in CLEAN_DIR.glob('weather_*_2018-2025_clean.csv'):
    old.unlink()

for code, city in AIRPORTS.items():
    path, source, metadata, issues = find_source(code, city)
    if path is None:
        reports.append({'airport_code': code, 'city': city, 'status': 'SOURCE_NOT_READY',
                        'details': ' | '.join(issues)})
        print(f'{code}: cannot clean: {issues}')
        continue
    df = source.rename(columns=COLUMN_MAP).copy()
    df['weather_date'] = pd.to_datetime(df['weather_date'], errors='coerce')
    df = df.loc[df['weather_date'].between(START_DATE, END_DATE)].copy()
    invalid_numeric = 0
    invalid_ranges = 0
    for col in MEASUREMENT_COLUMNS:
        existing = df[col].notna()
        df[col] = pd.to_numeric(df[col], errors='coerce')
        invalid_numeric += int((existing & df[col].isna()).sum())
    for col in NONNEGATIVE_COLUMNS:
        bad = df[col].notna() & (df[col] < 0)
        invalid_ranges += int(bad.sum())
        df.loc[bad, col] = float('nan')
    for col, lo, hi in [('weather_code_wmo', 0, 99), ('wind_direction_deg', 0, 360)]:
        bad = df[col].notna() & ~df[col].between(lo, hi)
        invalid_ranges += int(bad.sum())
        df.loc[bad, col] = float('nan')
    bad_temp = (df['temperature_min_c'].notna() & df['temperature_max_c'].notna() &
                (df['temperature_max_c'] < df['temperature_min_c']))
    if bad_temp.any():
        reports.append({'airport_code': code, 'city': city, 'source_file': path.name,
                        'status': 'INVALID_TEMPERATURE', 'details': f'{int(bad_temp.sum())} days'})
        print(f'{code}: inconsistent temperatures; excluded')
        continue
    df['weather_code_wmo'] = df['weather_code_wmo'].astype('Int64')
    df.insert(0, 'airport_code', code)
    df.insert(1, 'city', city)
    df = df[['airport_code', 'city', *COLUMN_MAP.values()]]
    df = df.sort_values('weather_date').reset_index(drop=True)
    df.to_csv(cleaned_path(code, city), index=False, date_format='%Y-%m-%d')
    frames.append(df)
    reports.append({'airport_code': code, 'city': city, 'source_file': path.name,
                    'source_rows': len(source), 'cleaned_rows': len(df),
                    'start_date': str(df.weather_date.min().date()),
                    'end_date': str(df.weather_date.max().date()),
                    'invalid_numeric_cells': invalid_numeric,
                    'invalid_range_cells': invalid_ranges,
                    'missing_measurement_cells': int(df[MEASUREMENT_COLUMNS].isna().sum().sum()),
                    'status': 'CLEANED'})
    print(f'{code}: saved {len(df):,} days from {path.name}')

pd.DataFrame(reports).to_csv(REPORT_DIR / 'weather_cleaning_summary.csv', index=False)
if len(frames) != len(AIRPORTS):
    raise SystemExit(f'Cleaned {len(frames)} / {len(AIRPORTS)} airports. See weather_cleaning_summary.csv.')
combined = pd.concat(frames, ignore_index=True).sort_values(['airport_code', 'weather_date'])
combined.to_csv(CLEAN_DIR / 'weather_all_airports_2018-2025_clean.csv',
                index=False, date_format='%Y-%m-%d')
print(f'DONE: {len(frames)} airports, {len(combined):,} rows, {len(EXPECTED_DATES)} days each.')
