# src/data_processing/flood_features.py
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os
import logging

try:
    project_root = Path(__file__).resolve().parents[2]
except NameError:
    project_root = Path.cwd()
    if project_root.name in ['src', 'data_processing']:
        project_root = project_root.parents[1]

sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config

class FloodFeatureEngineering:
    """Advanced feature engineering for flood prediction"""
    
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
    
    def create_temporal_features(self, df):
        """Create temporal pattern features with cyclical encoding"""
        print("\nCreating temporal features...")
        
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        df['day_of_year_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
        df['day_of_year_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
        
        season_map = {'winter': 0, 'spring': 1, 'summer': 2, 'fall': 3}
        df['season_encoded'] = df['season'].map(season_map).fillna(-1).astype(int)
        
        print("Added temporal features")
        return df
    
    def create_statistical_features(self, df):
        """Create statistical features from discharge"""
        print("\nCreating statistical features...")
        
        for percentile in [25, 50, 75, 90, 95, 99]:
            threshold = df['discharge'].quantile(percentile / 100)
            df[f'above_p{percentile}'] = (df['discharge'] > threshold).astype(int)
        
        df['discharge_zscore'] = (df['discharge'] - df['discharge'].mean()) / (df['discharge'].std() + 1e-6)
        
        # moving statistics ratios
        df['discharge_to_7d_mean'] = df['discharge'] / (df['discharge_rolling_mean_7d'] + 1e-6)
        df['discharge_to_30d_mean'] = df['discharge'] / (df['discharge_rolling_mean_30d'] + 1e-6)
        
        print("Added statistical features")
        return df
    
    def create_trend_features(self, df):
        """Create trend and momentum features"""
        print("\nCreating trend features...")
        
        # rate of change
        df['discharge_pct_change_1d'] = df['discharge'].pct_change(1).fillna(0)
        df['discharge_pct_change_7d'] = df['discharge'].pct_change(7).fillna(0)
        
        # acceleration
        df['discharge_acceleration'] = df['discharge_change_1d'].diff(1).fillna(0)
        
        # trend direction
        df['discharge_trend_7d'] = np.where(df['discharge_change_7d'] > 0, 1, -1)
        df['discharge_trend_14d'] = np.where(df['discharge'].diff(14) > 0, 1, -1)
        
        # volatility
        df['discharge_volatility_7d'] = df['discharge'].rolling(window=7, min_periods=1).std().fillna(0)
        df['discharge_volatility_30d'] = df['discharge'].rolling(window=30, min_periods=1).std().fillna(0)
        
        print("Added trend features")
        return df
    
    def create_extreme_event_features(self, df):
        """Features related to extreme events"""
        print("\nCreating extreme event features...")
        
        # days since last flood event (vectorized)
        df = df.sort_values('date').reset_index(drop=True)
        flood_mask = df['is_flood'] == 1
        
        # create cumulative count of flood events
        df['flood_cumcount'] = flood_mask.cumsum()
        
        # days since last flood = current index - index of last flood event
        df['days_since_last_flood'] = df.groupby('flood_cumcount').cumcount()
        
        # for days before first flood, set to large number
        df.loc[df['flood_cumcount'] == 0, 'days_since_last_flood'] = 999
        
        # clean up temporary column
        df = df.drop(columns=['flood_cumcount'])
        
        # consecutive days above threshold (95th percentile)
        threshold_95 = df['discharge'].quantile(0.95)
        above_threshold = (df['discharge'] > threshold_95).astype(int)
        
        # group consecutive days above threshold
        groups = (above_threshold != above_threshold.shift()).cumsum()
        df['consecutive_high_days'] = above_threshold.groupby(groups).cumsum()
        
        print("Added extreme event features")
        return df
    
    def create_target_variable(self, df, prediction_window_days=7):
        """
        Create target variable: Will there be a flood in the next N days?
        """
        print(f"\nCreating target variable (window: {prediction_window_days} days)...")
        
        df = df.sort_values('date').reset_index(drop=True)
        
        # vectorized target creation
        df['target_flood_next_7d'] = (
            df['is_flood']
            .rolling(window=prediction_window_days, min_periods=1)
            .max()
            .shift(-prediction_window_days + 1)
            .fillna(0)
            .astype(int)
        )
        
        # handle last prediction_window_days rows (no future data)
        df.loc[df.index >= len(df) - prediction_window_days, 'target_flood_next_7d'] = 0
        
        positive_rate = df['target_flood_next_7d'].mean()
        print(f"Target created. Positive rate: {positive_rate:.3f} ({df['target_flood_next_7d'].sum():,} / {len(df):,})")
        
        return df

def engineer_flood_features(site_id='07374000'):
    """Main function to engineer flood features for a specific site"""
    
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'flood_feature_engineering.log'))
    logger = logging.getLogger(__name__)
    
    config_file = project_root / 'config' / 'config.yaml'
    config = load_config(str(config_file))
    
    print(f"FLOOD FEATURE ENGINEERING - Site {site_id}")
    
    # load cleaned data using project_root
    input_file = project_root / 'data' / 'processed' / f'flood_cleaned_{site_id}.csv'
    
    if not input_file.exists():
        print(f"Cleaned data not found: {input_file}")
        print("Run flood_cleaner.py first")
        return None
    
    print(f"Loading data from {input_file}")
    df = pd.read_csv(input_file)
    
    # ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date']).reset_index(drop=True)
    
    print(f"Loaded {len(df):,} cleaned records")
    
    # engineer features
    engineer = FloodFeatureEngineering(config)
    
    df = engineer.create_temporal_features(df)
    df = engineer.create_statistical_features(df)
    df = engineer.create_trend_features(df)
    df = engineer.create_extreme_event_features(df)
    df = engineer.create_target_variable(df, prediction_window_days=7)
    
    # remove rows with NaN
    initial_rows = len(df)
    df = df.dropna().reset_index(drop=True)
    print(f"Dropped {initial_rows - len(df):,} NaN rows")
    
    print(f"\nFinal shape: {df.shape}")

    # save feature-engineered data
    processed_dir = project_root / 'data' / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_file = processed_dir / f'flood_features_{site_id}.csv'
    
    df.to_csv(output_file, index=False)
    print(f"\nSaved to {output_file}")
    
    # print summary
    print(f"\nFEATURE SUMMARY - SITE {site_id}")
    print(f"Total features: {len(df.columns)}")
    print(f"Total samples: {len(df):,}")
    print(f"Target distribution:\n{df['target_flood_next_7d'].value_counts()}")
    print(f"Positive rate: {df['target_flood_next_7d'].mean():.3f}")
    
    return df

def engineer_all_flood_sites():
    """Engineer features for all monitoring sites defined in config"""
    setup_logging(str(project_root / 'logs' / 'flood_feature_engineering.log'))
    logger = logging.getLogger(__name__)
    
    config_file = project_root / 'config' / 'config.yaml'
    config = load_config(str(config_file))
    
    monitoring_sites = config['flood']['monitoring_sites']
    print(f"Engineering features for {len(monitoring_sites)} sites...")
    
    results = {}
    for site_id, site_name in monitoring_sites.items():
        print(f"\nProcessing site {site_id}: {site_name}")
        
        df = engineer_flood_features(site_id)
        if df is not None:
            results[site_id] = df
            print(f"Successfully engineered features for {site_id}")
        else:
            print(f"Failed for {site_id}")
    
    print(f"\nCOMPLETE: {len(results)}/{len(monitoring_sites)} sites processed")
    
    return results

if __name__ == "__main__":
    engineer_all_flood_sites()