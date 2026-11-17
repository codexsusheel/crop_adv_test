"""Crop Advisor API: the supplied notebook model plus transparent planning tools."""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sklearn.model_selection import train_test_split
from .market import prices
from .notebook_policy import assess_input

ROOT = Path(__file__).resolve().parents[1]
model = joblib.load(ROOT / 'model/crop_recommendation_model.pkl')
meta = joblib.load(ROOT / 'model/model_metadata.pkl')
detectors = joblib.load(ROOT / 'model/class_anomaly_detectors.pkl')
data = pd.read_csv(ROOT / 'dataset/Crop_recommendation.csv')
train, _ = train_test_split(data, test_size=0.2, random_state=42, stratify=data.label)
FEATURES = meta['features']
SCALE = train[FEATURES].std()
app = FastAPI(title='Crop Advisor', version='1.0.0')

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Soil(StrictModel):
    N: float = Field(ge=0)
    P: float = Field(ge=0)
    K: float = Field(ge=0)
    temperature: float = Field(ge=-10, le=60)
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    rainfall: float = Field(ge=0)

def check_crop(crop):
    if crop not in meta['classes']:
        raise HTTPException(404, 'Crop is not supported by this model')

def prediction(soil):
    raw = soil.model_dump()
    result = assess_input(raw, model, meta, detectors)
    x = pd.DataFrame([raw], columns=FEATURES)
    p = model.predict_proba(x)[0]
    order = np.argsort(p)[::-1]
    # Inspect the forests inside the existing calibrated model. No retraining or
    # artificial probability smoothing: isotonic calibration can produce 0/1.
    forest_scores = np.mean([c.estimator.predict_proba(x)[0]
                            for c in model.calibrated_classifiers_], axis=0)
    forest_order = np.argsort(forest_scores)[::-1]
    winner = model.classes_[order[0]]
    rng = np.random.default_rng(42)
    # Noise uses 1% of each training standard deviation, not mixed-unit percentages.
    noisy = pd.DataFrame(np.tile(x.values, (40, 1)) + rng.normal(size=(40, len(FEATURES))) * SCALE.values * .01, columns=FEATURES)
    stability = float(np.mean(model.predict(noisy) == winner))
    margin = float(p[order[0]] - p[order[1]])
    status = result['status']
    if status in ('out_of_range', 'unusual_input'):
        status = 'OUT_OF_RANGE'
    elif status == 'low_confidence' or margin < .15 or stability < .70:
        status = 'LOW_CONFIDENCE'
    else:
        status = 'OK'
    reasons = result.get('reasons', [])
    if margin < .15:
        reasons.append('The top two crops have similar probabilities (margin below 0.15).')
    if stability < .70:
        reasons.append('The top crop changes in more than 30% of small-noise trials.')
    explanations = []
    if status != 'OUT_OF_RANGE':
        # A local sensitivity explanation, not a causal or SHAP attribution.
        changed = pd.concat([x] * len(FEATURES), ignore_index=True)
        for i, feature in enumerate(FEATURES):
            changed.loc[i, feature] = train[feature].median()
        effects = p[order[0]] - model.predict_proba(changed)[:, order[0]]
        explanations = sorted([{'feature': f, 'probability_difference': round(float(e), 4)} for f, e in zip(FEATURES, effects)], key=lambda r: abs(r['probability_difference']), reverse=True)[:5]
    return {'status': status, 'recommendation': str(winner) if status == 'OK' else None,
        'top_candidates': [{'crop': str(model.classes_[i]), 'probability': float(p[i])}
                           for i in order[:3]] if status != 'OUT_OF_RANGE' else None,
        'forest_candidates': [{'crop': str(model.classes_[i]), 'score': float(forest_scores[i]),
                               'calibrated_probability': float(p[i])}
                              for i in forest_order[:5]] if status != 'OUT_OF_RANGE' else None,
        'probability_note': 'Isotonic calibration may produce exact 0% or 100%. Forest scores show the underlying uncalibrated model support; they are not calibrated confidence.',
        'confidence': float(p.max()), 'confidence_label': 'High' if status=='OK' else 'Low' if status=='OUT_OF_RANGE' else 'Medium',
        'margin': margin, 'normalised_entropy': float(-np.sum(p * np.log(np.maximum(p, 1e-15)))/np.log(len(p))),
        'stability': {'trials': 40, 'unchanged_fraction': stability, 'noise': '1% of training standard deviation; seed 42'},
        'reasons': reasons, 'explanation': explanations,
        'explanation_method': 'Probability difference when one input is replaced with its training median; not causal.',
        'note': 'Confidence is a model probability, not a guarantee of crop success.'}

@app.get('/meta')
def metadata():
    return {**meta, 'context_only': ['state', 'season', 'soil_type', 'salinity', 'organic_carbon'],
            'units_note': 'CSV does not document nutrient units or rainfall period. Match the original dataset scale; do not assume NPK values are fertilizer doses.'}

@app.get('/states')
def states():
    return {'states': [], 'message': 'No state labels in training CSV. Enter a state name for the market API only; no state-wise suitability is claimed.'}

@app.get('/crops')
def crops():
    return {'crops': meta['classes']}

@app.get('/crops/{crop}')
def crop_details(crop: str):
    check_crop(crop)
    rows = train[train.label == crop]
    return {'crop': crop, 'ranges': {f: {'ideal': rows[f].quantile([.1,.9]).tolist(), 'acceptable': rows[f].quantile([.025,.975]).tolist()} for f in FEATURES},
            'duration_days': None, 'yield': None, 'cost': None, 'seasons': None, 'soil_types': None,
            'note': 'Training-data percentiles, not validated agronomic limits. Missing reference data is deliberately left unknown.'}

@app.post('/predict')
def predict(soil: Soil):
    return prediction(soil)

class Land(StrictModel):
    crop: str
    inputs: Soil

@app.post('/land-check')
def land_check(body: Land):
    ranges = crop_details(body.crop)['ranges']
    checks = {}
    for f,v in body.inputs.model_dump().items():
        r = ranges[f]
        checks[f] = 'ideal' if r['ideal'][0] <= v <= r['ideal'][1] else 'borderline' if r['acceptable'][0] <= v <= r['acceptable'][1] else 'outside'
    score = sum({'ideal':1,'borderline':.5,'outside':0}[v] for v in checks.values())/len(checks)
    return {'crop': body.crop, 'features': checks, 'fit_score': score,
        'verdict': 'SUITABLE' if score >= .8 else 'MARGINAL' if score >= .5 else 'NOT_SUITABLE',
        'model_probability': float(model.predict_proba(pd.DataFrame([body.inputs.model_dump()], columns=FEATURES))[0,list(model.classes_).index(body.crop)]),
        'advice': 'Review outside-range measurements with a local agronomist; percentile fit is not an intervention plan.',
        'assessment': prediction(body.inputs)}

class Change(StrictModel):
    inputs: Soil
    feature: str
    operation: str = 'set'
    value: float

@app.post('/what-if')
def what_if(body: Change):
    if body.feature not in FEATURES or body.operation not in ('set','add','percent'):
        raise HTTPException(422, 'Use a supported feature and set, add or percent')
    raw = body.inputs.model_dump()
    old = raw[body.feature]
    raw[body.feature] = body.value if body.operation=='set' else old+body.value if body.operation=='add' else old*(1+body.value/100)
    try:
        after = Soil(**raw)
    except ValueError:
        raise HTTPException(422, 'Changed value exceeds application input limits')
    before_p, after_p = model.predict_proba(pd.DataFrame([body.inputs.model_dump(), raw], columns=FEATURES))
    return {'before': prediction(body.inputs), 'after': prediction(after),
            'probability_changes': {str(c): float(b-a) for c,a,b in zip(model.classes_, before_p, after_p)},
            'note': 'Model sensitivity only; not a causal effect or a fertilizer prescription.'}

class Sweep(StrictModel):
    inputs: Soil
    feature: str
    start: float
    end: float
    steps: int = Field(default=10, ge=2, le=30)

@app.post('/what-if/sweep')
def sweep(body: Sweep):
    if body.start >= body.end:
        raise HTTPException(422, 'Start must be less than end')
    rows = []
    for value in np.linspace(body.start, body.end, body.steps):
        result = what_if(Change(inputs=body.inputs, feature=body.feature, value=float(value)))['after']
        rows.append({'value': float(value), 'status': result['status'], 'recommendation': result['recommendation'], 'confidence': result['confidence']})
    return {'points': rows, 'tipping_intervals': [[a['value'], b['value']] for a,b in zip(rows, rows[1:]) if a['recommendation']!=b['recommendation']]}

@app.get('/market/{crop}')
async def market(crop: str, state: str = Query(min_length=2, max_length=80), commodity: str | None = Query(default=None, max_length=80), district: str | None = Query(default=None, max_length=80)):
    check_crop(crop)
    return await prices(crop, state, commodity, district)

class Profit(StrictModel):
    area_ha: float = Field(gt=0)
    price_per_quintal: float = Field(gt=0)
    low_yield_q_ha: float = Field(ge=0)
    typical_yield_q_ha: float = Field(gt=0)
    high_yield_q_ha: float = Field(gt=0)
    cost_per_ha: float = Field(ge=0)
    duration_days: float = Field(gt=0)

@app.post('/profit')
def profit(body: Profit):
    if not body.low_yield_q_ha <= body.typical_yield_q_ha <= body.high_yield_q_ha:
        raise HTTPException(422, 'Yields must be ordered low <= typical <= high')
    scenarios = {}
    for label, amount in [('low',body.low_yield_q_ha),('typical',body.typical_yield_q_ha),('high',body.high_yield_q_ha)]:
        net = (amount*body.price_per_quintal-body.cost_per_ha)*body.area_ha
        scenarios[label] = {'revenue_inr': amount*body.price_per_quintal*body.area_ha, 'profit_inr': net, 'profit_per_30_days_inr': net/body.duration_days*30}
    return {'scenarios': scenarios, 'break_even_yield_q_ha': body.cost_per_ha/body.price_per_quintal,
            'break_even_price_inr_q': body.cost_per_ha/body.typical_yield_q_ha,
            'note': 'Scenario arithmetic using your assumptions; not a yield or price forecast.'}

class Fertilizer(StrictModel):
    crop: str
    inputs: Soil
    measurement_basis: str = 'csv_scale'

@app.post('/fertilizer')
def fertilizer(body: Fertilizer):
    check_crop(body.crop)
    if body.measurement_basis not in ('csv_scale', 'confirmed_available_kg_ha'):
        raise HTTPException(422, 'Choose csv_scale or confirmed_available_kg_ha')
    rows = train[train.label == body.crop]
    products = {'N': 'Urea (nitrogen source)', 'P': 'Single superphosphate / SSP (phosphorus source)',
                'K': 'Muriate of potash / MOP (potassium source)'}
    # TNAU available-N/P/K ratings use elemental kg/ha, not P2O5/K2O or ppm.
    published = {'N': (240, 480), 'P': (11, 22), 'K': (110, 280)}
    nutrients = []
    for feature in ('N', 'P', 'K'):
        value = getattr(body.inputs, feature)
        confirmed = body.measurement_basis == 'confirmed_available_kg_ha'
        low, high = published[feature] if confirmed else rows[feature].quantile([.1, .9]).tolist()
        status = ('low' if value < low else 'high' if value > high else 'medium') if confirmed else (
            'below_reference' if value < low else 'above_reference' if value > high else 'within_reference')
        needs_review = value < low
        nutrients.append({'nutrient': feature, 'value': value, 'reference_range': [float(low), float(high)],
            'status': status, 'suggested_product': products[feature] if needs_review else None,
            'action': (f'Consider {products[feature]} after confirming the crop-specific requirement with a soil-test recommendation.' if confirmed else
                       f'Lower than typical {body.crop} samples. Verify a deficiency with a soil test; if confirmed, discuss {products[feature]}.') if needs_review else
                      'No extra nutrient suggested from this screening. Follow the crop-specific soil-test recommendation.',
            'priority': 'review' if needs_review else 'no_extra_suggested'})
    ph = body.inputs.ph
    warnings = []
    if ph < 6:
        warnings.append('Acidic pH can affect nutrient availability. Ask for a lime-requirement test before adding amendments.')
    elif ph > 8.5:
        warnings.append('High pH can restrict nutrient availability. Test alkalinity/sodicity before choosing amendments.')
    return {'crop': body.crop, 'measurement_basis': body.measurement_basis,
        'reference_label': 'TNAU available elemental N/P/K soil ratings (kg/ha)' if body.measurement_basis=='confirmed_available_kg_ha' else 'Selected crop training-sample 10th–90th percentiles (CSV scale)',
        'nutrients': nutrients, 'ph': ph, 'warnings': warnings,
        'source_url': 'https://agritech.tnau.ac.in/agriculture/agri_soil_soilratingchart.html' if body.measurement_basis=='confirmed_available_kg_ha' else None,
        'note': 'Suggestions identify nutrient sources, not an application dose. CSV comparisons are not laboratory deficiency diagnoses. Do not subtract soil readings from reference values to calculate fertilizer quantities.'}

class Rotation(StrictModel):
    previous_crop: str

@app.post('/rotation')
def rotation(body: Rotation):
    check_crop(body.previous_crop)
    legumes = {'blackgram','chickpea','kidneybeans','lentil','mothbeans','mungbean','pigeonpeas'}
    annual_nonlegumes = {'rice','maize','cotton','jute','watermelon','muskmelon'}
    if body.previous_crop not in legumes | annual_nonlegumes:
        return {'candidates': [], 'note': 'Perennial/orchard crops need a separate rotation plan.'}
    return {'candidates': sorted(annual_nonlegumes if body.previous_crop in legumes else legumes),
            'note': 'Broad legume/non-legume planning hint only. Season, crop family, water, pests and local sequences are not validated by this dataset.'}

@app.get('/metrics')
def metrics():
    return json.loads((ROOT / 'reports/metrics.json').read_text())

@app.get('/metrics/{section}')
def metric_section(section: str):
    if section == 'decision-rules':
        return {'probability_threshold': meta['thresholds']['low_confidence'], 'minimum_margin': .15, 'minimum_stability': .70,
            'out_of_range': meta['thresholds']['unusual_input'], 'precedence': 'OUT_OF_RANGE > LOW_CONFIDENCE > OK',
            'note': 'Retains notebook 98th-percentile detector and confidence threshold, rather than PDF thresholds.'}
    mapping = {'classwise':'classwise','confusion-matrix':'confusion_matrix','robustness':'robustness'}
    if section not in mapping:
        raise HTTPException(404, 'Unknown metrics section')
    return metrics()[mapping[section]]

app.mount('/plots', StaticFiles(directory=ROOT / 'reports/plots'), name='plots')
app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
