# src/models/earthquake_predictor.py

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import joblib
import logging
from datetime import datetime

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    classification_report
)
from sklearn.calibration import CalibratedClassifierCV

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config

# predictor
class EarthquakePredictor:
    """Probabilistic earthquake risk predictor with alert levels"""

    def __init__(self, model_path=None):
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.feature_names = None
        self.alert_cutoffs = None

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path):
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact["features"]
        self.alert_cutoffs = artifact["alert_cutoffs"]

        print(f"\nModel loaded from {model_path}")

    def predict_risk(self, df: pd.DataFrame):
        X = df[self.feature_names].select_dtypes(include=[np.number])
        X = X.fillna(0)
        return self.model.predict_proba(X)[:, 1]

    def get_alert_level(self, risk_score: float):
        c = self.alert_cutoffs
        if risk_score >= c["SEVERE"]:
            return "SEVERE"
        if risk_score >= c["HIGH"]:
            return "HIGH"
        if risk_score >= c["MODERATE"]:
            return "MODERATE"
        if risk_score >= c["LOW"]:
            return "LOW"
        return "NONE"

# training pipeline
def train_earthquake_model():
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / "earthquake_training.log"))
    logger = logging.getLogger(__name__)

    config = load_config(str(project_root / "config" / "config.yaml"))

    print("\nEARTHQUAKE MODEL TRAINING")

    feature_file = project_root / "data" / "processed" / "earthquake_features.csv"

    df = pd.read_csv(feature_file)
    print(f"Loaded {len(df):,} records")

    # select features
    exclude_cols = {
        "time", "place", "type", "id", "updated",
        "url", "detail", "status",
        "target", "is_event"
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    feature_cols = [c for c in numeric_cols if c not in exclude_cols]

    X = df[feature_cols].fillna(0)
    y = df["target"].astype(int)

    # split
    test_size = config["earthquake"]["training"]["test_size"]
    split_idx = int(len(df) * (1 - test_size))

    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"Train size: {len(X_train):,}")
    print(f"Test size:  {len(X_test):,}")
    print(f"Train positive rate: {y_train.mean():.2%}")

    # sample weight
    sample_weight = np.ones(len(y_train))

    pos_rate = y_train.mean()
    pos_weight = (1 - pos_rate) / (pos_rate + 1e-6)
    sample_weight[y_train == 1] *= pos_weight * 1.5

    if "eq_energy_1d" in X_train.columns:
        activity = X_train["eq_energy_1d"].values
        activity_norm = activity / (np.percentile(activity, 95) + 1e-6)
        sample_weight *= (1 + 0.5 * activity_norm)

    print(f"Effective positive weight ≈ {pos_weight:.1f}")

    # base model (before calibrating)
    base_model = HistGradientBoostingClassifier(
        max_depth=6,
        learning_rate=0.04,
        max_iter=500,
        min_samples_leaf=30,
        random_state=config["earthquake"]["training"]["random_state"]
    )

    print("\nTraining base gradient boosting model...")
    base_model.fit(X_train, y_train, sample_weight=sample_weight)

    # calibration
    print("\nCalibrating probabilities (isotonic)...")

    calibrated_model = CalibratedClassifierCV(
    estimator=base_model,
    method="isotonic",
    cv=5   # 5-fold calibration
)

    calibrated_model.fit(X_train, y_train)

    # evaluation
    y_proba = calibrated_model.predict_proba(X_test)[:, 1]

    pr_auc = average_precision_score(y_test, y_proba)
    roc_auc = roc_auc_score(y_test, y_proba)

    print(f"\nPR-AUC:  {pr_auc:.4f}")
    print(f"ROC-AUC: {roc_auc:.4f}")

 
    # alert thresholds
    pos_scores = y_proba[y_test == 1]

    alert_cutoffs = {
        "LOW": float(np.percentile(pos_scores, 20)),
        "MODERATE": float(np.percentile(pos_scores, 40)),
        "HIGH": float(np.percentile(pos_scores, 65)),
        "SEVERE": float(np.percentile(pos_scores, 85)),
    }

    print("\nAlert cutoffs (event-conditioned):")
    for k, v in alert_cutoffs.items():
        print(f"{k}: {v:.4f}")

    # report
    y_pred = (y_proba >= alert_cutoffs["MODERATE"]).astype(int)

    print("\nClassification Report (MODERATE alert):")
    print(classification_report(
        y_test,
        y_pred,
        target_names=["No Event", "Event"]
    ))

    models_dir = project_root / "models"
    models_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = models_dir / f"earthquake_risk_model_{timestamp}.pkl"

    artifact = {
        "model": calibrated_model,
        "features": feature_cols,
        "alert_cutoffs": alert_cutoffs,
    }

    joblib.dump(artifact, model_path)

    print(f"\nModel saved to {model_path}")
    print("\nTraining complete")

    predictor = EarthquakePredictor()
    predictor.model = calibrated_model
    predictor.feature_names = feature_cols
    predictor.alert_cutoffs = alert_cutoffs

    return predictor

if __name__ == "__main__":
    try:
        train_earthquake_model()
        print("\nTraining completed successfully")
    except Exception as e:
        print("\nTraining failed:", e)
        raise
