# src/alert_system/alert_manager.py
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from datetime import datetime
from enum import Enum

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.utils.helpers import load_config
import logging

class AlertLevel(Enum):
    """Alert severity levels """
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4  

class Alert:
    """Individual alert object"""
    
    def __init__(self, hazard_type, level, location, probability, 
                 message, timestamp=None, metadata=None):
        self.hazard_type = hazard_type
        self.level = level
        self.location = location
        self.probability = probability
        self.message = message
        self.timestamp = timestamp or datetime.now()
        self.metadata = metadata or {}
        self.alert_id = self._generate_alert_id()
    
    def _generate_alert_id(self):
        """Generate unique alert ID"""
        timestamp_str = self.timestamp.strftime('%Y%m%d%H%M%S')
        hazard_code = 'EQ' if self.hazard_type == 'earthquake' else 'FL'
        return f"{hazard_code}-{timestamp_str}-{self.level.value}"
    
    def to_dict(self):
        """Convert alert to dictionary"""
        return {
            'alert_id': self.alert_id,
            'hazard_type': self.hazard_type,
            'level': self.level.name,
            'level_value': self.level.value,
            'location': self.location,
            'probability': float(self.probability),
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
    
    def __repr__(self):
        return f"Alert({self.hazard_type}, {self.level.name}, {self.location}, {self.probability:.2%})"

class AlertGenerator:
    """Generate alerts based on prediction probabilities"""
    
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or load_config()
        
        # load thresholds from config
        self.earthquake_thresholds = self.config['alerts']['thresholds']['earthquake']
        self.flood_thresholds = self.config['alerts']['thresholds']['flood']
    
    def generate_earthquake_alert(self, probability, location, magnitude=None, depth=None):
        """Generate earthquake alert based on probability"""
        level = self._determine_level(probability, self.earthquake_thresholds)
        if level is None:
            return None
        
        # magnitude/depth removed from message generation (unused in template)
        message = self._generate_earthquake_message(level, probability, location)
        
        metadata = {
            'expected_magnitude': magnitude,
            'expected_depth': depth,
            'prediction_window': '24 hours'
        }
        
        alert = Alert(
            hazard_type='earthquake',
            level=level,
            location=location,
            probability=probability,
            message=message,
            metadata=metadata
        )
        
        self.logger.info(f"Generated earthquake alert: {alert}")
        return alert
    
    def generate_flood_alert(self, probability, site_id, site_name, 
                            current_discharge=None, threshold=None):
        """Generate flood alert based on probability"""
        level = self._determine_level(probability, self.flood_thresholds)
        if level is None:
            return None
        
        message = self._generate_flood_message(level, probability, site_name,
                                               current_discharge, threshold)
        
        metadata = {
            'site_id': site_id,
            'current_discharge': current_discharge,
            'flood_threshold': threshold,
            'prediction_window': '7 days'
        }
        
        alert = Alert(
            hazard_type='flood',
            level=level,
            location=site_name,
            probability=probability,
            message=message,
            metadata=metadata
        )
        
        self.logger.info(f"Generated flood alert: {alert}")
        return alert
    
    def _determine_level(self, probability, thresholds):
        """Determine alert level based on probability and thresholds"""
        if probability >= thresholds['SEVERE']:
            return AlertLevel.SEVERE
        elif probability >= thresholds['HIGH']:
            return AlertLevel.HIGH
        elif probability >= thresholds['MODERATE']:
            return AlertLevel.MODERATE
        elif probability >= thresholds['LOW']:
            return AlertLevel.LOW
        else:
            return None
    
    def _generate_earthquake_message(self, level, probability, location):
        """Generate earthquake alert message (magnitude/depth parameters removed - unused)"""
        if level == AlertLevel.SEVERE:
            message = f"SEVERE EARTHQUAKE ALERT for {location}! "
            message += f"High probability ({probability:.1%}) of significant seismic activity within 24 hours. "
            message += "Immediate preparation recommended."
        elif level == AlertLevel.HIGH:
            message = f"HIGH earthquake risk detected in {location}. "
            message += f"Probability: {probability:.1%}. "
            message += "Review emergency plans and supplies."
        elif level == AlertLevel.MODERATE:
            message = f"MODERATE earthquake risk in {location}. "
            message += f"Probability: {probability:.1%}. "
            message += "Stay informed and be prepared."
        else:
            message = f"Low earthquake risk detected in {location}. "
            message += f"Probability: {probability:.1%}. "
            message += "Monitor conditions."
        
        return message
    
    def _generate_flood_message(self, level, probability, site_name,
                                current_discharge, threshold):
        """Generate flood alert message"""
        if level == AlertLevel.SEVERE:
            message = f"SEVERE FLOOD ALERT for {site_name}! "
            message += f"Very high probability ({probability:.1%}) of flooding within 7 days. "
            message += "Evacuate low-lying areas immediately."
        elif level == AlertLevel.HIGH:
            message = f"HIGH flood risk at {site_name}. "
            message += f"Probability: {probability:.1%}. "
            message += "Prepare for possible evacuation."
        elif level == AlertLevel.MODERATE:
            message = f"MODERATE flood risk at {site_name}. "
            message += f"Probability: {probability:.1%}. "
            message += "Monitor river levels closely."
        else:
            message = f"Low flood risk at {site_name}. "
            message += f"Probability: {probability:.1%}. "
            message += "Stay informed."
        
        if current_discharge and threshold:
            pct_of_threshold = (current_discharge / threshold) * 100
            message += f" Current discharge: {current_discharge:,.0f} cfs ({pct_of_threshold:.0f}% of flood threshold)."
        
        return message
    
    def aggregate_alerts(self, alerts_list):
        """Sort alerts by severity and probability (renamed from misleading 'aggregate')"""
        if not alerts_list:
            return []
        
        sorted_alerts = sorted(alerts_list, 
                             key=lambda x: (x.level.value, x.probability), 
                             reverse=True)
        
        self.logger.info(f"Sorted {len(sorted_alerts)} alerts by severity")
        return sorted_alerts
    
    def filter_alerts(self, alerts_list, min_level=AlertLevel.LOW, 
                     hazard_type=None, max_age_hours=24):
        """Filter alerts by criteria"""
        filtered = []
        current_time = datetime.now()
        
        for alert in alerts_list:
            if alert.level.value < min_level.value:
                continue
            if hazard_type and alert.hazard_type != hazard_type:
                continue
            age_hours = (current_time - alert.timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                continue
            filtered.append(alert)
        
        self.logger.info(f"Filtered to {len(filtered)} alerts (from {len(alerts_list)})")
        return filtered

class AlertStorage:
    """Store and retrieve alerts"""
    
    def __init__(self, storage_dir='data/alerts'):
        self.logger = logging.getLogger(__name__)
        self.storage_dir = Path.cwd() / storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_alerts_file = self.storage_dir / 'active_alerts.json'
        self.alert_history_file = self.storage_dir / 'alert_history.csv'
    
    def save_alert(self, alert):
        """Save an alert to storage"""
        self._add_to_history(alert)
        self._update_active_alerts(alert)
        self.logger.info(f"Saved alert: {alert.alert_id}")
    
    def _add_to_history(self, alert):
        """Add alert to historical log"""
        alert_dict = alert.to_dict()
        df_new = pd.DataFrame([alert_dict])
        
        if self.alert_history_file.exists():
            df_existing = pd.read_csv(self.alert_history_file)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new
        
        df_combined.to_csv(self.alert_history_file, index=False)
    
    def _update_active_alerts(self, alert):
        """Update active alerts list (auto-expire after 24h)"""
        import json
        
        if self.active_alerts_file.exists():
            with open(self.active_alerts_file, 'r') as f:
                active_alerts = json.load(f)
        else:
            active_alerts = []
        
        active_alerts.append(alert.to_dict())
        
        # auto-expire old alerts
        cutoff_time = datetime.now().timestamp() - (24 * 3600)
        active_alerts = [
            a for a in active_alerts 
            if datetime.fromisoformat(a['timestamp']).timestamp() > cutoff_time
        ]
        
        with open(self.active_alerts_file, 'w') as f:
            json.dump(active_alerts, f, indent=2)
    
    def get_active_alerts(self, min_level=AlertLevel.LOW, hazard_type=None):
        """Get active alerts"""
        import json
        
        if not self.active_alerts_file.exists():
            return []
        
        with open(self.active_alerts_file, 'r') as f:
            active_alerts = json.load(f)
        
        filtered = []
        for alert_dict in active_alerts:
            if alert_dict['level_value'] < min_level.value:
                continue
            if hazard_type and alert_dict['hazard_type'] != hazard_type:
                continue
            filtered.append(alert_dict)
        
        return filtered
    
    def get_alert_history(self, days=7, hazard_type=None):
        """Get alert history"""
        if not self.alert_history_file.exists():
            return pd.DataFrame()
        
        df = pd.read_csv(self.alert_history_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        cutoff_date = datetime.now() - pd.Timedelta(days=days)
        df = df[df['timestamp'] >= cutoff_date]
        
        if hazard_type:
            df = df[df['hazard_type'] == hazard_type]
        
        return df
    
    def clear_old_alerts(self, days=30):
        """ Clear old alerts from history """
        if not self.alert_history_file.exists():
            return 0
        
        df = pd.read_csv(self.alert_history_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        original_count = len(df)
        cutoff_date = datetime.now() - pd.Timedelta(days=days)
        df = df[df['timestamp'] >= cutoff_date]
        df.to_csv(self.alert_history_file, index=False)
        
        removed_count = original_count - len(df)
        self.logger.info(f"Cleared {removed_count} old alerts")
        return removed_count