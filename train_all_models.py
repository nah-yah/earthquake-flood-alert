# train_all_models.py

import sys
from pathlib import Path
import logging

project_root = Path(__file__).resolve().parents[0]

config_file = project_root / 'config' / 'config.yaml'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config

def run_complete_pipeline():
    """Run the complete training pipeline"""
    
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'complete_pipeline.log'))
    logger = logging.getLogger(__name__)
    
    config = load_config(str(config_file))
    
    print("\nSTARTING COMPLETE MODEL TRAINING PIPELINE")
    print(f"Project root: {project_root}")
    
    # step 1: data cleaning
    print("STEP 1: DATA CLEANING")
    
    # clean earthquake data
    print("\nEarthquake data")
    try:
        from src.utils.earthquake_cleaner import clean_earthquake_data
        eq_clean = clean_earthquake_data()
        if eq_clean is None:
            print("Earthquake data cleaning failed!")
            return False
        print("Earthquake data cleaning completed successfully")
    except Exception as e:
        print(f"Earthquake cleaning failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # clean flood data
    print("\nFlood data")
    try:
        from src.utils.flood_cleaner import clean_all_flood_sites
        flood_results = clean_all_flood_sites()
        if not flood_results:
            print("Flood data cleaning failed for all sites!")
            return False
        print(f"Flood data cleaning completed for {len(flood_results)} sites")
    except Exception as e:
        print(f"Flood cleaning failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # step 2: feature engineering
    print("STEP 2: FEATURE ENGINEERING")
    
    # earthquake features
    print("\nEarthquake features")
    try:
        from src.utils.earthquake_features import engineer_earthquake_features
        eq_features = engineer_earthquake_features()
        if eq_features is None:
            print("Earthquake feature engineering failed!")
            return False
        print("Earthquake feature engineering completed successfully")
    except Exception as e:
        print(f"Earthquake feature engineering failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # flood features
    print("\nFlood features")
    try:
        from src.utils.flood_features import engineer_all_flood_sites
        flood_features = engineer_all_flood_sites()
        if not flood_features:
            print("Flood feature engineering failed for all sites!")
            return False
        print(f"OK Flood feature engineering completed for {len(flood_features)} sites")
    except Exception as e:
        print(f"Flood feature engineering failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # step 3: model training
    print("STEP 3: MODEL TRAINING")
    
    # earthquake model
    print("\nEarthquake model")
    try:
        from src.predictors.earthquake_predictor import train_earthquake_model
        eq_predictor = train_earthquake_model()
        if eq_predictor is None:
            print("Earthquake model training failed!")
            return False
        print("Earthquake model training completed successfully")
    except Exception as e:
        print(f"Earthquake model training failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    # flood models
    print("\nFlood models")
    try:
        from src.predictors.flood_predictor import train_all_flood_sites
        flood_predictors = train_all_flood_sites()
        if not flood_predictors:
            print("Flood model training failed for all sites!")
            return False
        print(f"Flood model training completed for {len(flood_predictors)} sites")
    except Exception as e:
        print(f"Flood model training failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    print("COMPLETE PIPELINE FINISHED SUCCESSFULLY!")
    print("\nAll models have been trained and saved to the 'models' directory.")
    print("Check the 'data' directory for evaluation plots and metrics.")
    
    return True

if __name__ == "__main__":
    success = run_complete_pipeline()
    sys.exit(0 if success else 1)