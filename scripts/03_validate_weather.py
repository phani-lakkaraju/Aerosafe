"""Validate full 2018-2025 coverage and consistency of the 13-airport output."""
import pandas as pd
from pandas.testing import assert_frame_equal
from weather_config import (AIRPORTS, CLEAN_DIR, REPORT_DIR, START_DATE, END_DATE,
                            EXPECTED_DATES, MEASUREMENT_COLUMNS, cleaned_path)

combined_file = CLEAN_DIR / 'weather_all_airports_2018-2025_clean.csv'
if not combined_file.exists():
    raise SystemExit('Missing combined cleaned weather CSV. Run 02_clean_weather.py first.')
combined = pd.read_csv(combined_file, parse_dates=['weather_date'], low_memory=False)
checks = []
for code, city in AIRPORTS.items():
    file = cleaned_path(code, city)
    if not file.exists():
        checks.append({'airport_code': code, 'passed': False, 'problem': 'Missing cleaned airport file'})
        print(f'{code}: FAIL — missing cleaned airport CSV')
        continue
    df = pd.read_csv(file, parse_dates=['weather_date'], low_memory=False)
    subset = combined.loc[combined.airport_code == code, df.columns].copy()
    dates = pd.DatetimeIndex(df['weather_date'])
    outside = int((~df.weather_date.between(START_DATE, END_DATE)).sum())
    duplicates = int(df.duplicated(['airport_code', 'weather_date']).sum())
    missing_days = len(EXPECTED_DATES.difference(dates))
    wrong_code = int(df.airport_code.ne(code).sum())
    identical = True
    try:
        assert_frame_equal(df.sort_values('weather_date').reset_index(drop=True),
                           subset.sort_values('weather_date').reset_index(drop=True),
                           check_dtype=False)
    except (AssertionError, ValueError, KeyError):
        identical = False
    valid = (len(df) == len(EXPECTED_DATES) and outside == 0 and duplicates == 0
             and missing_days == 0 and wrong_code == 0 and identical)
    checks.append({'airport_code': code, 'city': city, 'rows': len(df),
                   'start_date': str(df.weather_date.min().date()),
                   'end_date': str(df.weather_date.max().date()),
                   'out_of_range': outside, 'duplicate_dates': duplicates,
                   'missing_dates': missing_days, 'wrong_airport': wrong_code,
                   'matches_combined': identical,
                   'missing_measurements': int(df[MEASUREMENT_COLUMNS].isna().sum().sum()),
                   'passed': valid})
    print(f'{code}: {"PASS" if valid else "FAIL"} ({len(df):,} rows)')

REPORT_DIR.mkdir(parents=True, exist_ok=True)
pd.DataFrame(checks).to_csv(REPORT_DIR / 'weather_validation_summary.csv', index=False)
overall = (len(combined) == len(EXPECTED_DATES) * len(AIRPORTS)
           and not combined.duplicated(['airport_code', 'weather_date']).any()
           and combined.weather_date.between(START_DATE, END_DATE).all()
           and all(row['passed'] for row in checks))
print(f'OVERALL {"PASS" if overall else "FAIL"}: {len(combined):,} weather rows across {len(AIRPORTS)} airports')
if not overall:
    raise SystemExit(1)
