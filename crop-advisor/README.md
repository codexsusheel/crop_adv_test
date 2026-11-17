# Crop Advisor

A local FastAPI application with a plain HTML, CSS and JavaScript frontend, built exclusively from your `Crop_recommendation.csv` and `model_train_v2.ipynb`.

## Updates: 17 November 2026

Prediction reports now show the underlying Random Forest support scores separately from calibrated confidence. Isotonic calibration can legitimately return exactly 0 or 1; neither the original model nor its calibrated output is altered. Forest scores come from the estimators already stored inside the calibrated model and are not calibrated probabilities. API fields: `forest_candidates` (top five by forest support), `top_candidates` (top three calibrated probabilities, now unrounded). Both lists are withheld for out-of-range inputs.

Reports use summary cards, compact tables and expandable technical explanations rather than recursive object displays.

The old fertilizer converter has been removed. `POST /fertilizer` now accepts `{"crop":"rice","inputs":{"N":90,"P":42,"K":43,"temperature":20.9,"humidity":82,"ph":6.5,"rainfall":203},"measurement_basis":"csv_scale"}`. It compares nutrients with the selected crop's training percentiles, flags lower values for soil-test review, and suggests nutrient sources conditionally. It does not diagnose a deficiency from CSV-scale inputs or calculate an application dose.

Optional `confirmed_available_kg_ha` mode uses the [TNAU soil rating chart](https://agritech.tnau.ac.in/agriculture/agri_soil_soilratingchart.html): available elemental N 240–480, P 11–22, K 110–280 kg/ha are rated medium. This requires compatible laboratory units/methods; do not use ppm or oxide units. Lower values trigger source suggestions; medium/high readings do not automatically trigger extra fertilizer. pH flags prompt amendment testing. The mode is independent of the model's training bounds, since laboratory soil readings may exceed the CSV scale.

Restart uvicorn and hard-refresh the browser after updating. The ZIP from the original delivery is unchanged; test these changes from this project directory.

## Run on Windows

Use Python 3.11–3.13 (tested with Python 3.13). Open PowerShell in this extracted folder:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# Optional: enable the live market service with your data.gov.in account key.
$env:DATA_GOV_API_KEY = 'your-key-here'
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the UI and http://127.0.0.1:8000/docs for interactive HTTP documentation. Leave the terminal running. No Node, React, build tool or frontend framework is needed. Fonts fall back to local system fonts offline.

The ZIP includes reproduced trained artifacts; training is not required to start. Only load trusted pickle/joblib artifacts. Keep the pinned scikit-learn version when loading them.

## Model provenance

- Only the supplied CSV: 2,200 rows, 22 crops and seven numeric features.
- The original notebook is included unchanged. `scripts/build_model.py` executes its code cells with a project-directory override, saves plots and exports reports.
- The notebook compares its original five classifiers and selects its 300-tree Random Forest, then chooses calibration by training-fold log loss. It preserves the 80/20 stratified split, random seed 42, calibrated confidence threshold and class-specific Mahalanobis detector.
- The older, incompatible 200-tree saved model in the original folder is not used.
- Notebook stored outputs were produced with scikit-learn 1.9.1. This reproduction uses installed 1.7.2; `reports/metrics.json` and exported metadata describe this run. Stored notebook outputs are historical, not the current report.
- `backend/notebook_policy.py` is extracted directly from the notebook. The API adds the PDF's margin check and 40-trial stability check. It retains the notebook's learned confidence cutoff and 98th-percentile anomaly cutoff rather than substituting the PDF's 0.50/99th-percentile defaults.
- OUT_OF_RANGE suppresses crops and alternatives. LOW_CONFIDENCE offers a shortlist, not an unconditional recommendation. Valid input is not a promise of agronomic suitability.

Rebuild and test:

```powershell
.venv\Scripts\python scripts/build_model.py
.venv\Scripts\python -m unittest discover -s tests -v
```

Rebuilding takes several minutes because it repeats the notebook's full cross-validation and nested calibration. Original input files outside this project are never modified.

## Selected government API

Official resource: https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity

Endpoint: `https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24`

Parameters: `api-key`, `format=json`, `filters[State]`, `filters[Commodity]`, `filters[District]`, `filters[Arrival_Date]` (dd-MM-yyyy), `limit=100`, `offset=0`. Capitalization matters for this resource. State and district are required by our endpoint; date defaults to today's India calendar date. The UI exposes a date picker. Local endpoint example: `/market/apple?state=Telangana&district=Hyderabad&date=2026-11-16`.

The supplied government HTTP 200 response contains capitalized record fields and historical 2009 rows when unfiltered. The adapter normalizes field names to lowercase and only accepts the requested date and location; an old quote cannot silently become today's price. Cache keys include reporting date. A new authenticated filtered request timed out during development; provider-side date filtering remains unverified live. Offline tests verify the expected filter parameters and reject wrong-date records.

This AGMARKNET/DMI resource supplies state, district, market, commodity, variety, reporting date and minimum/modal/maximum wholesale prices. Register at data.gov.in to obtain your own key. The key stays in a server environment variable. Never put it in frontend JavaScript or commit it.

The adapter returns up to 100 quotes (not an all-markets average), with source dates and variety. It does not convert paddy into rice, raw cotton into lint, or pulses into processed dal. For ambiguous crop names, supply an exact market commodity name. The six-hour process-local cache avoids repeated calls; restart clears it. Missing keys, missing quotes and provider failures remain explicit. No fabricated MSP/reference fallback is supplied. Current mandi prices are not future harvest prices.

Live authenticated responses could not be verified during development: no user API key was supplied and an unauthenticated connection attempt timed out. Offline contract tests exercise successful responses, filtering, caching and errors. Confirm the resource's current API schema with your key before relying on live quotes.

## How the PDF is adapted

| Feature | Implementation / constraint |
|---|---|
| Predict with uncertainty | Same trained model; validation, abstention, top three, entropy, margin, stability |
| State selection | Market filter only. Training CSV has no state labels |
| Season, soil type, salinity, organic carbon | Not trained inputs; not fabricated or passed to the model |
| Ideal conditions | Training-split percentiles, explicitly not agronomic thresholds |
| Land checker | Per-feature percentile fit and requested-crop probability, with full uncertainty assessment |
| Duration, yield, costs | User assumptions in calculator; no invented reference table |
| Market prices | Live government adapter, six-hour cache, explicit unavailable state |
| Fertilizer | Soil-based nutrient screening and conditional product-source suggestions for a selected crop |
| Fertilizer scheduling / soil low-medium-high | Not inferred: soil nutrient units and local agronomic guidance are missing |
| Sponsors | No brands or endorsements included |
| What-if / sweep | Set/add/percentage changes, probability deltas and sampled tipping intervals |
| Profit | Low/typical/high yield scenarios, break-even values, area and duration scaling |
| Rotation | Broad legume/non-legume hint; no unverified local season/family/heavy-feeder claims |
| Explanation | Local median-replacement sensitivity, not causal attribution or SHAP |
| Evaluation | Original model comparison plus final class-wise metrics, matrix and perturbation tests |
| Wrong state/season/soil tests | Inapplicable: these are not model inputs; extra prediction fields are rejected |
| Kaggle | Optional instructions below; local app is the tested delivery |

The guide's 12-class dataset, seven-classifier requirement and 72% results belong to a different experiment and are not substituted into your project. Wheat and other absent labels cannot be predicted by the supplied model.

## API examples

`POST /predict` accepts exactly:

```json
{"N":90,"P":42,"K":43,"temperature":20.9,"humidity":82,"ph":6.5,"rainfall":203}
```

`POST /what-if`:

```json
{"inputs":{"N":90,"P":42,"K":43,"temperature":20.9,"humidity":82,"ph":6.5,"rainfall":203},"feature":"rainfall","operation":"set","value":350}
```

Every endpoint and validation rule is available in `/docs` and `/openapi.json`. Import `/openapi.json` into Postman as a collection/API definition, set the base URL to `http://127.0.0.1:8000`, and use the examples above. The automated tests use FastAPI's TestClient; no claim is made that Postman itself was run.

GET routes: `/meta`, `/states`, `/crops`, `/crops/{crop}`, `/market/{crop}?state=Punjab&district=Amritsar`, `/metrics`, `/metrics/classwise`, `/metrics/confusion-matrix`, `/metrics/robustness`, `/metrics/decision-rules`, `/plots/*.png`.

POST routes: `/predict`, `/land-check`, `/what-if`, `/what-if/sweep`, `/profit`, `/fertilizer`, `/rotation`.

## Files to read first

- `backend/main.py`: small request models, input policy wrapper and planning calculations.
- `backend/market.py`: government API integration and cache.
- `backend/notebook_policy.py`: original notebook validation and recommendation logic.
- `frontend/app.js`: forms, HTTP requests and safe DOM rendering.
- `scripts/build_model.py`: reproducible model/report generation.
- `tests/`: boundary, uncertainty, arithmetic and adapter tests.
- `reports/`: measured results and plots.

## Optional Kaggle use

Upload this project as a private Kaggle Dataset, copy it from the read-only input directory to `/kaggle/working/crop-advisor`, install the pinned requirements, and run uvicorn from that folder. Set `DATA_GOV_API_KEY` from Kaggle Secrets, never in a published cell. A notebook server is temporary and needs an explicitly configured public tunnel for external browser/Postman access. This package does not create or publish a tunnel. A persistent Python host is preferable for a stable URL.

## Interpretation limits

The CSV has no units metadata for nutrients or rainfall period, no measured yields, no location/season labels, no costs and no farming outcome labels. Do not treat the model's probability as the probability of a profitable harvest. Perturbation tests measure prediction stability, not real-world intervention effects. Good held-out CSV performance does not establish regional or field generalization. Input bounds such as temperature -10 to 60 are the notebook's supported application limits, not universal physical laws.
