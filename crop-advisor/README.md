# Crop Advisor

**Sharing this project? Start with [instructions.md](instructions.md).** It covers installation on another computer and importing the bundled market-price CSV into that computer's MongoDB database.

FastAPI with a plain HTML/CSS/JavaScript frontend, using your supplied crop CSV and notebook. Market prices come exclusively from imported government records stored in MongoDB.

## Run locally

Open PowerShell in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MONGODB_URI = 'mongodb://127.0.0.1:27017'
$env:MONGODB_DATABASE = 'crop_advisor'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000 for the app or http://127.0.0.1:8000/docs for endpoint documentation. Keep MongoDB running. The connection settings above are also the defaults. No government API key is required.

The trained artifacts are included; startup does not retrain the model. Keep the pinned scikit-learn version and only load trusted model artifacts. Restart FastAPI after code changes and hard-refresh the browser.

## Model and uncertainty

Only the supplied Crop_recommendation.csv is used for model training: 2,200 rows, 22 crops and seven numeric inputs (N, P, K, temperature, humidity, ph, rainfall). No state, season, salinity or organic-carbon inputs are fabricated.

scripts/build_model.py executes the supplied model_train_v2.ipynb using a project-directory override. It retains the notebook's stratified 80/20 split, seed 42, five-classifier comparison, 300-tree Random Forest, training-fold calibration selection, confidence threshold and Mahalanobis detectors. Reproduction selected isotonic calibration and a 0.75 confidence threshold; final test accuracy/macro-F1 were 0.9909 on 440 rows. The notebook's stored outputs used scikit-learn 1.9.1; reproduced artifacts use 1.7.2.

The API retains the notebook's 98th-percentile anomaly cutoff and adds margin/stability checks. OUT_OF_RANGE withholds recommendations and candidates. LOW_CONFIDENCE offers a shortlist. Calibrated probabilities may be exactly 0 or 1; the interface separately shows uncalibrated support from the forests inside the existing model, without smoothing or replacing calibrated confidence. Explanations show median-replacement sensitivity, not causal effects.

## Market data

See [MONGODB_SETUP.md](MONGODB_SETUP.md) for imports and database details.

The market browser uses MongoDB-driven State → District → Commodity selectors and optional reporting-date, market and variety filters. Commodities are independent of model labels. Freshness indicators, INR/quintal reports and import history make stored-data coverage visible.

The supplied government CSV has been imported into crop_advisor.market_prices: 6,897 records dated 17 November 2026. Example selections: Cotton / Telangana / Siddipet or Apple / Tamil Nadu / Madurai. There are no Telangana Apple quotes in that snapshot.

All external government API request code, key configuration, HTTP sync and diagnostics have been removed. Updating prices requires a downloaded government CSV/JSON import. Links to government websites remain for downloads and source attribution. FastAPI's own HTTP endpoints remain because the frontend needs them. httpx is retained solely for FastAPI TestClient.

## Planning tools

- Land checker: training-percentile fit, with model assessment.
- What-if and sweep: model sensitivity to input changes.
- Profit: scenarios using explicit user-provided price, yield, duration, area and cost.
- Rotation: broad legume/non-legume hints.
- Fertilizer: N/P/K/pH screening against crop samples or confirmed laboratory available elemental kg/ha ratings. Product-source suggestions are conditional; no dose is inferred from undocumented CSV units.
- Regional fertilizer references: three source-checked TNAU profiles for specified Tamil Nadu rice/cotton conditions, requiring matching state/crop, laboratory-unit selection and cultivation confirmation. Published N/P2O5/K2O reference rates are not soil-adjusted prescriptions or product-quantity conversions. Unsupported crops/regions retain screening only.

Reference sources: https://agritech.tnau.ac.in/agriculture/agri_main_feild_%20InOrganic_biofertilizers_Rice.html and https://agritech.tnau.ac.in/CropProduction/Fibre%20crops/fibrecrops_cotton.html . Soil rating source: https://agritech.tnau.ac.in/agriculture/agri_soil_soilratingchart.html .

## Endpoints

GET: /meta, /states, /crops, /crops/{crop}, /fertilizer/references, /market/options, /market/prices, /market/status, /market/imports, /metrics and its classwise/confusion-matrix/robustness/decision-rules sections, /plots/*.png.

POST: /predict, /land-check, /what-if, /what-if/sweep, /fertilizer, /profit, /rotation.

Example prediction body:

```json
{"N":90,"P":42,"K":43,"temperature":20.9,"humidity":82,"ph":6.5,"rainfall":203}
```

Use /docs or import /openapi.json into Postman for request schemas. External government endpoints are not part of this app.

## Verification and rebuild

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# Optional: enable local MongoDB integration tests.
$env:RUN_MONGO_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# Optional, slow: reproduce the original notebook and reports.
.\.venv\Scripts\python.exe scripts/build_model.py
```

Tests create and remove uniquely named disposable collections under crop_advisor_tests. Real imported production records are retained. See reports/VERIFICATION.md for measured checks.

## Limits

Nutrient units and rainfall period are undocumented in the crop CSV. Dataset accuracy is not evidence of field-trial success. Stored market prices do not update automatically and are not harvest-price forecasts. Soil-sample percentile fit does not establish deficiency or a safe fertilizer application rate. No ZIP is regenerated as part of local updates.
