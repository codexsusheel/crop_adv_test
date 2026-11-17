# Verification

## External government API removal

Removed the outbound market adapter, government HTTP sync and diagnostic scripts, their specific tests and the legacy /market/{crop} route. Market browsing now uses /market/prices and MongoDB only. CSV/JSON imports, source-attribution links, the classifier and FastAPI frontend endpoints remain. The original delivery ZIP is unchanged; the entries below are historical verification records, not descriptions of currently available external integrations.

## Market browser improvements (17 November 2026)

- 23 tests passed, including real MongoDB integration checks for dependent options, date filters, import-history success/failure states and repeat-import idempotence. Source-checked regional fertilizer references reject mismatched crops/states and withhold rates without unit/condition confirmation.
- Browser verified: State Telangana → District Siddipet → Commodity Tomato (outside classifier labels) → Find prices returned Vantamamidi APMC, Local grade, 17/11/2026, INR 2,000/quintal minimum/modal/maximum. Browser screenshot capture timed out; accessibility inspection verified the selectors and rendered report.
- Reimported existing official CSV with tracking: 6,897 accepted, zero rejected, 6,897 documents remain. A real completed run is stored in market_imports; no prior history fabricated.
- Both frontend scripts passed Node syntax checks. No training data or classifier artifact changed, no ZIP regenerated.

## Government CSV import completed (17 November 2026)

- Imported the user-downloaded `9ef84268-d588-465a-a308-a864a43d0070.csv` into local `crop_advisor.market_prices`.
- 6,897 source rows accepted, zero invalid; 6,897 documents stored. All reporting dates are 2026-11-17. No model-training files changed.
- Added XML-encoded CSV header support and preserved the original government source ID/URL.
- Apple / Tamil Nadu / Madurai lookup returned four quotes in about 3.4 ms (one measurement, not a latency guarantee).
- Telangana has 88 records in this snapshot, with no Apple quotes. Maize / Telangana / Adilabad is an available example.
- 20 tests passed, including live MongoDB integration tests. Only the disposable test collection was removed; real production records remain stored.

## Initial MongoDB setup (before CSV import)

- Local MongoDB ping succeeded on 127.0.0.1:27017.
- 19 tests passed, including live local MongoDB integration checks in a uniquely named disposable test collection. Only that test collection was removed afterwards.
- Verified repeat-import upserts, corrected prices, latest reporting date selection and explicit date filtering. Database reads do not call the government API, including on database failures.
- JavaScript syntax and Python compilation checks passed.
- The first bounded government API import returned an HTTP error. The production market_prices collection remains empty; no real dataset has been claimed loaded.
- CSV/JSON/JSON Lines importer and bounded government API sync are included. Initial loading still requires a valid government export or successful sync.

## Original delivery

Completed 16 November 2026.

- Executed every code cell of the supplied notebook against only the supplied CSV.
- Reproduced Random Forest selection, isotonic calibration and 0.75 confidence threshold.
- Final calibrated test macro-F1: 0.9909 (440 test rows). See metrics.json for exact class-wise results.
- Original notebook round-trip serialization checks passed.
- 12 unittest tests passed in 10.897 seconds: typical input, repeatability, out-of-range abstention, unusual combinations, malformed/missing/extra inputs, report routes, land/what-if/sweep routes, profit units, fertilizer nitrogen accounting, rotation, missing API key, mocked upstream filtering/cache and provider error handling.
- Python compilation and JavaScript syntax checks passed.
- Browser check: page loaded; sample-input button populated the form; submitting returned rice with 100% model confidence and 100% stability; assessment and explanation rendered legibly.
- No authenticated live government API test: no key supplied; unauthenticated connection timed out. Market success tests use clearly synthetic mock responses only, never displayed as real market data.
- Postman and Kaggle hosting were not executed. README explains how to use both.

The guide's broader fertilizer advice, validated agronomic reference tables, state/season modelling and yield prediction cannot be substantiated from the supplied seven-feature CSV. These boundaries are explicit in the interface and README.
