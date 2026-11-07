"""Shared settings and Open-Meteo CSV parsing for AeroSafe (2018-2025)."""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw'
CLEAN_DIR = ROOT / 'data' / 'cleaned'
REPORT_DIR = ROOT / 'data' / 'processed'
START_DATE = pd.Timestamp('2018-01-01')
END_DATE = pd.Timestamp('2025-12-31')
EXPECTED_DATES = pd.date_range(START_DATE, END_DATE, freq='D')

AIRPORTS = {
    'CYEG': 'Edmonton', 'CYHZ': 'Halifax', 'CYOW': 'Ottawa',
    'CYQB': 'QuebecCity', 'CYUL': 'Montreal', 'CYVR': 'Vancouver',
    'CYWG': 'Winnipeg', 'CYXY': 'Whitehorse', 'CYYC': 'Calgary',
    'CYYJ': 'Victoria', 'CYYT': 'StJohns', 'CYYZ': 'Toronto',
    'CYZF': 'Yellowknife',
}

COLUMN_MAP = {
    'time': 'weather_date',
    'weather_code (wmo code)': 'weather_code_wmo',
    'temperature_2m_max (°C)': 'temperature_max_c',
    'temperature_2m_min (°C)': 'temperature_min_c',
    'precipitation_sum (mm)': 'precipitation_mm',
    'rain_sum (mm)': 'rain_mm',
    'snowfall_sum (cm)': 'snowfall_cm',
    'wind_speed_10m_max (km/h)': 'wind_speed_max_kmh',
    'wind_gusts_10m_max (km/h)': 'wind_gusts_max_kmh',
    'wind_direction_10m_dominant (°)': 'wind_direction_deg',
}
MEASUREMENT_COLUMNS = [name for name in COLUMN_MAP.values() if name != 'weather_date']
NONNEGATIVE_COLUMNS = ['precipitation_mm', 'rain_mm', 'snowfall_cm',
                       'wind_speed_max_kmh', 'wind_gusts_max_kmh']

def read_open_meteo(path):
    """Read Open-Meteo CSV with two metadata lines and an empty line before header."""
    with Path(path).open('r', encoding='utf-8-sig') as fh:
        meta_keys = next(fh).strip().split(',')
        meta_values = next(fh).strip().split(',')
    metadata = dict(zip(meta_keys, meta_values))
    df = pd.read_csv(path, skiprows=3, encoding='utf-8-sig', low_memory=False)
    df.columns = df.columns.str.strip()
    return df, metadata

def find_source(code, city):
    """Choose the most complete in-range export, including Windows (1) downloads.

    Rejects old 2026-only files. Requires a full 2018-2025 calendar and all columns.
    Returns (path or None, dataframe or None, metadata, issues).
    """
    pattern = re.compile(rf'^weather_{re.escape(code)}_{re.escape(city)}_2010-2025(?:\(\d+\))?\.csv$', re.I)
    candidates = sorted(p for p in RAW_DIR.glob('*.csv') if pattern.fullmatch(p.name))
    issues = []
    eligible = []
    for path in candidates:
        try:
            df, meta = read_open_meteo(path)
            missing = sorted(set(COLUMN_MAP) - set(df.columns))
            if missing:
                issues.append(f'{path.name}: missing columns {missing}')
                continue
            dates = pd.to_datetime(df['time'], errors='coerce')
            selection = dates.between(START_DATE, END_DATE)
            selected_dates = dates[selection]
            if selected_dates.duplicated().any():
                issues.append(f'{path.name}: duplicate historical dates')
                continue
            missing_dates = len(EXPECTED_DATES.difference(pd.DatetimeIndex(selected_dates)))
            if missing_dates:
                issues.append(f'{path.name}: missing {missing_dates} dates within 2018-2025')
                continue
            if len(selected_dates) != len(EXPECTED_DATES):
                issues.append(f'{path.name}: unexpected historical row count')
                continue
            # Prefer latest named Windows download when multiple valid candidates exist.
            suffix = re.search(r'\((\d+)\)\.csv$', path.name)
            priority = int(suffix.group(1)) if suffix else 0
            eligible.append((priority, path, df, meta))
        except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
            issues.append(f'{path.name}: {exc}')
    if eligible:
        _, path, df, meta = max(eligible, key=lambda item: item[0])
        return path, df, meta, issues
    if not candidates:
        issues.append(f'No source file found for {code} {city}')
    return None, None, {}, issues

def cleaned_path(code, city):
    return CLEAN_DIR / f'weather_{code}_{city}_2018-2025_clean.csv'
