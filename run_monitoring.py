# run_monitoring.py
"""
Main script to run the disaster monitoring system
"""

import sys
from pathlib import Path
import argparse

project_root = Path(__file__).resolve().parent

config_file = project_root / 'config' / 'config.yaml'

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.alert_system.monitoring import start_monitoring

def main():
    parser = argparse.ArgumentParser(description='Earthquake & Flood Monitoring System')
    parser.add_argument('--continuous', action='store_true', 
                       help='Run continuous monitoring (default: run once)')
    parser.add_argument('--interval', type=int, default=1,
                       help='Monitoring interval in hours (default: 1)')
    
    args = parser.parse_args()
    
    print("EARTHQUAKE & FLOOD EARLY WARNING SYSTEM")
    print()
    
    if args.continuous:
        print(f"Starting continuous monitoring (interval: {args.interval} hour(s))")
        print("Press Ctrl+C to stop")
        print()
        start_monitoring(continuous=True, interval_hours=args.interval)
    else:
        print("Running one-time monitoring check")
        print()
        start_monitoring(continuous=False)

if __name__ == "__main__":
    main()