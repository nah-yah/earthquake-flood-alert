# run_dashboard.py

import subprocess
import sys
from pathlib import Path

def run_dashboard():
    """Run the Streamlit dashboard"""
    
    dashboard_path = Path(__file__).parent / 'dashboard' / 'app.py'

    print("STARTING EARTHQUAKE & FLOOD ALERT DASHBOARD")
    print()
    print("Dashboard will open in your browser...")
    print("Press Ctrl+C to stop the server")
    print()
    
    # run streamlit
    subprocess.run([
        sys.executable, '-m', 'streamlit', 'run', 
        str(dashboard_path),
        '--server.port', '8501',
        '--server.address', 'localhost'
    ])

if __name__ == "__main__":
    run_dashboard()