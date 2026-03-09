"""
Train ML models on India Life Insurance Claims dataset.
Models:
  1. Claims Settlement Ratio Predictor (Regression)
  2. Insurer Risk Tier Classifier (Classification)
  3. Anomaly Detection for unusual claim patterns

Run this script to train and save models:
    python train_model.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import cross_val_score, LeaveOneOut
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    IsolationForest,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_absolute_error,
    classification_report,
    r2_score,
)

warnings.filterwarnings("ignore")

DATA_PATH = Path(__file__).parent.parent / "Dataset" / "1. India Life Insurance Claims" / "India Life Insurance Claims.csv"
MODEL_DIR = Path(__file__).parent / "models"


def load_and_clean_data() -> pd.DataFrame:
    """Load the dataset, clean, and engineer features."""
    df = pd.read_csv(str(DATA_PATH), encoding="latin-1")

    # Drop rows with all nulls / summary rows
    df = df.dropna(subset=["life_insurer", "year"])

    # Remove "Industry" aggregate row
    df = df[df["life_insurer"] != "Industry"].copy()

    # Parse year to numeric (use end year)
    df["year_num"] = df["year"].str.split("-").str[0].astype(int)

    # Feature engineering
    df["rejection_rate"] = (
        df["claims_repudiated_no"] + df["claims_rejected_no"]
    ) / df["total_claims_no"].replace(0, np.nan)

    df["pending_rate"] = df["claims_pending_end_no"] / df["total_claims_no"].replace(0, np.nan)

    df["avg_claim_size"] = df["total_claims_amt"] / df["total_claims_no"].replace(0, np.nan)

    df["avg_paid_size"] = df["claims_paid_amt"] / df["claims_paid_no"].replace(0, np.nan)

    df["claims_volume_log"] = np.log1p(df["total_claims_no"])

    df["claims_amt_log"] = np.log1p(df["total_claims_amt"])

    df["pending_growth"] = (
        df["claims_pending_end_no"] - df["claims_pending_start_no"]
    ) / df["claims_pending_start_no"].replace(0, np.nan)

    # Fill remaining NaN with 0
    df = df.fillna(0)

    # Encode insurer names
    le = LabelEncoder()
    df["insurer_encoded"] = le.fit_transform(df["life_insurer"])

    return df, le


def get_features() -> list[str]:
    """Feature columns for the models."""
    return [
        "year_num",
        "insurer_encoded",
        "claims_pending_start_no",
        "claims_intimated_no",
        "total_claims_no",
        "claims_repudiated_no",
        "claims_rejected_no",
        "claims_unclaimed_no",
        "claims_pending_end_no",
        "total_claims_amt",
        "claims_paid_amt",
        "rejection_rate",
        "pending_rate",
        "avg_claim_size",
        "claims_volume_log",
        "claims_amt_log",
        "pending_growth",
    ]


def train_settlement_predictor(df: pd.DataFrame):
    """Model 1: Predict claims settlement ratio (regression)."""
    print("=" * 60)
    print("MODEL 1: Claims Settlement Ratio Predictor")
    print("=" * 60)

    features = get_features()
    X = df[features].values
    y = df["claims_paid_ratio_no"].values

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("regressor", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ])

    # Cross-validation (small dataset, use LOO-like approach)
    cv_scores = cross_val_score(model, X, y, cv=min(10, len(X)), scoring="r2")
    print(f"  Cross-val R² scores: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    cv_mae = cross_val_score(model, X, y, cv=min(10, len(X)), scoring="neg_mean_absolute_error")
    print(f"  Cross-val MAE: {-cv_mae.mean():.4f} ± {cv_mae.std():.4f}")

    # Train on full data
    model.fit(X, y)
    y_pred = model.predict(X)
    print(f"  Training R²: {r2_score(y, y_pred):.4f}")
    print(f"  Training MAE: {mean_absolute_error(y, y_pred):.4f}")

    # Feature importance
    importances = model.named_steps["regressor"].feature_importances_
    feat_imp = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
    print("\n  Top features:")
    for fname, imp in feat_imp[:8]:
        print(f"    {fname}: {imp:.4f}")

    return model


def train_risk_classifier(df: pd.DataFrame):
    """Model 2: Classify insurers into risk tiers (High/Medium/Low performance)."""
    print("\n" + "=" * 60)
    print("MODEL 2: Insurer Risk Tier Classifier")
    print("=" * 60)

    # Create risk tiers based on settlement ratio
    df = df.copy()
    df["risk_tier"] = pd.cut(
        df["claims_paid_ratio_no"],
        bins=[-0.01, 0.85, 0.95, 1.01],
        labels=["High Risk", "Medium Risk", "Low Risk"],
    )

    print(f"\n  Class distribution:")
    print(f"    {df['risk_tier'].value_counts().to_dict()}")

    features = get_features()
    # Remove features that directly leak the target
    clf_features = [f for f in features if "ratio" not in f.lower()]
    X = df[clf_features].values
    y_labels = df["risk_tier"].astype(str).values

    le_risk = LabelEncoder()
    y = le_risk.fit_transform(y_labels)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=2,
            random_state=42,
            class_weight="balanced",
        )),
    ])

    cv_scores = cross_val_score(model, X, y, cv=min(10, len(X)), scoring="accuracy")
    print(f"  Cross-val accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    model.fit(X, y)
    y_pred = model.predict(X)
    print(f"\n  Training classification report:")
    print(classification_report(le_risk.inverse_transform(y), le_risk.inverse_transform(y_pred), zero_division=0))

    return model, le_risk, clf_features


def train_anomaly_detector(df: pd.DataFrame):
    """Model 3: Detect anomalous insurer claim patterns."""
    print("\n" + "=" * 60)
    print("MODEL 3: Anomaly Detector")
    print("=" * 60)

    features = get_features()
    X = df[features].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.1,
        random_state=42,
    )
    model.fit(X_scaled)

    predictions = model.predict(X_scaled)
    anomaly_scores = model.decision_function(X_scaled)

    n_anomalies = (predictions == -1).sum()
    print(f"  Anomalies detected: {n_anomalies} / {len(df)}")

    anomaly_idx = np.where(predictions == -1)[0]
    if len(anomaly_idx) > 0:
        print(f"\n  Anomalous insurers:")
        for idx in anomaly_idx:
            print(f"    {df.iloc[idx]['life_insurer']} ({df.iloc[idx]['year']})"
                  f" - settlement ratio: {df.iloc[idx]['claims_paid_ratio_no']:.3f}"
                  f" - anomaly score: {anomaly_scores[idx]:.3f}")

    return model, scaler


def main():
    MODEL_DIR.mkdir(exist_ok=True)

    # Load data
    print("Loading and preparing data...")
    df, insurer_encoder = load_and_clean_data()
    print(f"Dataset: {len(df)} records, {df['life_insurer'].nunique()} insurers, {df['year'].nunique()} years\n")

    # Train models
    settlement_model = train_settlement_predictor(df)
    risk_model, risk_encoder, risk_features = train_risk_classifier(df)
    anomaly_model, anomaly_scaler = train_anomaly_detector(df)

    # Save everything
    joblib.dump(settlement_model, MODEL_DIR / "settlement_predictor.joblib")
    joblib.dump(risk_model, MODEL_DIR / "risk_classifier.joblib")
    joblib.dump(risk_encoder, MODEL_DIR / "risk_label_encoder.joblib")
    joblib.dump(anomaly_model, MODEL_DIR / "anomaly_detector.joblib")
    joblib.dump(anomaly_scaler, MODEL_DIR / "anomaly_scaler.joblib")
    joblib.dump(insurer_encoder, MODEL_DIR / "insurer_encoder.joblib")
    joblib.dump(get_features(), MODEL_DIR / "feature_names.joblib")
    joblib.dump(risk_features, MODEL_DIR / "risk_feature_names.joblib")

    # Save the cleaned data for serving
    df.to_csv(MODEL_DIR / "cleaned_data.csv", index=False)

    print("\n" + "=" * 60)
    print("All models trained and saved to backend/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
