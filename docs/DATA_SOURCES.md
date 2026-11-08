# AeroSafe data sources and attribution

| Data | Source | Notes |
|---|---|---|
| CADORS occurrence, category, event, aircraft files | Transport Canada, Civil Aviation Daily Occurrence Reporting System (CADORS), open data | Raw files in `Data/Raw`, cleaned to 2018-2025 in `Data/Cleaned`. |
| Daily weather (13 airports) | Open-Meteo Historical Weather API, https://open-meteo.com | Licence: CC BY 4.0 (attribution required). Free for non-commercial use. |
| Airport coordinates | OurAirports, https://ourairports.com/data/ | Joined to CADORS on `aerodromeid` = OurAirports `ident`. |
| Occurrence summaries | Transportation Safety Board of Canada (TSB), Aviation Safety Information System occurrence data, https://www.tsb.gc.ca (Air > Data and statistics) | Reproduced for non-commercial, academic use (BSMM 8730, University of Windsor). Original data and narrative text belong to the TSB. Joined to CADORS on `tsboccurrencenumber` = TSB `OccNo`. |

Occurrence counts are raw counts of reported occurrences. They do not show cause, and
nothing in this repository should be read as a finding about fault or risk.
