
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
RAW = ROOT / 'data' / 'raw'
CLEAN = ROOT / 'data' / 'cleaned'
PROCESSED = ROOT / 'data' / 'processed'


def main():
    if not RAW.is_dir():
        raise SystemExit(f'Missing raw data folder: {RAW}')
    CLEAN.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    # Clean only outputs of the WEATHER pipeline: never remove CADORS or input files.
    old_outputs = list(CLEAN.glob('weather_*_2018-2025_clean.csv'))
    old_reports = list(PROCESSED.glob('weather_*.csv'))
    print(f'Removing {len(old_outputs)} old weather output(s) and {len(old_reports)} weather report(s).', flush=True)
    for path in old_outputs + old_reports:
        path.unlink()
    for name in ('01_profile_weather.py', '02_clean_weather.py', '03_validate_weather.py'):
        print(f'\n===== Running {name} =====', flush=True)
        subprocess.run([sys.executable, str(SCRIPTS / name)], cwd=ROOT, check=True)
    print('\nSUCCESS — all 13 airport weather files cleaned and validated.', flush=True)
    print(f'Combined weather CSV: {CLEAN / "weather_all_airports_2018-2025_clean.csv"}')


if __name__ == '__main__':
    main()
