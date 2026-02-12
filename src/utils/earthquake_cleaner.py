# src/data_processing/earthquake_cleaner.py
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
    while project_root.name != 'earthquake-flood-alert' and project_root != project_root.parent:
        project_root = project_root.parent

config_file = project_root / 'config' / 'config.yaml'

# add project root to Python path before importing project modules
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config, DataValidator, save_dataframe

class EarthquakeDataCleaner:
    """Clean and preprocess earthquake data"""
    
    def __init__(self, config=None):
        self.config = config or {}
        
    def clean_data(self, df):
        print("\nStarting data cleaning...")
        
        original_rows = len(df)
        
        # remove duplicates
        df = df.drop_duplicates()
        after_dedup = len(df)  # fixed variable name to avoid overwriting original count
        
        # handle missing values in critical columns
        critical_cols = ['time', 'latitude', 'longitude', 'depth', 'mag']
        
        for col in critical_cols:
            missing = df[col].isnull().sum()
            if missing > 0:
                print(f"Missing values in {col}: {missing}")
        
        df = df.dropna(subset=critical_cols)
        print(f"After dropping missing critical values: {len(df)} rows (was {after_dedup})")
        
        # remove invalid magnitude values
        invalid_mag = (df['mag'] <= 0) | (df['mag'] > 10)  # no earthquake >9.5 historically
        if invalid_mag.any():
            print(f"Removing {invalid_mag.sum()} invalid magnitude values (<=0 or >10)")
            df = df[~invalid_mag]
        
        # remove invalid depth values
        invalid_depth = (df['depth'] < 0) | (df['depth'] > 700)  # deepest quakes ~700km
        if invalid_depth.any():
            print(f"Removing {invalid_depth.sum()} invalid depth values (<0 or >700km)")
            df = df[~invalid_depth]
        
        # ensure valid latitude/longitude
        invalid_lat = (df['latitude'] < -90) | (df['latitude'] > 90)
        invalid_lon = (df['longitude'] < -180) | (df['longitude'] > 180)
        invalid_geo = invalid_lat | invalid_lon
        
        if invalid_geo.any():
            print(f"Removing {invalid_geo.sum()} invalid geographic coordinates")
            df = df[~invalid_geo]
        
        # convert time to datetime (robust parsing)
        if not pd.api.types.is_datetime64_any_dtype(df['time']):
            df['time'] = pd.to_datetime(df['time'], errors='coerce', utc=True)
            
            # drop unparseable timestamps
            invalid_time = df['time'].isna()
            if invalid_time.any():
                print(f"Removing {invalid_time.sum()} rows with unparseable timestamps")
                df = df[~invalid_time]
        
        # sort by time
        df = df.sort_values('time').reset_index(drop=True)
        
        print(f"\nCleaning complete. Final rows: {len(df)} (from original {original_rows})")
        
        return df
    
    def add_derived_features(self, df):
        print("\nAdding derived features...")
        
        # time-based features
        df['year'] = df['time'].dt.year
        df['month'] = df['time'].dt.month
        df['day'] = df['time'].dt.day
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        df['day_of_year'] = df['time'].dt.dayofyear
        df['week_of_year'] = df['time'].dt.isocalendar().week.astype(int)
        
        # is significant earthquake (mag >= 5.0)
        significant_mag = self.config.get('earthquake', {}).get('significant_magnitude', 5.0)
        df['is_significant'] = (df['mag'] >= significant_mag).astype(int)
        
        # depth category
        df['depth_category'] = pd.cut(df['depth'], 
                                      bins=[0, 70, 300, 700],
                                      labels=['shallow', 'intermediate', 'deep'])
        
        # magnitude category
        df['mag_category'] = pd.cut(df['mag'],
                                    bins=[0, 4, 5, 6, 10],
                                    labels=['minor', 'light', 'moderate', 'strong'])
        
        print("Added derived features")
        
        return df
    
    def filter_outliers(self, df, columns=['mag', 'depth']):
        """Remove statistical outliers using IQR method"""
        print("\nFiltering outliers...")
        
        original_rows = len(df)
        
        for col in columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR
            
            mask = (df[col] >= lower_bound) & (df[col] <= upper_bound)
            removed = (~mask).sum()
            if removed > 0:
                print(f"Removed {removed} outliers from '{col}' (IQR bounds: {lower_bound:.2f}-{upper_bound:.2f})")
                df = df[mask]
        
        print(f"\nTotal outliers removed: {original_rows - len(df)}")
        
        return df

def clean_earthquake_data():
    """Main function to clean earthquake data"""
    
    # setup logging with absolute path and Windows-safe encoding
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    try:
        # try to reconfigure stdout to UTF-8 (Python 3.7+)
        import sys
        if sys.platform == 'win32':
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass 
    
    setup_logging(str(log_dir / 'earthquake_cleaning.log'))
    logger = logging.getLogger(__name__)  # main function retains logging for pipeline integration
    
    # load config with absolute path
    config = load_config(str(config_file))
    
    print("\n")
    print("EARTHQUAKE DATA CLEANING")
    
    # load raw data using project_root
    raw_file = project_root / 'data' / 'raw' / 'earthquakes' / 'california_training_data.csv'
    
    if not raw_file.exists():
        print(f"Raw data file not found: {raw_file}")
        print("Run notebooks/01_earthquake_exploration.py first to fetch data")
        return None
    
    print(f"Loading data from {raw_file}")
    df = pd.read_csv(raw_file)
    print(f"Loaded {len(df):,} raw records")
    
    # clean data
    cleaner = EarthquakeDataCleaner(config)
    df_clean = cleaner.clean_data(df)
    df_clean = cleaner.add_derived_features(df_clean)  # skipping outlier filtering (large events are critical signals)
    
    # save cleaned data
    processed_dir = project_root / 'data' / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_file = processed_dir / 'earthquake_cleaned.csv'
    
    save_dataframe(df_clean, str(output_file), "cleaned earthquake data")
    
    # print summary 
    print("\n")
    print("CLEANING SUMMARY")
    print(f"Original records: {len(df):,}")
    print(f"Cleaned records: {len(df_clean):,}")
    print(f"Retention rate: {len(df_clean)/len(df)*100:.1f}%")
    print(f"Significant earthquakes (mag >= {config['earthquake']['significant_magnitude']}): {df_clean['is_significant'].sum():,}")
    print(f"Date range: {df_clean['time'].min()} to {df_clean['time'].max()}")
    print(f"\nCleaned data saved to: {output_file}")
    
    return df_clean

if __name__ == "__main__":
    df = clean_earthquake_data()