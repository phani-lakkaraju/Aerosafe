from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw'
REPORT_DIR = ROOT / 'data' / 'processed'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
START, END = pd.Timestamp('2018-01-01'), pd.Timestamp('2025-12-31')
FILES = [
    'CADORS_Occurrence_Information.csv',
    'CADORS_Occurrence_Category.csv',
    'CADORS_Occurrence_Event_Information.csv',
    'CADORS_Aircraft_Information.csv',
    'CADORS_Aircraft_Event_Information.csv',
]
KEYS = {
    FILES[0]: ['cadorsnumber'],
    FILES[1]: ['cadorsnumber', 'occurrence_category_etxt'],
    FILES[2]: ['cadorsnumber', 'event_name_enm'],
    FILES[3]: ['cadorsnumber', 'aircraftnumber'],
    FILES[4]: ['cadorsnumber', 'aircraftnumber', 'event_seq_num'],
}

def load_csv(filename):
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Missing raw file: {path}')
    return pd.read_csv(path, encoding='utf-8-sig', low_memory=False, dtype={'cadorsnumber': 'string'})

main = load_csv(FILES[0])
dates = pd.to_datetime(main['occurrencedate'], errors='coerce', format='mixed')
valid = dates.dt.normalize().ge(START) & dates.dt.normalize().le(END)
valid_ids = set(main.loc[valid, 'cadorsnumber'].dropna())
print(f'Occurrence records in 2018–2025: {valid.sum():,}; distinct IDs: {len(valid_ids):,}')
print(f'Unparseable/missing source dates: {dates.isna().sum():,}')

summary, missing_reports, empty_reports, duplicate_reports, dtype_reports = [], [], [], [], []
for filename in FILES:
    df = main.loc[valid].copy() if filename == FILES[0] else load_csv(filename).loc[lambda x: x['cadorsnumber'].isin(valid_ids)].copy()
    missing = df.isna().sum()
    empty = df.select_dtypes(include=['object', 'string']).apply(lambda s: s.astype('string').str.strip().eq('').sum())
    key_cols = KEYS[filename]
    dup_keys = df.duplicated(subset=key_cols, keep=False).sum()
    summary.append(dict(file=filename, rows=len(df), columns=len(df.columns), missing_cells=int(missing.sum()),
                        fully_duplicate_rows=int(df.duplicated().sum()), empty_string_cells=int(empty.sum()),
                        duplicate_key_rows=int(dup_keys), key_columns=', '.join(key_cols)))
    for col in df.columns:
        if missing[col]:
            missing_reports.append(dict(file=filename, column=col, missing_count=int(missing[col]),
                                        missing_percent=round(100 * missing[col] / len(df), 2) if len(df) else 0))
        if col in empty.index and empty[col]:
            empty_reports.append(dict(file=filename, column=col, empty_string_count=int(empty[col])))
        dtype_reports.append(dict(file=filename, column=col, data_type=str(df[col].dtype)))
    duplicate_reports.append(dict(file=filename, duplicate_key_rows=int(dup_keys), key_columns=', '.join(key_cols)))
    print(f'{filename}: {len(df):,} rows, {dup_keys:,} duplicate-key rows')

for name, rows, cols in [
    ('cadors_quality_summary.csv', summary, ['file', 'rows', 'columns', 'missing_cells', 'fully_duplicate_rows', 'empty_string_cells', 'duplicate_key_rows', 'key_columns']),
    ('cadors_missing_values.csv', missing_reports, ['file', 'column', 'missing_count', 'missing_percent']),
    ('cadors_empty_strings.csv', empty_reports, ['file', 'column', 'empty_string_count']),
    ('cadors_duplicate_keys.csv', duplicate_reports, ['file', 'duplicate_key_rows', 'key_columns']),
    ('cadors_data_types.csv', dtype_reports, ['file', 'column', 'data_type']),
]:
    pd.DataFrame(rows, columns=cols).to_csv(REPORT_DIR / name, index=False)
print(f'2018–2025 profiling completed. Reports: {REPORT_DIR}')
