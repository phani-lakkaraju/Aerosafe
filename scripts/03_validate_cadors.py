from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / 'data' / 'cleaned'
FILES = [
    'CADORS_Occurrence_Information_clean.csv',
    'CADORS_Occurrence_Category_clean.csv',
    'CADORS_Occurrence_Event_Information_clean.csv',
    'CADORS_Aircraft_Information_clean.csv',
    'CADORS_Aircraft_Event_Information_clean.csv',
]
START, END = pd.Timestamp('2018-01-01'), pd.Timestamp('2025-12-31')

def read(filename):
    path = CLEAN_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Cleaned file missing: {path}. Run 02_clean_cadors.py first.')
    return pd.read_csv(path, low_memory=False, dtype={'cadorsnumber': 'string'})

main = read(FILES[0])
if 'occurrencedate' not in main.columns:
    raise ValueError('Main occurrence file has no occurrencedate column')
dates = pd.to_datetime(main['occurrencedate'], errors='coerce')
invalid_dates = int((~(dates.dt.normalize().ge(START) & dates.dt.normalize().le(END))).sum())
valid_ids = set(main['cadorsnumber'].dropna())
issues = []
if invalid_dates:
    issues.append(f'Main table has {invalid_dates} missing/invalid/out-of-range dates')
if main['cadorsnumber'].isna().any():
    issues.append('Main table contains missing occurrence IDs')
print(f'Expected date range: 2018-01-01 through 2025-12-31')
print(f'Main table: {len(main):,} rows, {len(valid_ids):,} distinct occurrence IDs')
print(f'Earliest: {dates.min()} | Latest: {dates.max()}')
print(f'Invalid/out-of-range dates: {invalid_dates:,}')

for filename in FILES:
    df = main if filename == FILES[0] else read(filename)
    duplicates = int(df.duplicated().sum())
    missing = int(df.isna().sum().sum())
    missing_ids = int(df['cadorsnumber'].isna().sum())
    orphan_ids = set(df['cadorsnumber'].dropna()) - valid_ids
    print('\n' + '=' * 60)
    print(f'{filename}\nRows: {len(df):,} | Columns: {len(df.columns)}')
    print(f'Fully duplicate rows: {duplicates:,} | Missing cells: {missing:,}')
    print(f'Missing CADORS IDs: {missing_ids:,} | Unmatched CADORS IDs: {len(orphan_ids):,}')
    if missing_ids or orphan_ids:
        issues.append(f'{filename}: {missing_ids} missing IDs, {len(orphan_ids)} unmatched IDs')
    if filename == FILES[0]:
        duplicate_main_ids = int(df['cadorsnumber'].duplicated().sum())
        print(f'Duplicate occurrence IDs: {duplicate_main_ids:,}')
        if duplicate_main_ids:
            issues.append(f'Main table has {duplicate_main_ids} duplicate occurrence IDs')

print('\n' + '=' * 60)
if issues:
    print('VALIDATION FAILED:')
    for issue in issues:
        print(' - ' + issue)
    raise SystemExit(1)
print('VALIDATION PASSED: All retained occurrences are in 2018–2025 and child IDs match.')
print('Note: Missing non-key fields and fully duplicated rows are reported, not automatically deleted.')
