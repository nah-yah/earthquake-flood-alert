# src/data_processing/flood_cleaner.py

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

class FloodDataCleaner:
    """Clean and preprocess flood/streamflow data"""
    
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
    def clean_data(self, df, site_id):
        print(f"\nStarting data cleaning for site {site_id}...")
        
        original_rows = len(df)
        
        # parse date column to datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])
        
        # find discharge column
        discharge_cols = [col for col in df.columns if '00060' in col and 'Mean' in col]
        if not discharge_cols:
            # look for any discharge-related column
            discharge_cols = [col for col in df.columns if 'discharge' in col.lower() or 'streamflow' in col.lower()]
        
        if not discharge_cols:
            self.logger.error("No discharge column found!")
            return None
        
        discharge_col = discharge_cols[0]
        print(f"Using discharge column: {discharge_col}")
        
        # rename for easier handling
        df = df.rename(columns={discharge_col: 'discharge'})
        
        # remove duplicates
        duplicates = df.duplicated(subset=['date'], keep='first')
        if duplicates.any():
            print(f"\nRemoving {duplicates.sum()} duplicate dates")
            df = df[~duplicates].reset_index(drop=True)
        
        # sort by date
        df = df.sort_values('date').reset_index(drop=True)
        
        # handle missing values in discharge
        missing_count = df['discharge'].isnull().sum()
        if missing_count > 0:
            print(f"\nMissing discharge values: {missing_count} ({missing_count/len(df)*100:.2f}%)")
            
            df_temp = df.set_index('date')
            
            # interpolate short gaps (<7 days) using time-based interpolation
            max_gap_days = self.config.get('flood', {}).get('max_interpolation_gap_days', 7)
            df_temp['discharge'] = df_temp['discharge'].interpolate(
                method='time',
                limit=max_gap_days,
                limit_direction='both'
            )
            # reset index back to default
            df = df_temp.reset_index()
            
            # fill remaining NaN at edges with forward/backward fill
            remaining_missing = df['discharge'].isnull().sum()
            if remaining_missing > 0:
                df['discharge'] = df['discharge'].fillna(method='ffill').fillna(method='bfill')
        
        # remove negative discharge values
        df.loc[df['discharge'] < 0, 'discharge'] = 0
        
        # remove extreme outliers
        p99 = df['discharge'].quantile(0.99)
        extreme_threshold = p99 * 10
        extreme_mask = df['discharge'] > extreme_threshold
        df = df[~extreme_mask].reset_index(drop=True)
        
        print(f"\nCleaning complete. Final rows: {len(df):,} (from original {original_rows:,})")
        
        return df
    
    def add_derived_features(self, df):
        """Add useful derived features"""
        print("\nAdding derived features...")
        
        # time-based features
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        df['day'] = df['date'].dt.day
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_year'] = df['date'].dt.dayofyear
        df['week_of_year'] = df['date'].dt.isocalendar().week.astype(int)
        df['quarter'] = df['date'].dt.quarter
        
        # season
        df['season'] = df['month'].map({
            12: 'winter', 1: 'winter', 2: 'winter',
            3: 'spring', 4: 'spring', 5: 'spring',
            6: 'summer', 7: 'summer', 8: 'summer',
            9: 'fall', 10: 'fall', 11: 'fall'
        })
        
        # log-transformed discharge
        df['discharge_log'] = np.log1p(df['discharge'])  # log(1+x) handles zeros
        
        # rolling statistics (7, 14, 30 days)
        for window in [7, 14, 30]:
            df[f'discharge_rolling_mean_{window}d'] = df['discharge'].rolling(window=window, min_periods=1).mean()
            df[f'discharge_rolling_std_{window}d'] = df['discharge'].rolling(window=window, min_periods=1).std()
            df[f'discharge_rolling_max_{window}d'] = df['discharge'].rolling(window=window, min_periods=1).max()
            df[f'discharge_rolling_min_{window}d'] = df['discharge'].rolling(window=window, min_periods=1).min()
        
        # lag features (previous days)
        for lag in [1, 2, 3, 7, 14, 30]:
            df[f'discharge_lag_{lag}d'] = df['discharge'].shift(lag)
        
        # rate of change
        df['discharge_change_1d'] = df['discharge'].diff(1)
        df['discharge_change_7d'] = df['discharge'].diff(7)
        
        # percentile rank
        df['discharge_percentile'] = df['discharge'].rank(pct=True)
        
        print(f"Added derived features")
        
        return df
    
    def create_flood_labels(self, df, threshold_percentile=95):
        """Create flood event labels based on configurable percentile threshold"""
        print(f"\nCreating flood labels (threshold: {threshold_percentile}th percentile)...")
        
        threshold = df['discharge'].quantile(threshold_percentile / 100)
        
        df['is_flood'] = (df['discharge'] > threshold).astype(int)
        df['flood_threshold'] = threshold
        df['flood_severity'] = ((df['discharge'] - threshold) / threshold).clip(lower=0)
        
        # identify continuous flood events
        df['flood_event_id'] = (df['is_flood'] != df['is_flood'].shift()).cumsum()
        
        flood_count = df['is_flood'].sum()
        print(f"Identified {flood_count:,} flood events ({flood_count/len(df)*100:.2f}%)")
        print(f"Flood threshold: {threshold:,.2f} cfs")
        
        return df

def clean_flood_data(site_id='07374000'):
    """Main function to clean flood data for a specific site"""
    
    # setup logging
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'flood_cleaning.log'))
    logger = logging.getLogger(__name__)
    
    # load config
    config_file = project_root / 'config' / 'config.yaml'
    config = load_config(str(config_file))
    
    print("\n")
    print(f"FLOOD DATA CLEANING - Site {site_id}")
    
    # find raw data file
    raw_dir = project_root / 'data' / 'raw' / 'floods'
    raw_files = list(raw_dir.glob(f"{site_id}*.csv"))
    
    if not raw_files:
        print(f"\nNo raw data file found for site {site_id}")
        print("Run flood collector first")
        return None
    
    raw_file = raw_files[0]
    print(f"\nLoading data from {raw_file}")
    df = pd.read_csv(raw_file)
    print(f"Loaded {len(df):,} raw records")
    
    # clean data
    cleaner = FloodDataCleaner(config)
    df_clean = cleaner.clean_data(df, site_id)
    
    if df_clean is None:
        return None
    
    df_clean = cleaner.add_derived_features(df_clean)
    df_clean = cleaner.create_flood_labels(
        df_clean, 
        threshold_percentile=config['flood']['flood_threshold_percentile']
    )
    
    # Save cleaned data
    processed_dir = project_root / 'data' / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_file = processed_dir / f'flood_cleaned_{site_id}.csv'

    df_clean.to_csv(output_file, index=False)
    logger.info(f"Saved to {output_file}")
    
    # Print summary
    print(f"\nCLEANING SUMMARY - SITE {site_id}")
    print(f"Original records: {len(df):,}")
    print(f"Cleaned records: {len(df_clean):,}")
    print(f"Flood events: {df_clean['is_flood'].sum():,}")
    print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()}")
    print(f"Discharge range: {df_clean['discharge'].min():,.2f} - {df_clean['discharge'].max():,.2f} cfs")
    
    return df_clean

def clean_all_flood_sites():
    """Clean data for all monitoring sites defined in config"""
    setup_logging(str(project_root / 'logs' / 'flood_cleaning.log'))
    logger = logging.getLogger(__name__)
    
    config_file = project_root / 'config' / 'config.yaml'
    config = load_config(str(config_file))

    monitoring_sites = config['flood']['monitoring_sites']
    print(f"\nCleaning data for {len(monitoring_sites)} monitoring sites...")
    
    results = {}
    for site_id, site_name in monitoring_sites.items():
        print(f"\nProcessing site {site_id}: {site_name}")
        
        df = clean_flood_data(site_id)
        if df is not None:
            results[site_id] = df
            print(f"Successfully cleaned {site_id}")
        else:
            print(f"Failed to clean {site_id}")
    
    print(f"\nCOMPLETE: {len(results)}/{len(monitoring_sites)} sites processed")
    
    return results

if __name__ == "__main__":
    clean_all_flood_sites()