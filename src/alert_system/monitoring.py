# src/alert_system/monitoring.py
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import joblib
import schedule
import time
from datetime import datetime, timedelta  # Ensure timedelta is imported
import logging

project_root = Path(__file__).resolve().parents[2] 

config_file = project_root / 'config' / 'config.yaml'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config
from src.collectors.usgs_earthquake import USGSEarthquakeCollector
from src.collectors.usgs_flood import USGSFloodCollector

try:
    from src.alert_system.alert_manager import AlertGenerator, AlertStorage 
except ImportError:
    class AlertLevel:
        NONE, LOW, MODERATE, HIGH, SEVERE = 0, 1, 2, 3, 4
    
    class Alert:
        def __init__(self, alert_type, level_value, message, location, timestamp=None):
            self.alert_type = alert_type
            self.level_value = level_value
            self.level_name = {0:'NONE',1:'LOW',2:'MODERATE',3:'HIGH',4:'SEVERE'}.get(level_value, 'UNKNOWN')
            self.message = message
            self.location = location
            self.timestamp = timestamp or datetime.now()
    
    class AlertGenerator:
        def __init__(self, config):
            self.config = config
            self.thresholds = config.get('alerts', {}).get('thresholds', {})
        
        def generate_earthquake_alert(self, probability, location, magnitude, depth):
            th = self.thresholds.get('earthquake', {'LOW':0.3,'MODERATE':0.5,'HIGH':0.7,'SEVERE':0.9})
            lvl = 4 if probability>=th['SEVERE'] else 3 if probability>=th['HIGH'] else 2 if probability>=th['MODERATE'] else 1 if probability>=th['LOW'] else 0
            if lvl == 0: return None
            msg = f"Earthquake Alert [{self._level_name(lvl)}] - M{magnitude:.1f} at {location} (depth: {depth:.1f}km) - Probability: {probability:.1%}"
            return Alert('earthquake', lvl, msg, location)
        
        def generate_flood_alert(self, probability, site_id, site_name, discharge, threshold):
            th = self.thresholds.get('flood', {'LOW':0.3,'MODERATE':0.5,'HIGH':0.7,'SEVERE':0.9})
            lvl = 4 if probability>=th['SEVERE'] else 3 if probability>=th['HIGH'] else 2 if probability>=th['MODERATE'] else 1 if probability>=th['LOW'] else 0
            if lvl == 0: return None
            msg = f"Flood Alert [{self._level_name(lvl)}] - {site_name} discharge {discharge:,.0f} cfs (threshold: {threshold:,.0f} cfs) - Probability: {probability:.1%}"
            return Alert('flood', lvl, msg, site_name)
        
        def _level_name(self, v): return {0:'NONE',1:'LOW',2:'MODERATE',3:'HIGH',4:'SEVERE'}.get(v, 'UNKNOWN')
    
    class AlertStorage:
        def __init__(self, alerts_dir=None):
            self.alerts_dir = Path(alerts_dir) if alerts_dir else project_root / 'data' / 'alerts'
            self.alerts_dir.mkdir(parents=True, exist_ok=True)
            self.alerts = []
        
        def save_alert(self, alert):
            self.alerts.append(alert)
            fp = self.alerts_dir / f"alert_{alert.alert_type}_{alert.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            import json
            with open(fp, 'w') as f:
                json.dump({'alert_type':alert.alert_type,'level_value':alert.level_value,'level_name':alert.level_name,'message':alert.message,'location':alert.location,'timestamp':alert.timestamp.isoformat()}, f, indent=2)
            logging.getLogger(__name__).info(f"Saved alert to {fp}")
            return fp

try:
    from src.alert_system.notifier import NotificationHandler
except ImportError:
    class NotificationHandler:
        def __init__(self, config): self.config = config
        def send_alert(self, alert, channels=None):
            channels = channels or ['log']
            logger = logging.getLogger(__name__)
            for ch in channels:
                if ch == 'log':
                    lvl_str = f"[{alert.level_name}]"
                    (logger.error if alert.level_value>=3 else logger.warning if alert.level_value>=2 else logger.info)(f"{lvl_str} {alert.message}")

class DisasterMonitoringSystem:
    def __init__(self):
        (project_root / 'logs').mkdir(exist_ok=True)
        setup_logging(str(project_root / 'logs' / 'monitoring_system.log'))
        self.logger = logging.getLogger(__name__)
        
        self.config = load_config(str(config_file))
        
        # initialize components
        self.eq_collector = USGSEarthquakeCollector()
        self.flood_collector = USGSFloodCollector(self.config['flood']['monitoring_sites'])
        self.alert_generator = AlertGenerator(self.config)
        self.alert_storage = AlertStorage(str(project_root / 'data' / 'alerts'))
        self.notifier = NotificationHandler(self.config)
        
        # load models
        self.load_models()
        self.logger.info("Disaster Monitoring System initialized")
    
    def load_models(self):
        """Load latest timestamped models"""
        self.logger.info("Loading prediction models...")
        model_dir = project_root / 'models'
        
        # load earthquake model (find latest timestamped file)
        eq_models = sorted(model_dir.glob('earthquake_risk_model_*.pkl'), reverse=True)
        
        if eq_models:
            self.eq_model = joblib.load(eq_models[0])
            self.logger.info(f"Earthquake model loaded: {eq_models[0].name}")
        else:
            self.logger.warning("Earthquake model not found. Using rule-based alerts")
            self.eq_model = None
        
        # load flood models (find latest per site)
        self.flood_models = {}
        for site_id in self.config['flood']['monitoring_sites'].keys():
            site_models = sorted(model_dir.glob(f'flood_risk_model_{site_id}_*.pkl'), reverse=True)
            site_scalers = sorted(model_dir.glob(f'flood_scaler_{site_id}_*.pkl'), reverse=True)
            
            if site_models and site_scalers:
                self.flood_models[site_id] = {
                    'model': joblib.load(site_models[0]),
                    'scaler': joblib.load(site_scalers[0])
                }
                self.logger.info(f"Flood model loaded for {site_id}: {site_models[0].name}")
    
    def monitor_earthquakes(self):
        """Monitor earthquakes (rule-based fallback if no model)"""
        df = self.eq_collector.fetch_realtime('day', min_magnitude=2.5)
        if df is None or df.empty:
            self.logger.info("No recent earthquakes found")
            return []
        
        # rule-based alert
        significant = df[df['mag'] >= self.config['earthquake']['significant_magnitude']]
        alerts = []
        
        for _, row in significant.iterrows():
            prob = min(0.95, (row['mag'] - 4.0) / 6.0) if row['mag'] > 4.0 else 0.1
            alert = self.alert_generator.generate_earthquake_alert(prob, row['place'], row['mag'], row['depth'])
            if alert:
                alerts.append(alert)
                self.alert_storage.save_alert(alert)
                if alert.level_value >= 3:  
                    self.notifier.send_alert(alert, channels=['log'])
        
        self.logger.info(f"Generated {len(alerts)} earthquake alerts")
        return alerts
    
    def monitor_floods(self):
        """Monitor floods using daily values API (no true realtime feed)"""
        alerts = []
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        for site_id, site_name in self.config['flood']['monitoring_sites'].items():
            df = self.flood_collector.fetch_daily_values(site_id, start_date, end_date)
            if df is None or df.empty:
                continue
            
            # find discharge column (USGS parameter 00060 = streamflow)
            discharge_cols = [c for c in df.columns if '00060' in str(c)]
            if not discharge_cols:
                continue
            
            latest = df[discharge_cols[0]].iloc[-1]
            threshold = df[discharge_cols[0]].quantile(0.95)  # 95th percentile as flood threshold
            
            if latest > threshold:
                severity = (latest - threshold) / threshold
                prob = min(0.95, 0.5 + severity * 0.3)
                alert = self.alert_generator.generate_flood_alert(
                    prob, site_id, site_name, latest, threshold
                )
                if alert:
                    alerts.append(alert)
                    self.alert_storage.save_alert(alert)
                    if alert.level_value >= 3:
                        self.notifier.send_alert(alert, channels=['log'])
        
        self.logger.info(f"Generated {len(alerts)} flood alerts")
        return alerts
    
    def run_monitoring_cycle(self):
        self.logger.info(f"MONITORING CYCLE START: {datetime.now()}")
        
        alerts = self.monitor_earthquakes() + self.monitor_floods()
        
        self.logger.info(f"CYCLE COMPLETE. Total alerts: {len(alerts)}")
        if alerts:
            severe = [a for a in alerts if a.level_value >= 4]
            high = [a for a in alerts if a.level_value == 3]
            self.logger.info(f"  Severe: {len(severe)}, High: {len(high)}")
        return alerts
    
    def start_continuous_monitoring(self, interval_hours=1):
        self.logger.info("\nSTARTING CONTINUOUS MONITORING")
        self.logger.info(f"Interval: {interval_hours} hour(s)")
        self.logger.info("Press Ctrl+C to stop")
        
        schedule.every(interval_hours).hours.do(self.run_monitoring_cycle)
        self.run_monitoring_cycle()  # run immediately
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("Monitoring stopped by user")

def start_monitoring(continuous=True, interval_hours=1):
    setup_logging(str(project_root / 'logs' / 'monitoring_system.log'))
    system = DisasterMonitoringSystem()
    system.start_continuous_monitoring(interval_hours) if continuous else system.run_monitoring_cycle()

if __name__ == "__main__":
    start_monitoring(continuous=True, interval_hours=1)