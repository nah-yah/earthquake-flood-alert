# src/collectors/usgs_flood.py
import pandas as pd
from dataretrieval import nwis
from datetime import datetime, timedelta
import logging
import time
import sys
import os

# import path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

class USGSFloodCollector:
    """
    Collect streamflow and river level data from USGS Water Data
    """
    
    def __init__(self, monitoring_sites=None):

        self.monitoring_sites = monitoring_sites
        self.logger = logging.getLogger(__name__)
   
    def fetch_daily_values(self, site_id, start_date, end_date):
        """
        Fetch daily streamflow values
        """
        try:
            self.logger.info(f"Fetching daily values for site {site_id}: {start_date} to {end_date}")
            
            df = nwis.get_record(
                sites=site_id,
                service='dv',  # daily values
                start=start_date,
                end=end_date,
                parameterCd='00060,00065'  # discharge and gage height
            )
            
            # rename columns for easier handling
            df = df.reset_index()
            df.columns = ['date'] + list(df.columns[1:])
            
            self.logger.info(f"Fetched {len(df)} daily records")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching daily data for {site_id}: {e}")
            return None
    
    def fetch_all_sites(self, start_date, end_date):
        all_data = {} # container to aggragate all the datasets
        
        for site_id, site_name in self.monitoring_sites.items():
            self.logger.info(f"Fetching data for {site_name}...")
            df = self.fetch_daily_values(site_id, start_date, end_date)
            
            if df is not None:
                df['site_name'] = site_name
                df['site_id'] = site_id
                all_data[site_id] = df
            
            # API rate limits
            time.sleep(1)
        
        # report completion summary
        self.logger.info(f"Completed data collection: {len(all_data)}/{len(self.monitoring_sites)} sites fetched successfully")
        return all_data

    def save_data(self, df, filename):

        if df is None or df.empty:
            self.logger.warning("No data to save")
            return
        
        filepath = f"data/raw/floods/{filename}"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        df.to_csv(filepath, index=False)
        self.logger.info(f"Saved to {filepath}")

if __name__ == "__main__":
    from src.utils.helpers import setup_logging, load_config
    
    setup_logging()
    config = load_config()
    
    monitoring_sites = config['flood']['monitoring_sites']
    collector = USGSFloodCollector(monitoring_sites)
    
    # fetch data for all sites
    print("Fetching flood data for all monitoring sites...")
    all_data = collector.fetch_all_sites(
        start_date=config['flood']['training']['start_date'],
        end_date=config['flood']['training']['end_date']
    )
    
    # save each site data
    for site_id, df in all_data.items():
        site_name = monitoring_sites[site_id].replace(' ', '_').replace(',', '')
        collector.save_data(df, f"{site_id}_{site_name}_training.csv")