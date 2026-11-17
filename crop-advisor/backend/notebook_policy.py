# Extracted unchanged from model_train_v2.ipynb.
import numpy as np
import pandas as pd

def validate_input(raw, meta):
    """Returns (clean_values or None, errors, range_warnings)."""
    errors, warns, clean = [], [], {}
    for f in meta["features"]:
        if f not in raw or raw[f] is None:
            errors.append(f"Missing input: {f}"); continue
        try:
            v = float(raw[f])
        except (TypeError, ValueError):
            errors.append(f"{f} must be numeric"); continue
        if not np.isfinite(v):
            errors.append(f"{f} must be a finite number"); continue
        lo_b, hi_b = meta["physical_bounds"][f]
        if (lo_b is not None and v < lo_b) or (hi_b is not None and v > hi_b):
            errors.append(f"{f}={v:g} is physically impossible (allowed {lo_b} to {hi_b if hi_b is not None else 'no upper limit'})")
            continue
        clean[f] = v
    if errors:
        return None, errors, warns
    for f, v in clean.items():
        r = meta["training_ranges"][f]
        if v < r["min"] or v > r["max"]:
            warns.append(f"{f}={v:g} is outside the range the model was trained on ({r['min']:.3f} to {r['max']:.3f})")
    return clean, errors, warns

def assess_input(raw, model, meta, detectors, top_k=3):
    clean, errors, range_warns = validate_input(raw, meta)
    if errors:
        return {"status": "invalid", "recommendation": None, "errors": errors}

    x = pd.DataFrame([[clean[f] for f in meta["features"]]], columns=meta["features"])
    proba = model.predict_proba(x)[0]
    order = np.argsort(proba)[::-1][:top_k]
    top = [{"crop": str(model.classes_[i]), "probability": round(float(proba[i]), 3)} for i in order]
    pred, conf = top[0]["crop"], float(proba[order[0]])

    det = detectors[pred]
    diff = x.values[0] - det["mean"]
    d2 = float(diff @ det["precision"] @ diff)
    unusual = d2 > det["threshold"]

    reasons = list(range_warns)
    if unusual:
        reasons.append(f"This combination is atypical for {pred} (distance {d2:.1f} vs limit {det['threshold']:.1f})")
    low_conf = conf < meta["thresholds"]["low_confidence"]
    if low_conf:
        reasons.append(f"Model confidence {conf:.0%} is below {meta['thresholds']['low_confidence']:.0%}")

    if range_warns:                 status = "out_of_range"
    elif unusual:                   status = "unusual_input"
    elif low_conf:                  status = "low_confidence"
    else:                           status = "ok"

    return {"status": status,
            "recommendation": pred if status == "ok" else None,
            "top_candidates": top if status in ("ok", "low_confidence") else None,
            "confidence": round(conf, 3), "reasons": reasons}