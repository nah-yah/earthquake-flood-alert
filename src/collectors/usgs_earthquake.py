# src/collectors/usgs_earthquake.py
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import logging
from io import StringIO
import sys
import os

# import path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

class USGSEarthquakeCollector:
    """
    Collect earthquake data from USGS Earthquake Catalog
    API Documentation: https://earthquake.usgs.gov/fdsnws/event/1/
    """
    
    def __init__(self):
        # primary API endpoint for historical queries
        self.base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        # pre-agrageted feeds for recent events
        self.feed_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/"
        self.logger = logging.getLogger(__name__)
        
    def fetch_realtime(self, timeframe='day', min_magnitude=2.5):
        url = f"{self.feed_url}all_{timeframe}.csv"
        
        try:
            self.logger.info(f"Fetching real-time earthquakes from last {timeframe}...")
            df = pd.read_csv(url)
            df['time'] = pd.to_datetime(df['time'])
            df = df[df['mag'] >= min_magnitude]
            
            self.logger.info(f"Fetched {len(df)} earthquakes (mag >= {min_magnitude})")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return None
    

    def fetch_by_region(self, min_lat, max_lat, min_lon, max_lon, 
                       start_date, end_date, min_magnitude=2.5):
        params = {
            'format': 'csv',
            'starttime': start_date,
            'endtime': end_date,
            'minmagnitude': min_magnitude,
            'minlatitude': min_lat,
            'maxlatitude': max_lat,
            'minlongitude': min_lon,
            'maxlongitude': max_lon,
            'orderby': 'time'
        }
        
        try:
            self.logger.info(f"Fetching earthquakes for region: lat[{min_lat},{max_lat}], lon[{min_lon},{max_lon}]")
            response = requests.get(self.base_url, params=params, timeout=60)
            response.raise_for_status()
            
            df = pd.read_csv(StringIO(response.text))
            df['time'] = pd.to_datetime(df['time'])
            
            self.logger.info(f"Fetched {len(df)} regional earthquakes")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching regional data: {e}")
            return None
    
    def save_data(self, df, filename):
        """Save earthquake data to CSV"""
        if df is None or df.empty:
            self.logger.warning("No data to save")
            return
        
        filepath = f"data/raw/earthquakes/{filename}"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        df.to_csv(filepath, index=False)
        self.logger.info(f"Saved to {filepath}")

if __name__ == "__main__":
    from src.utils.helpers import setup_logging, load_config
    
    setup_logging()
    config = load_config()
    
    collector = USGSEarthquakeCollector()
    
    # fetch recent earthquakes
    print("Fetching recent earthquakes...")
    recent = collector.fetch_realtime('day', min_magnitude=4.0)
    if recent is not None:
        print(f"\nFound {len(recent)} earthquakes in the last day")
        print(recent[['time', 'mag', 'place']].head())
        collector.save_data(recent, f"realtime_{datetime.now().strftime('%Y%m%d')}.csv")
    
    # quick fetch o significant recent events
    # California is the most seismically active US state
    print("\n\nFetching California historical data...")
    ca_config = config['earthquake']['regions']['california']
    ca_data = collector.fetch_by_region(
        min_lat=ca_config['min_lat'],
        max_lat=ca_config['max_lat'],
        min_lon=ca_config['min_lon'],
        max_lon=ca_config['max_lon'],
        start_date=config['earthquake']['training']['start_date'],
        end_date=config['earthquake']['training']['end_date'],
        min_magnitude=config['earthquake']['min_magnitude']
    )
    
    if ca_data is not None:
        print(f"\nFound {len(ca_data)} California earthquakes")
        print(ca_data[['time', 'mag', 'depth', 'place']].head())
        collector.save_data(ca_data, "california_training_data.csv")