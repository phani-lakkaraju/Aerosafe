from pathlib import Path
import csv
import io
import json
import time
import urllib.parse
import urllib.request
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

AIRPORTS = {
    'CYWG': ('Winnipeg', 49.8844, -97.1478),
    'CYQB': ('QuebecCity', 46.7838, -71.3893),
    'CYYJ': ('Victoria', 48.6116, -123.3896),
    'CYYT': ('StJohns', 47.6274, -52.7842),
    'CYXY': ('Whitehorse', 60.7030, -135.1069),
    'CYZF': ('Yellowknife', 62.4628, -114.4403),
}
START = '2018-01-01'
END = '2025-12-31'
EXPECTED = (date.fromisoformat(END) - date.fromisoformat(START)).days + 1
DAILY = [
    'weather_code', 'temperature_2m_max', 'temperature_2m_min',
    'precipitation_sum', 'rain_sum', 'snowfall_sum',
    'wind_speed_10m_max', 'wind_gusts_10m_max', 'wind_direction_10m_dominant',
]
CSV_HEADERS = [
    'time', 'weather_code (wmo code)', 'temperature_2m_max (°C)',
    'temperature_2m_min (°C)', 'precipitation_sum (mm)', 'rain_sum (mm)',
    'snowfall_sum (cm)', 'wind_speed_10m_max (km/h)',
    'wind_gusts_10m_max (km/h)', 'wind_direction_10m_dominant (°)',
]
API = 'https://archive-api.open-meteo.com/v1/archive'

def fetch_airport(code, city, lat, lon):
    params = urllib.parse.urlencode({
        'latitude': lat, 'longitude': lon, 'start_date': START, 'end_date': END,
        'daily': ','.join(DAILY), 'timezone': 'auto', 'models': 'era5',
        'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh',
        'precipitation_unit': 'mm',
    })
    url = API + '?' + params
    print(f'\nDownloading {code} ({city})...')
    last_error = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'AeroSafe-academic-project/1.0'})
            with urllib.request.urlopen(req, timeout=180) as response:
                data = json.load(response)
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                print(f'  Attempt {attempt} failed ({exc}); retrying...')
                time.sleep(attempt * 3)
    else:
        raise RuntimeError(f'{code}: network/API failed after 3 attempts: {last_error}')

    daily = data.get('daily') or {}
    dates = daily.get('time') or []
    if len(dates) != EXPECTED or dates[0] != START or dates[-1] != END:
        raise ValueError(f'{code}: wrong date coverage: {len(dates)} rows, {dates[:1]}..{dates[-1:]}')
    if len(set(dates)) != EXPECTED:
        raise ValueError(f'{code}: duplicate dates')
    for key in DAILY:
        if key not in daily or len(daily[key]) != EXPECTED:
            raise ValueError(f'{code}: missing or malformed variable: {key}')

    # Preserve the original Open-Meteo CSV structure used by weather_config.read_source:
    # first line metadata names; second line values; blank; fourth line daily header.
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['latitude', 'longitude', 'elevation', 'utc_offset_seconds', 'timezone', 'timezone_abbreviation'])
    writer.writerow([data.get('latitude', lat), data.get('longitude', lon), data.get('elevation', ''),
                     data.get('utc_offset_seconds', ''), data.get('timezone', ''),
                     data.get('timezone_abbreviation', '')])
    writer.writerow([])
    writer.writerow(CSV_HEADERS)
    for i, d in enumerate(dates):
        writer.writerow([d] + [daily[key][i] if daily[key][i] is not None else '' for key in DAILY])

    # Existing pipeline expects this legacy filename even though dates are 2018–2025.
    filename = f'weather_{code}_{city}_2010-2025.csv'
    output = RAW / filename
    tmp = output.with_suffix('.csv.tmp')
    tmp.write_text(buffer.getvalue(), encoding='utf-8', newline='')
    tmp.replace(output)
    print(f'  Saved {EXPECTED:,} days: {output}')
    print(f'  Historical timezone: {data.get("timezone")} | model: ERA5')
    return output

def main():
    print(f'Open-Meteo ERA5 daily weather; {START} through {END} inclusive')
    print(f'Output folder: {RAW}')
    successes, errors = [], []
    for code, (city, lat, lon) in AIRPORTS.items():
        try:
            successes.append(fetch_airport(code, city, lat, lon))
        except Exception as exc:
            errors.append((code, str(exc)))
            print(f'  ERROR: {exc}')
    print(f'\nDone: {len(successes)}/6 files downloaded and checked.')
    for code, message in errors:
        print(f'  FAILED {code}: {message}')
    if errors:
        raise SystemExit(1)
    print('Next: python scripts/01_profile_weather.py')
    print('      python scripts/02_clean_weather.py')
    print('      python scripts/03_validate_weather.py')

if __name__ == '__main__':
    main()
