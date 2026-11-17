# Verification

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
