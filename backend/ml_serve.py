"""ML model serving: load trained models and provide predictions."""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "models"

# Lazy-loaded model cache
_cache: dict = {}


def _load(name: str):
    if name not in _cache:
        path = MODEL_DIR / name
        if not path.exists():
            raise FileNotFoundError(
                f"Model file {name} not found. Run 'python train_model.py' first."
            )
        _cache[name] = joblib.load(path)
    return _cache[name]


def get_cleaned_data() -> pd.DataFrame:
    return pd.read_csv(MODEL_DIR / "cleaned_data.csv")


def predict_settlement_ratio(insurer_name: str, year: int, claims_data: dict) -> dict:
    """Predict the claims settlement ratio for an insurer."""
    model = _load("settlement_predictor.joblib")
    insurer_enc = _load("insurer_encoder.joblib")
    features = _load("feature_names.joblib")

    # Encode insurer
    try:
        insurer_code = insurer_enc.transform([insurer_name])[0]
    except ValueError:
        # Unknown insurer — use median encoding
        insurer_code = len(insurer_enc.classes_) // 2

    # Build feature vector
    total_claims = claims_data.get("total_claims_no", 0)
    total_amt = claims_data.get("total_claims_amt", 0)
    repudiated = claims_data.get("claims_repudiated_no", 0)
    rejected = claims_data.get("claims_rejected_no", 0)
    pending_start = claims_data.get("claims_pending_start_no", 0)
    pending_end = claims_data.get("claims_pending_end_no", 0)
    intimated = claims_data.get("claims_intimated_no", total_claims)
    unclaimed = claims_data.get("claims_unclaimed_no", 0)
    paid_amt = claims_data.get("claims_paid_amt", 0)

    rejection_rate = (repudiated + rejected) / total_claims if total_claims > 0 else 0
    pending_rate = pending_end / total_claims if total_claims > 0 else 0
    avg_claim_size = total_amt / total_claims if total_claims > 0 else 0
    claims_volume_log = np.log1p(total_claims)
    claims_amt_log = np.log1p(total_amt)
    pending_growth = (
        (pending_end - pending_start) / pending_start if pending_start > 0 else 0
    )

    feature_values = {
        "year_num": year,
        "insurer_encoded": insurer_code,
        "claims_pending_start_no": pending_start,
        "claims_intimated_no": intimated,
        "total_claims_no": total_claims,
        "claims_repudiated_no": repudiated,
        "claims_rejected_no": rejected,
        "claims_unclaimed_no": unclaimed,
        "claims_pending_end_no": pending_end,
        "total_claims_amt": total_amt,
        "claims_paid_amt": paid_amt,
        "rejection_rate": rejection_rate,
        "pending_rate": pending_rate,
        "avg_claim_size": avg_claim_size,
        "claims_volume_log": claims_volume_log,
        "claims_amt_log": claims_amt_log,
        "pending_growth": pending_growth,
    }

    X = np.array([[feature_values[f] for f in features]])
    predicted_ratio = float(model.predict(X)[0])
    predicted_ratio = max(0.0, min(1.0, predicted_ratio))

    return {
        "predicted_settlement_ratio": round(predicted_ratio, 4),
        "predicted_percentage": round(predicted_ratio * 100, 2),
        "risk_level": (
            "Low Risk" if predicted_ratio >= 0.95
            else "Medium Risk" if predicted_ratio >= 0.85
            else "High Risk"
        ),
        "insurer": insurer_name,
        "year": year,
    }


def classify_risk_tier(insurer_name: str, year: int, claims_data: dict) -> dict:
    """Classify an insurer into a risk tier."""
    model = _load("risk_classifier.joblib")
    risk_enc = _load("risk_label_encoder.joblib")
    insurer_enc = _load("insurer_encoder.joblib")
    features = _load("risk_feature_names.joblib")

    try:
        insurer_code = insurer_enc.transform([insurer_name])[0]
    except ValueError:
        insurer_code = len(insurer_enc.classes_) // 2

    total_claims = claims_data.get("total_claims_no", 0)
    total_amt = claims_data.get("total_claims_amt", 0)
    repudiated = claims_data.get("claims_repudiated_no", 0)
    rejected = claims_data.get("claims_rejected_no", 0)
    pending_start = claims_data.get("claims_pending_start_no", 0)
    pending_end = claims_data.get("claims_pending_end_no", 0)
    intimated = claims_data.get("claims_intimated_no", total_claims)
    unclaimed = claims_data.get("claims_unclaimed_no", 0)
    paid_amt = claims_data.get("claims_paid_amt", 0)

    avg_claim_size = total_amt / total_claims if total_claims > 0 else 0
    claims_volume_log = np.log1p(total_claims)
    claims_amt_log = np.log1p(total_amt)
    pending_growth = (
        (pending_end - pending_start) / pending_start if pending_start > 0 else 0
    )

    feature_values = {
        "year_num": year,
        "insurer_encoded": insurer_code,
        "claims_pending_start_no": pending_start,
        "claims_intimated_no": intimated,
        "total_claims_no": total_claims,
        "claims_repudiated_no": repudiated,
        "claims_rejected_no": rejected,
        "claims_unclaimed_no": unclaimed,
        "claims_pending_end_no": pending_end,
        "total_claims_amt": total_amt,
        "claims_paid_amt": paid_amt,
        "avg_claim_size": avg_claim_size,
        "claims_volume_log": claims_volume_log,
        "claims_amt_log": claims_amt_log,
        "pending_growth": pending_growth,
    }

    X = np.array([[feature_values.get(f, 0) for f in features]])
    pred = model.predict(X)[0]
    proba = model.predict_proba(X)[0]
    tier = risk_enc.inverse_transform([pred])[0]
    class_names = risk_enc.inverse_transform(range(len(proba)))
    confidence = {name: round(float(p) * 100, 1) for name, p in zip(class_names, proba)}

    return {
        "risk_tier": tier,
        "confidence": confidence,
        "insurer": insurer_name,
        "year": year,
    }


def detect_anomalies() -> list[dict]:
    """Run anomaly detection on all data and return flagged insurers."""
    model = _load("anomaly_detector.joblib")
    scaler = _load("anomaly_scaler.joblib")
    features = _load("feature_names.joblib")
    df = get_cleaned_data()

    X = df[features].values
    X_scaled = scaler.transform(X)

    preds = model.predict(X_scaled)
    scores = model.decision_function(X_scaled)

    anomalies = []
    for i in range(len(df)):
        if preds[i] == -1:
            anomalies.append({
                "insurer": df.iloc[i]["life_insurer"],
                "year": df.iloc[i]["year"],
                "settlement_ratio": round(float(df.iloc[i]["claims_paid_ratio_no"]), 4),
                "anomaly_score": round(float(scores[i]), 4),
                "total_claims": int(df.iloc[i]["total_claims_no"]),
                "reason": _explain_anomaly(df.iloc[i]),
            })

    return sorted(anomalies, key=lambda x: x["anomaly_score"])


def _explain_anomaly(row: pd.Series) -> str:
    """Generate a human-readable reason for the anomaly flag."""
    reasons = []
    if row["total_claims_no"] > 50000:
        reasons.append("very high claims volume")
    if row["claims_paid_ratio_no"] < 0.85:
        reasons.append("low settlement ratio")
    if row["rejection_rate"] > 0.05:
        reasons.append(f"high rejection rate ({row['rejection_rate']:.1%})")
    if row["pending_rate"] > 0.02:
        reasons.append(f"high pending rate ({row['pending_rate']:.1%})")
    if row["pending_growth"] > 1.0:
        reasons.append("pending claims grew significantly")
    if not reasons:
        reasons.append("unusual pattern in claims metrics relative to peers")
    return "; ".join(reasons)


def get_insurer_list() -> list[str]:
    """Return list of known insurers."""
    enc = _load("insurer_encoder.joblib")
    return list(enc.classes_)


def get_all_predictions() -> list[dict]:
    """Return predictions for all insurers in the dataset (for dashboard overview)."""
    df = get_cleaned_data()
    model = _load("settlement_predictor.joblib")
    features = _load("feature_names.joblib")

    X = df[features].values
    predictions = model.predict(X)

    results = []
    for i, row in df.iterrows():
        pred = max(0.0, min(1.0, float(predictions[i] if isinstance(i, int) else predictions[results.__len__()])))
        results.append({
            "insurer": row["life_insurer"],
            "year": row["year"],
            "actual_ratio": round(float(row["claims_paid_ratio_no"]), 4),
            "predicted_ratio": round(pred, 4),
            "residual": round(float(row["claims_paid_ratio_no"]) - pred, 4),
            "total_claims": int(row["total_claims_no"]),
            "total_amount": round(float(row["total_claims_amt"]), 2),
        })

    return results
