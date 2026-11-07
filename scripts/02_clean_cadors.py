from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw'
CLEAN_DIR = ROOT / 'data' / 'cleaned'
CLEAN_DIR.mkdir(parents=True, exist_ok=True)
START, END = pd.Timestamp('2018-01-01'), pd.Timestamp('2025-12-31')
FILES = [
    'CADORS_Occurrence_Information.csv',
    'CADORS_Occurrence_Category.csv',
    'CADORS_Occurrence_Event_Information.csv',
    'CADORS_Aircraft_Information.csv',
    'CADORS_Aircraft_Event_Information.csv',
]

def clean_column_name(name):
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(name))
    return re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_').lower()

def load_and_clean(filename):
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Missing raw file: {path}')
    df = pd.read_csv(path, encoding='utf-8-sig', low_memory=False, dtype={'cadorsnumber': 'string'})
    df.columns = [clean_column_name(c) for c in df.columns]
    for col in df.select_dtypes(include=['object', 'string']).columns:
        df[col] = df[col].astype('string').str.strip().replace('', pd.NA)
    for col in ('fatalities', 'injuries', 'aircraftyearbuilt'):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'aircraftnumber' in df.columns:
        nums = pd.to_numeric(df['aircraftnumber'], errors='coerce')
        if nums.dropna().mod(1).eq(0).all():
            df['aircraftnumber'] = nums.astype('Int64')
    return df

def save(df, filename, before):
    output = CLEAN_DIR / filename.replace('.csv', '_clean.csv')
    df.to_csv(output, index=False, date_format='%Y-%m-%d')
    print(f'{filename}: {before:,} -> {len(df):,} rows | saved {output}')

# The occurrence table is the only authoritative source of occurrence dates.
main = load_and_clean(FILES[0])
original_count = len(main)
original_dates = main['occurrencedate'].copy()
dates = pd.to_datetime(original_dates, errors='coerce', format='mixed')
print(f'Missing/unparseable occurrence dates: {dates.isna().sum():,}')
mask = dates.dt.normalize().ge(START) & dates.dt.normalize().le(END)
main = main.loc[mask].copy()
main['occurrencedate'] = dates.loc[mask]
valid_ids = set(main['cadorsnumber'].dropna())
if main['cadorsnumber'].isna().any():
    print(f'WARNING: {main["cadorsnumber"].isna().sum():,} retained occurrences have no CADORS ID.')
save(main, FILES[0], original_count)

# Child tables do not contain occurrence dates: filter by the selected IDs.
for filename in FILES[1:]:
    df = load_and_clean(filename)
    before = len(df)
    df = df.loc[df['cadorsnumber'].isin(valid_ids)].copy()
    save(df, filename, before)

print(f'CLEANING COMPLETED: 2018-01-01 through 2025-12-31 (inclusive).')
print(f'Retained {len(main):,} occurrences and {len(valid_ids):,} distinct occurrence IDs.')
