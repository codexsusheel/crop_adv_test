# Run Crop Advisor on your computer

This guide is for the project recipient. The ZIP includes the trained crop model, plain HTML/CSS/JavaScript frontend, FastAPI backend and a government market-price CSV. You do not need to train the model or get an API key.

The app uses MongoDB for market searches. The sender's MongoDB database is not part of the ZIP: import the included CSV once on your own computer using step 4.

## 1. Install the prerequisites

- **Python 3.13, 64-bit**: choose a 3.13 release from [Python's official Windows downloads](https://www.python.org/downloads/windows/). This is the Python version used for verification. Avoid creating this environment with Python 3.14; keep the supplied package versions for the saved model.
- **MongoDB Community Server**: follow the [official Windows installation guide](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-windows/) and choose a server release supported by your Windows version. Select **Install MongoD as a Service** during installation so MongoDB can run in the background. MongoDB Compass is an optional database viewer; Compass alone does not install the database server.
- **VS Code** is optional but convenient. Node.js, npm, Anaconda, Jupyter and Live Server are not required to run the app.

Installers/dependencies need internet access initially. Normal predictions and imported market lookups run locally. Font downloads are optional; the UI falls back to system fonts offline.

## 2. Extract and open the project

Extract the ZIP completely, for example to `C:\Projects\crop-advisor`. Do not run it from inside the ZIP preview.

In VS Code, choose **File → Open Folder** and open the folder containing these items directly:

```text
crop-advisor/
  instructions.md
  requirements.txt
  backend/
  frontend/
  model/
  dataset/
    Crop_recommendation.csv
    9ef84268-d588-465a-a308-a864a43d0070.csv
  scripts/
  reports/
  tests/
```

Open **Terminal → New Terminal** and choose PowerShell. All commands below must run from that project folder. If needed, change directory using your actual extracted path:

```powershell
cd "C:\Projects\crop-advisor"
```

## 3. Create your own Python environment

```powershell
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `py` is unavailable but `python --version` reports Python 3.13, use `python -m venv .venv` instead. Do not copy or reuse the sender's `.venv`; it contains machine-specific paths.

The commands call the environment's interpreter directly, so PowerShell environment activation and execution-policy changes are unnecessary.

Optional VS Code setting: **Ctrl+Shift+P → Python: Select Interpreter**, then choose `.venv\Scripts\python.exe`.

## 4. Start MongoDB and import the bundled prices

Open Windows **Services**, find **MongoDB**, and confirm it is Running. If it is stopped, choose Start. If the service does not exist, revisit the server installation instructions; installing Compass alone is insufficient.

In the project terminal:

```powershell
$env:MONGODB_URI = "mongodb://127.0.0.1:27017"
$env:MONGODB_DATABASE = "crop_advisor"
.\.venv\Scripts\python.exe -c "from backend.market_store import client; print(client().admin.command('ping')['ok'])"
```

A successful check prints `1.0`. Then import the included official CSV:

```powershell
.\.venv\Scripts\python.exe scripts/import_market_data.py ".\dataset\9ef84268-d588-465a-a308-a864a43d0070.csv" --resource-id 9ef84268-d588-465a-a308-a864a43d0070
```

The bundled file contains **6,897 records dated 17 November 2026**. Its original government source is [Current Daily Price of Various Commodities from Various Markets (Mandi)](https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi). Expect the final counters to show `accepted: 6897` and `invalid: 0`.

Database: `crop_advisor`. Quote collection: `market_prices`. Import-history collection: `market_imports`. Repeating the same import updates existing matching quotes rather than duplicating them. Importing this snapshot does not overwrite unrelated quotes already in that database.

Optional Compass check: connect to `mongodb://127.0.0.1:27017`, then open `crop_advisor → market_prices`.

The URI/database above are defaults. If you use an existing authenticated MongoDB or Atlas deployment, set your own URI and database in the terminal; keep credentials out of code and shared files. For the local setup described here, no government API key is needed.

## 5. Run FastAPI

Use the same project terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Wait for **Application startup complete**, then open:

- **Application:** http://127.0.0.1:8000
- **Endpoint documentation:** http://127.0.0.1:8000/docs

Keep this terminal running. The server serves both frontend and backend. Do not open `index.html` directly or use Live Server.

## 6. Try the features

### Crop recommendation

Open **Recommend → Use sample values → Assess my field**. The supplied example should recommend rice. Calibrated confidence may be exactly 100%; the separate forest-support scores show the underlying uncalibrated distribution. Unusual inputs can withhold a recommendation.

### Market prices

Open **Market prices** and select:

| State | District | Commodity |
|---|---|---|
| Telangana | Siddipet | Cotton |
| Telangana | Siddipet | Tomato |
| Tamil Nadu | Madurai | Apple |

Leave the reporting date at **Latest imported date** and click **Find prices**. Dropdowns show only imported combinations. These are stored government quotes for the reporting date, not a live market feed. There are no Telangana Apple quotes in the bundled snapshot.

### Other tools

Use **Land & crops** to compare measurements, or **Planning tools** for fertilizer screening, what-if analysis, profit scenarios and rotation hints. Enter the field measurements under Recommend before using tools that depend on them.

Fertilizer screening does not infer application doses from undocumented CSV units. Optional regional references cover specified Tamil Nadu rice/cotton conditions only and require unit/cultivation confirmation. Do not select those profiles for unrelated locations or varieties.

## 7. Stop, restart and use it next time

Press **Ctrl+C** in the FastAPI terminal to stop it. To start again, open the project folder and run the command from step 5. You do not need to reinstall packages, reimport the same CSV or retrain the model each time. MongoDB must remain available.

After code updates, restart FastAPI and press **Ctrl+F5** in the browser to reload assets. If you set custom environment variables, set them again in each new terminal.

## 8. Updating the stored market data

Download a newer official government CSV and run the importer with its path and matching resource ID. Then click **Data refresh & import history → Refresh database coverage** in the UI. The app does not download prices automatically.

See `MONGODB_SETUP.md` for accepted formats, source IDs and import behavior. Keep the bundled crop-training CSV separate from market exports; market data never changes the crop classifier.

## Troubleshooting

| Problem | What to check |
|---|---|
| `No module named uvicorn`, `pymongo`, etc. | Install requirements using `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and start with that same interpreter. |
| `.venv\Scripts\python.exe` is missing | Confirm the terminal is in the project folder and complete step 3. |
| Address/port 8000 already in use | Stop the previous server with Ctrl+C, or use `--port 8001` and open http://127.0.0.1:8001. |
| MongoDB unavailable or import cannot connect | Check MongoDB Server is running on port 27017, then repeat the ping command in step 4. |
| No stored market quotes | Import the bundled CSV, refresh database coverage, and use one of the example combinations above. |
| Model version warnings/errors | Use Python 3.13 and the supplied scikit-learn/numpy/joblib versions in a new environment. Do not retrain just to fix an interpreter mismatch. |
| Old interface | Restart FastAPI, close old tabs, and reopen the local app with Ctrl+F5. |
| Prediction works but market lookup fails | The crop model does not require MongoDB; check the database separately. |

## Optional checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

After importing the bundled data, you can enable MongoDB integration tests:

```powershell
$env:RUN_MONGO_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Integration tests create and remove their own uniquely named disposable collections under `crop_advisor_tests`. They retain your real `crop_advisor.market_prices` records.

## Notes for the sender before making the ZIP

Include this file, source code, requirements, model, reports, tests and **both dataset CSVs**. Exclude `.venv`, `__pycache__`, `.git`, `.env`, old ZIPs and the old generated `manifest.json`. Do not include credentials or MongoDB's internal storage files. The recipient reconstructs market records from the bundled CSV.

After saving the project in Git, a clean ZIP can be produced from the repository root using:

```powershell
git archive --format=zip --prefix=crop-advisor/ --output=Crop-Advisor-Share.zip HEAD:crop-advisor
```

This command includes committed project files and excludes ignored local environments. It is optional; no ZIP is generated automatically by the application.
