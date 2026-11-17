# Government market data in MongoDB

Market searches query MongoDB only. No external government request code or API-key configuration remains.

## Connection

MongoDB must be running locally or accessible through your configured URI.

```powershell
$env:MONGODB_URI = 'mongodb://127.0.0.1:27017'
$env:MONGODB_DATABASE = 'crop_advisor'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Defaults are localhost port 27017, database crop_advisor. Collections: market_prices for quotes and market_imports for import history. For Atlas, put your connection URI in the environment variable; do not commit credentials.

## Import downloaded government data

Download CSV from the official resource:
https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi

The alternative variety-wise resource is:
https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity

Extract compressed downloads before importing:

```powershell
.\.venv\Scripts\python.exe scripts/import_market_data.py 'C:\path\to\government.csv' --resource-id 9ef84268-d588-465a-a308-a864a43d0070
```

Use resource ID 35985678-0d79-46b4-9ed6-6f13308a1d24 for the alternative resource. Resource IDs in filenames are recognized automatically; otherwise supply --resource-id to identify the correct source.

CSV is streamed in batches of 500. Required columns: State, District, Market, Commodity, Arrival_Date, Min_Price, Max_Price and Modal_Price. XML-encoded export headers (e.g. Min_x0020_Price) are supported. Variety and Grade are preserved. JSON records arrays, government JSON response files and JSON Lines also work; use CSV/JSON Lines for large imports because plain JSON loads in memory.

Rows are validated and invalid counts are recorded. Reimporting updates matching resource/location/market/commodity/variety/grade/date quotes. Other quotes remain unchanged. Completed batches persist if a later batch fails; rerunning safely upserts them. No API key or government connection is needed for import.

## Browse and refresh

Choose State → District → Commodity in Market prices. The browser includes all imported commodities, independently of model labels. Optional filters: reporting date, market and variety. Blank date selects the latest imported date for the selected filters.

Coverage cards show stored count, latest reporting date, age and last-record import time (IST). Reimporting old records changes import time, not reporting date. Reports include variety/grade/date and INR/quintal prices. Summaries cover displayed records (up to 1,000; chart up to 20), not a guaranteed market-wide average.

Open Data refresh & import history for the command and recent runs. After importing a newer file, click Refresh database coverage. A restart is unnecessary for newly imported records. Updates are manual; no background downloader or recurring task runs.

## Loaded snapshot

The supplied CSV imported successfully: 6,897 records dated 17 November 2026, 23 states, 234 districts and 155 commodities. Reimporting with tracking preserved the 6,897-document count. Examples: Cotton / Telangana / Siddipet, Tomato / Telangana / Siddipet, Apple / Tamil Nadu / Madurai. No Telangana Apple quotes are present.

History records filename (not full local path), method, resource ID, times, accepted/rejected counts, run status and coverage. Pre-tracking imports have no invented run entries. No credentials are stored.

Read-only FastAPI endpoints: /market/options, /market/prices, /market/status, /market/imports.

Example: /market/prices?state=Telangana&district=Siddipet&commodity=Tomato
