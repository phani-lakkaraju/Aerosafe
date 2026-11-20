from pathlib import Path
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from weather_data_download_api import fetch_airport
from weather_config import find_source

AIRPORTS = {
    "CYEG": "Edmonton",
    "CYHZ": "Halifax",
    "CYVR": "Vancouver",
    "CYYC": "Calgary",
}

for code, city in AIRPORTS.items():
    path, df, metadata, issues = find_source(code, city)

    if path is None:
        raise FileNotFoundError(
            f"Original weather source not found: {code}"
        )

    lat = float(metadata["latitude"])
    lon = float(metadata["longitude"])

    # Back up original source before downloading.
    backup = path.with_name(
        path.stem + "_before_timezone_fix.bak"
    )
    shutil.copy2(path, backup)

    print(f"\nCorrecting {code} - {city}")

    # Existing fetch_airport uses timezone='auto'.
    new_file = fetch_airport(
        code, city, lat, lon
    )

    # Give this corrected source the highest selection
    # priority in the existing weather_config logic.
    preferred = new_file.with_name(
        f"weather_{code}_{city}_2010-2025(99).csv"
    )

    new_file.replace(preferred)

    # Check returned source timezone.
    _, _, new_meta, _ = find_source(code, city)
    print("Selected timezone:", new_meta.get("timezone"))

print("\nFOUR AIRPORT DOWNLOADS COMPLETED")
