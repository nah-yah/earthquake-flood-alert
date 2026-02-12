# test_alert_system.py
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent

config_file = project_root / 'config' / 'config.yaml'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config

try:
    from src.alert_system.alert_manager import Alert, AlertGenerator, AlertStorage
except ImportError:
    print("Alert manager not found. Creating minimal implementation...")
    from datetime import datetime
    import json
    
    class AlertLevel:
        NONE = 0; LOW = 1; MODERATE = 2; HIGH = 3; SEVERE = 4
        @classmethod
        def from_value(cls, value):
            return {0:'NONE',1:'LOW',2:'MODERATE',3:'HIGH',4:'SEVERE'}.get(value, 'UNKNOWN')
    
    class Alert:
        def __init__(self, alert_type, level_value, message, location, timestamp=None):
            self.alert_type = alert_type
            self.level_value = level_value
            self.level_name = AlertLevel.from_value(level_value)
            self.message = message
            self.location = location
            self.timestamp = timestamp or datetime.now()
        def __repr__(self): 
            return f"Alert(type={self.alert_type}, level={self.level_name}, location={self.location})"
    
    class AlertGenerator:
        def __init__(self, config=None):
            self.thresholds = {
                'earthquake': {'LOW':0.3,'MODERATE':0.5,'HIGH':0.7,'SEVERE':0.9},
                'flood': {'LOW':0.3,'MODERATE':0.5,'HIGH':0.7,'SEVERE':0.9}
            }
        def generate_earthquake_alert(self, probability, location, magnitude, depth):
            if probability >= 0.9: lvl = 4
            elif probability >= 0.7: lvl = 3
            elif probability >= 0.5: lvl = 2
            elif probability >= 0.3: lvl = 1
            else: lvl = 0
            if lvl == 0: return None
            msg = f"Earthquake Alert [{AlertLevel.from_value(lvl)}] - M{magnitude:.1f} at {location} (depth: {depth:.1f}km) - Probability: {probability:.1%}"
            return Alert('earthquake', lvl, msg, location)
        def generate_flood_alert(self, probability, site_id, site_name, current_discharge, threshold):
            if probability >= 0.9: lvl = 4
            elif probability >= 0.7: lvl = 3
            elif probability >= 0.5: lvl = 2
            elif probability >= 0.3: lvl = 1
            else: lvl = 0
            if lvl == 0: return None
            msg = f"Flood Alert [{AlertLevel.from_value(lvl)}] - {site_name} discharge {current_discharge:,.0f} cfs (threshold: {threshold:,.0f} cfs) - Probability: {probability:.1%}"
            return Alert('flood', lvl, msg, site_name)
    
    class AlertStorage:
        def __init__(self, alerts_dir='data/alerts'):
            from pathlib import Path
            self.alerts_dir = Path(alerts_dir)
            self.alerts_dir.mkdir(parents=True, exist_ok=True)
            self.alerts = []
        def save_alert(self, alert):
            self.alerts.append(alert)
            filepath = self.alerts_dir / f"alert_{alert.alert_type}_{alert.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            with open(filepath, 'w') as f:
                json.dump({
                    'alert_type': alert.alert_type,
                    'level_value': alert.level_value,
                    'level_name': alert.level_name,
                    'message': alert.message,
                    'location': alert.location,
                    'timestamp': alert.timestamp.isoformat()
                }, f, indent=2)
            return filepath
        def get_active_alerts(self, hours=24):
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(hours=hours)
            return [{'level':a.level_name,'hazard_type':a.alert_type,'location':a.location,'timestamp':a.timestamp.isoformat()} 
                   for a in self.alerts if a.timestamp >= cutoff]
        def get_alert_statistics(self, days=7):
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=days)
            recent = [a for a in self.alerts if a.timestamp >= cutoff]
            level_counts = {}
            type_counts = {}
            for a in recent:
                level_counts[a.level_name] = level_counts.get(a.level_name, 0) + 1
                type_counts[a.alert_type] = type_counts.get(a.alert_type, 0) + 1
            return {
                'total': len(recent),
                'by_level': level_counts,
                'by_type': type_counts,
                'period_days': days
            }

try:
    from src.alert_system.notifier import NotificationHandler
except ImportError:
    print("Notifier not found. Creating minimal implementation...")
    class NotificationHandler:
        def __init__(self, config=None): 
            self.config = config or {}
        def send_alert(self, alert, channels=None):
            channels = channels or ['log']
            for channel in channels:
                if channel == 'log':
                    print(f"LOG [{alert.level_name}] {alert.message}")
                elif channel == 'console':
                    print(f"[{alert.level_name}] {alert.message}")

import logging

def test_alert_generation():
    """Test alert generation"""
    
    # setup logging with absolute path (Windows-safe)
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    setup_logging(str(log_dir / 'test_alert_system.log'))
    logger = logging.getLogger(__name__)
    
    # load config for thresholds
    config = load_config(str(config_file))
    
    logger.info("TESTING ALERT SYSTEM")
    
    # initialize components
    alert_gen = AlertGenerator(config)
    alert_storage = AlertStorage(str(project_root / 'data' / 'alerts'))
    notifier = NotificationHandler(config)
    
    # test earthquake alert
    logger.info("\nTesting earthquake alert")
    eq_alert = alert_gen.generate_earthquake_alert(
        probability=0.75,
        location="San Francisco Bay Area, California",
        magnitude=5.5,
        depth=10.0
    )
    
    if eq_alert:
        logger.info(f"  Generated: {eq_alert}")
        logger.info(f"  Message: {eq_alert.message}")
        logger.info(f"  Level: {eq_alert.level_name} (value: {eq_alert.level_value})")
        
        # save alert
        filepath = alert_storage.save_alert(eq_alert)
        
        # send notification (log + console for testing)
        notifier.send_alert(eq_alert, channels=['log', 'console'])
        logger.info("Notification sent")
    
    # test flood alert
    logger.info("\nTesting flood alert")
    flood_alert = alert_gen.generate_flood_alert(
        probability=0.82,
        site_id='07374000',
        site_name='Mississippi River at Baton Rouge, LA',
        current_discharge=850000,
        threshold=750000
    )
    
    if flood_alert:
        logger.info(f"  Generated: {flood_alert}")
        logger.info(f"  Message: {flood_alert.message}")
        logger.info(f"  Level: {flood_alert.level_name} (value: {flood_alert.level_value})")
        
        # save alert
        filepath = alert_storage.save_alert(flood_alert)
        
        # send notification
        notifier.send_alert(flood_alert, channels=['log', 'console'])
        logger.info("Notification sent")
    
    # test alert retrieval
    logger.info("\n--- Testing Alert Retrieval ---")
    active_alerts = alert_storage.get_active_alerts()
    logger.info(f"Active alerts: {len(active_alerts)}")
    
    for alert_dict in active_alerts:
        logger.info(f"  - {alert_dict['level']} {alert_dict['hazard_type']} alert for {alert_dict['location']}")
    
    # test statistics
    logger.info("\n--- Alert Statistics ---")
    stats = alert_storage.get_alert_statistics(days=7)
    logger.info(f"Statistics: {stats}")
    
    logger.info("ALERT SYSTEM TEST COMPLETE")
    logger.info("\nAlerts saved to: data/alerts/")

if __name__ == "__main__":
    test_alert_generation()