# src/utils/helpers.py

import yaml
import os
import pandas as pd
import numpy as np
from datetime import datetime
import logging

def setup_logging(log_file='logs/system.log'):
    # handle relative paths safely
    if not os.path.isabs(log_file):
        # try to find project root (navigate up from src/utils/)
        current = os.path.dirname(os.path.abspath(__file__))
        project_root = None # initialize the variable
        for _ in range(3):  # src/utils/ → src/ → project_root
            current = os.path.dirname(current)
            if os.path.exists(os.path.join(current, 'config', 'config.yaml')):
                project_root = current
                break
        
        if project_root:
            log_file = os.path.join(project_root, log_file)
        else:
            # fallback to current directory
            log_file = os.path.join(os.getcwd(), log_file)
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True) # create the directory structure for the log file if it doesn't already exist
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_config(config_path='config/config.yaml'):
    """Load configuration from YAML file with robust path handling"""
    if not os.path.isabs(config_path):
        # try to find project root
        current = os.path.dirname(os.path.abspath(__file__))
        project_root = None
        for _ in range(3):  # src/utils/ → src/ → project_root
            current = os.path.dirname(current)
            config_candidate = os.path.join(current, config_path)
            if os.path.exists(config_candidate):
                config_path = config_candidate
                project_root = current
                break
        
        if not os.path.exists(config_path):
            # final fallback: check current working directory
            cwd_config = os.path.join(os.getcwd(), config_path)
            if os.path.exists(cwd_config):
                config_path = cwd_config
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def save_dataframe(df, filepath, description=""):
    """Save DataFrame with logging"""
    logger = logging.getLogger(__name__)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    df.to_csv(filepath, index=False)
    logger.info(f"Saved {description}: {filepath} ({len(df)} records)")

def load_dataframe(filepath):
    """Load DataFrame with error handling"""
    logger = logging.getLogger(__name__)
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {filepath} ({len(df)} records)")
        return df
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return None

def calculate_time_features(df, time_column='time'):
    # standardize to datetime
    df[time_column] = pd.to_datetime(df[time_column])
    
    # calendar components
    df['year'] = df[time_column].dt.year
    df['month'] = df[time_column].dt.month     # 1–12
    df['day'] = df[time_column].dt.day         # 1–31
    df['hour'] = df[time_column].dt.hour       # 0–23 (NaN if no time)
    
    # cyclical/ordinal features
    df['day_of_week'] = df[time_column].dt.dayofweek    # Monday=0, Sunday=6
    df['day_of_year'] = df[time_column].dt.dayofyear    # 1–366
    # ISO week numbering
    df['week_of_year'] = df[time_column].dt.isocalendar().week.astype(int)
    
    return df

def calculate_rolling_features(df, column, windows=[7, 14, 30]):
    """Calculate rolling statistics"""
    for window in windows:
        df[f'{column}_rolling_mean_{window}d'] = df[column].rolling(window=window, min_periods=1).mean()
        df[f'{column}_rolling_std_{window}d'] = df[column].rolling(window=window, min_periods=1).std()
        df[f'{column}_rolling_max_{window}d'] = df[column].rolling(window=window, min_periods=1).max()
        df[f'{column}_rolling_min_{window}d'] = df[column].rolling(window=window, min_periods=1).min()
    return df

def create_lag_features(df, column, lags=[1, 2, 3, 7, 14]):
    """Create lag for autoregressive features"""
    for lag in lags:
        df[f'{column}_lag_{lag}'] = df[column].shift(lag)
    return df

class DataValidator:
    """Validate data quality"""
    
    @staticmethod
    def check_missing_values(df, threshold=0.6):
        # percentage of missing values
        missing_pct = df.isnull().sum() / len(df)
        # alert if columns exceed missingness threshold
        problematic_cols = missing_pct[missing_pct > threshold]
        
        if len(problematic_cols) > 0:
            print(f"Warning: {len(problematic_cols)} columns have >{threshold*100}% missing values:")
            print(problematic_cols)
        
        return problematic_cols

    @staticmethod
    def check_duplicates(df):
        """Check for duplicate rows"""
        duplicates = df.duplicated().sum()
        if duplicates > 0:
            print(f"Warning: Found {duplicates} duplicate rows")
        return duplicates

    @staticmethod
    def check_date_range(df, date_column, expected_start=None, expected_end=None):
        """Validate date range"""
        df[date_column] = pd.to_datetime(df[date_column])
        actual_start = df[date_column].min()
        actual_end = df[date_column].max()
        
        print(f"Date range: {actual_start} to {actual_end}")
        
        if expected_start and actual_start > pd.to_datetime(expected_start):
            print(f"Warning: Start date later than expected")
        
        if expected_end and actual_end < pd.to_datetime(expected_end):
            print(f"Warning: End date earlier than expected")
        
        return actual_start, actual_end

if __name__ == "__main__":
    # isolated test block to avoid circular imports during normal usage
    setup_logging('logs/helpers_test.log')
    logger = logging.getLogger(__name__)
    
    try:
        config = load_config('config/config.yaml')
        logger.info(f"Config loaded successfully")
        logger.info(f"Earthquake min magnitude: {config['earthquake']['min_magnitude']}")
        logger.info(f"Significant magnitude: {config['earthquake']['significant_magnitude']}")
    except Exception as e:
        logger.error(f"Error loading config: {e}")