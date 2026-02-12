# src/predictors/flood_predictor.py

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import joblib
import json
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix, 
                               accuracy_score, precision_score, recall_score, 
                               f1_score, roc_auc_score)
from sklearn.preprocessing import StandardScaler

project_root = Path(__file__).resolve().parents[2]

config_file = project_root / 'config' / 'config.yaml'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config
import logging

class FloodPredictor:
    """Flood risk prediction model for production deployment"""
    
    def __init__(self, site_id, model_path=None):
        self.logger = logging.getLogger(__name__)
        self.site_id = site_id
        self.model = None
        self.scaler = None
        self.feature_names = None
        
        if model_path:
            self.load_model(model_path)
    
    def load_model(self, model_path):
        """Load trained model, scaler, and metadata"""
        model_path = Path(model_path)

        self.model = joblib.load(model_path)
        print(f"\nModel loaded from {model_path}")

        scaler_path = model_path.parent / model_path.name.replace('model', 'scaler')
        
        features_path = model_path.parent / model_path.name.replace('model.pkl', 'features.json')
    
    def predict_risk(self, current_data):
        """ Predict flood risk probability for new data """
        
        if self.feature_names:
            missing_features = set(self.feature_names) - set(current_data.columns)
            if missing_features:
                raise ValueError(f"Missing required features for site {self.site_id}: {missing_features}")
            X = current_data[self.feature_names].copy()
        else:
            X = current_data.select_dtypes(include=[np.number]).copy()
            self.logger.warning(f"Using all {len(X.columns)} numeric columns (no feature names available)")
        
        X = X.fillna(0)
        X = X.replace([np.inf, -np.inf], 0)
        
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values
        
        # predict probability of flood event (class 1)
        risk_proba = self.model.predict_proba(X_scaled)[:, 1]
        
        return risk_proba
    
    def get_alert_level(self, risk_score, thresholds=None):
        """ Convert risk score to alert level """
        if thresholds is None:
            thresholds = {
                'LOW': 0.3,
                'MODERATE': 0.5,
                'HIGH': 0.7,
                'SEVERE': 0.9
            }
        
        if risk_score >= thresholds['SEVERE']:
            return 'SEVERE'
        elif risk_score >= thresholds['HIGH']:
            return 'HIGH'
        elif risk_score >= thresholds['MODERATE']:
            return 'MODERATE'
        elif risk_score >= thresholds['LOW']:
            return 'LOW'
        else:
            return 'NONE'

# training a specific model
def train_flood_model(site_id='07374000', model_type='RandomForest'):
    """
    Train flood prediction model for a specific USGS monitoring site
    """
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'flood_training.log'))
    logger = logging.getLogger(__name__)
    
    config = load_config(str(config_file))

    print(f"FLOOD MODEL TRAINING - Site {site_id}")
    
    print(f"Project root: {project_root}")
    
    input_file = project_root / 'data' / 'processed' / f'flood_features_{site_id}.csv'
    
    print(f"\nLoading data from {input_file}")
    df = pd.read_csv(input_file)
    
    if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date']).reset_index(drop=True)
    
    print(f"Loaded {len(df):,} records for site {site_id}")
    
    target_col = 'target_flood_next_7d'
    if target_col not in df.columns:
        logger.error(f"Target column '{target_col}' missing in data for site {site_id}")
        return None
    
    unique_classes = df[target_col].dropna().unique()
    print(f"Target class distribution: {df[target_col].value_counts().to_dict()}")
    
    if len(unique_classes) < 2:
        logger.warning(f"Site {site_id} has only ONE class in target ({unique_classes}). Skipping training.")
        return None
    
    exclude_cols = [
        'date', 'discharge', 'season', 'is_flood', 'flood_threshold', 
        'flood_severity', 'flood_event_id', 'year', 'month', 'day', 
        'day_of_week', 'day_of_year', 'week_of_year', 'quarter',
        target_col, 'site_name', 'site_id'
    ]
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [col for col in numeric_cols if col not in exclude_cols and col != target_col]
    
    print(f"Using {len(feature_cols)} NUMERIC features")
    
    X = df[feature_cols].copy()
    y = df[target_col].copy()

    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    y = y.fillna(0).astype(int)
    
    split_idx = int(len(X) * (1 - config['flood']['training']['test_size']))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    train_classes = np.unique(y_train)
    if len(train_classes) < 2:
        print(f"\nTraining set for site {site_id} has only ONE class ({train_classes}). Skipping training.")
        return None
    
    test_positives = y_test.sum()
    if test_positives == 0:
        print(f"\nTest set for site {site_id} has ZERO positive samples (all negatives). "
                      "Evaluation metrics will be limited.")
    
    print(f"Train set: {len(X_train):,} samples ({y_train.mean():.3%} flood events)")
    print(f"Test set: {len(X_test):,} samples ({y_test.mean():.3%} flood events)")

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # initialize model
    model = RandomForestClassifier(
        n_estimators=config['models']['flood']['n_estimators'],
        max_depth=config['models']['flood']['max_depth'],
        random_state=config['flood']['training']['random_state'],
        min_samples_split=10,
        min_samples_leaf=5,
        n_jobs=-1,
        class_weight='balanced'  # handle class imbalance
    )
    
    print(f"\nTraining {model.__class__.__name__}...")
    model.fit(X_train_scaled, y_train)
    
    # evaluate
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_proba) if len(np.unique(y_test)) > 1 else 0.0
    
     
    print("\nTEST SET PERFORMANCE")
    
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"ROC AUC:   {roc_auc:.4f}")
    
    print("\nClassification Report:")
    report = classification_report(
        y_test, 
        y_pred, 
        labels=[0, 1],  # always show both classes
        target_names=['No Flood', 'Flood Event'],
        zero_division=0
    )
    print(report)
    
    models_dir = project_root / 'models'
    models_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    model_path = models_dir / f'flood_risk_model_{site_id}_{timestamp}.pkl'
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    scaler_path = models_dir / f'flood_scaler_{site_id}_{timestamp}.pkl'
    joblib.dump(scaler, scaler_path)
    print(f"Scaler saved to {scaler_path}")
    
    # evaluation results
    eval_results = {
        'site_id': site_id,
        'site_name': config['flood']['monitoring_sites'].get(site_id, 'Unknown'),
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'roc_auc': float(roc_auc),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'test_positives': int(test_positives),
        'model_type': model.__class__.__name__,
        'features_used': feature_cols,
        'training_date': datetime.now().isoformat()
    }
    
    predictor = FloodPredictor(site_id=site_id)
    predictor.model = model
    predictor.scaler = scaler
    predictor.feature_names = feature_cols
    
    
    print("\nTRAINING COMPLETE!")
    
    
    return predictor

def train_all_flood_sites():
    """Train models for all monitoring sites defined in config"""
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'flood_training.log'))
    logger = logging.getLogger(__name__)
    
    config = load_config(str(config_file))
    
    monitoring_sites = config['flood']['monitoring_sites']
    print(f"Training flood models for {len(monitoring_sites)} sites...")
    
    predictors = {}
    failed_sites = []
    
    for site_id, site_name in monitoring_sites.items():
        print(f"\nTraining model for site {site_id}: {site_name}")
        
        try:
            predictor = train_flood_model(site_id=site_id, model_type='RandomForest')
            if predictor:
                predictors[site_id] = predictor
                print(f"Successfully trained model for {site_id}")
            else:
                failed_sites.append((site_id, "Insufficient class diversity"))
                logger.warning(f"Skipped training for {site_id} (insufficient class diversity)")
        except Exception as e:
            failed_sites.append((site_id, str(e)))
            logger.error(f"Failed to train model for {site_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    print(f"\nTRAINING SUMMARY")
    print(f"Successful: {len(predictors)}/{len(monitoring_sites)} sites")
    print(f"Failed: {len(failed_sites)}/{len(monitoring_sites)} sites")
    
    for site_id, reason in failed_sites:
        print(f"  - {site_id}: {reason}")
    
    return predictors

if __name__ == "__main__":
    print(f"Project root: {project_root}")
    
    config = load_config(str(project_root / "config" / "config.yaml"))
    
    print(f"Config file exists: {config_file.exists()}")
    
    try:
        predictors = train_all_flood_sites()
        success_count = len(predictors)
        total_sites = len(config['flood']['monitoring_sites'])
        print(f"\nSuccessfully trained models for {success_count}/{total_sites} sites!")
        print(f"Models saved to: {project_root / 'models'}")
        
        if success_count < total_sites:
            print(f"\n{total_sites - success_count} sites skipped due to insufficient flood events in data.")
            print("Check logs for details - this is common for sites with rare flooding.")
    except Exception as e:
        print(f"\nTraining failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)