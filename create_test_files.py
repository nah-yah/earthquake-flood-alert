# create_test_files.py
from pathlib import Path

# test notification script
test_notifications_code = '''"""
Test notification system without running the full monitoring
Tests email, SMS, and logging functionality
"""

import sys
from pathlib import Path
from datetime import datetime

# Fix import path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config
from src.alert_system.alert_manager import Alert, AlertLevel, AlertGenerator
from src.alert_system.notifier import NotificationHandler

def test_email_notification():
    """Test email notifications"""
    
    print("TESTING EMAIL NOTIFICATIONS")
    
    # Create test alert
    alert_gen = AlertGenerator()
    
    # Create a high severity earthquake alert
    test_alert = alert_gen.generate_earthquake_alert(
        probability=0.85,
        location="San Francisco Bay Area, California",
        magnitude=6.2,
        depth=12.5
    )
    
    if test_alert:
        print(f"\\nTest Alert Created:")
        print(f"  Type: {test_alert.hazard_type}")
        print(f"  Level: {test_alert.level.name}")
        print(f"  Location: {test_alert.location}")
        print(f"  Probability: {test_alert.probability:.1%}")
        print(f"  Message: {test_alert.message}")
        
        # Initialize notifier
        notifier = NotificationHandler()
        
        print("Attempting to send email...")
        
        # Check if email is configured
        import os
        sender = os.environ.get('EMAIL_SENDER')
        password = os.environ.get('EMAIL_PASSWORD')
        
        if not sender or not password:
            print("\\nEMAIL NOT CONFIGURED")
            print("\\nTo enable email notifications, set environment variables:")
            print("  - EMAIL_SENDER: Your email address")
            print("  - EMAIL_PASSWORD: Your email password/app password")
            print("\\nFor Gmail users:")
            print("  1. Enable 2-factor authentication")
            print("  2. Generate an app password: https://myaccount.google.com/apppasswords")
            print("  3. Use the app password (not your regular password)")
            print("\\nExample (Windows Command Prompt):")
            print('  set EMAIL_SENDER=your_email@gmail.com')
            print('  set EMAIL_PASSWORD=your_app_password')
            print("\\nExample (Windows PowerShell):")
            print('  $env:EMAIL_SENDER="your_email@gmail.com"')
            print('  $env:EMAIL_PASSWORD="your_app_password"')
            return False
        
        print(f"\\n✓ Email configured: {sender}")
        
        # Get recipients
        config = load_config()
        recipients = config['alerts'].get('recipients', [])
        
        if not recipients:
            print("\\nNo recipients configured in config.yaml")
            print("\\nUsing sender email as recipient for testing...")
            recipients = [sender]
        
        print(f"  Recipients: {recipients}")
        
        # Send test email
        success = notifier.send_email_alert(test_alert, recipients)
        
        if success:
            print("\\nEMAIL SENT SUCCESSFULLY!")
            print(f"   Check your inbox: {recipients}")
        else:
            print("\\nEMAIL FAILED")
            print("   Check the logs for error details")
        
        return success
    
    return False

def test_log_notification():
    """Test log-based notifications"""
    
    print("TESTING LOG NOTIFICATIONS")
    
    # Create test alerts of different types
    alert_gen = AlertGenerator()
    notifier = NotificationHandler()
    
    # Earthquake alert
    eq_alert = alert_gen.generate_earthquake_alert(
        probability=0.72,
        location="Los Angeles, California",
        magnitude=5.8,
        depth=8.3
    )
    
    # Flood alert
    flood_alert = alert_gen.generate_flood_alert(
        probability=0.88,
        site_id='07374000',
        site_name='Mississippi River at Baton Rouge, LA',
        current_discharge=920000,
        threshold=750000
    )
    
    print("\\nLogging test alerts...")
    
    if eq_alert:
        notifier.log_alert(eq_alert)
        print(f"Logged earthquake alert: {eq_alert.alert_id}")
    
    if flood_alert:
        notifier.log_alert(flood_alert)
        print(f"Logged flood alert: {flood_alert.alert_id}")
    
    # Check log file
    log_file = Path.cwd() / 'logs' / 'alerts.log'
    
    if log_file.exists():
        print(f"\\nAlert log file created: {log_file}")
        print("\\nLast 5 log entries:")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-5:]:
                print(f"  {line.strip()}")
    else:
        print(f"\\nLog file not found: {log_file}")
    
    return True

def main():
    """Run all notification tests"""
    
    setup_logging()
    
    print("NOTIFICATION SYSTEM TEST SUITE")
    
    # Test menu
    print("SELECT TEST TO RUN:")
    print("1. Test Email Notification (requires setup)")
    print("2. Test Log Notification (always works)")
    print("3. Run Both Tests")
    print("0. Exit")
    
    choice = input("\\nEnter choice (0-3): ").strip()
    
    if choice == '1':
        test_email_notification()
    elif choice == '2':
        test_log_notification()
    elif choice == '3':
        print("\\nRunning all tests...")
        test_log_notification()
        test_email_notification()
    elif choice == '0':
        print("\\nExiting...")
        return
    else:
        print("\\nInvalid choice!")
    
    print("TEST COMPLETE")

if __name__ == "__main__":
    main()
'''

# email setup script
setup_email_code = '''"""
Quick script to help set up email notifications for Windows
"""

import os
import sys

def setup_email():
    """Setup email for Windows"""
    print("EMAIL NOTIFICATION SETUP FOR WINDOWS")
    
    print("\\nBefore continuing, you need a Gmail App Password:")
    print("  1. Go to: https://myaccount.google.com/security")
    print("  2. Enable 2-Step Verification")
    print("  3. Go to: https://myaccount.google.com/apppasswords")
    print("  4. Select 'Mail' and your device")
    print("  5. Google will generate a 16-character password")
    print("  6. Copy this password (you'll need it below)")
    
    input("\\nPress Enter when you have your App Password ready...")
    
    email = input("\\nEnter your Gmail address: ").strip()
    password = input("Enter your Gmail App Password (16 characters): ").strip()
    
    print("SETTING UP ENVIRONMENT VARIABLES")
    
    # Set for current session
    os.environ['EMAIL_SENDER'] = email
    os.environ['EMAIL_PASSWORD'] = password
    
    print(f"\\nEMAIL_SENDER set to: {email}")
    print(f"EMAIL_PASSWORD set to: {'*' * len(password)}")
    
    print("\\nNOTE: These are set only for this session!")
    print("\\nTo set permanently, run these commands in Command Prompt:")
    print(f'  setx EMAIL_SENDER "{email}"')
    print(f'  setx EMAIL_PASSWORD "{password}"')
    
    print("\\nOR in PowerShell (Run as Administrator):")
    print(f'  [System.Environment]::SetEnvironmentVariable("EMAIL_SENDER", "{email}", "User")')
    print(f'  [System.Environment]::SetEnvironmentVariable("EMAIL_PASSWORD", "{password}", "User")')
    
    print("TESTING EMAIL SETUP")
    
    test = input("\\nWould you like to test email now? (yes/no): ").lower()
    
    if test == 'yes':
        print("\\nRunning test...")
        import subprocess
        subprocess.run([sys.executable, 'test_notifications.py'])
    else:
        print("\\nYou can test later by running:")
        print("  python test_notifications.py")

if __name__ == "__main__":
    setup_email()
'''

# create files
def create_files():
    """Create the test files"""
    
    current_dir = Path.cwd()
    
    # Minimal safety check (keep project name check but remove redundant prints)
    if current_dir.name != "earthquake-flood-alert":
        print(f"\\nWARNING: Not in project root (current: {current_dir.name})")
        response = input("Continue anyway? (yes/no): ").lower()
        if response != 'yes':
            print("\\nAborted. Run from project root directory.")
            return
    
    # Create test_notifications.py
    test_file = current_dir / 'test_notifications.py'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_notifications_code)
    print(f"\nCreated: {test_file.name}")
    
    # Create setup_email.py
    setup_file = current_dir / 'setup_email.py'
    with open(setup_file, 'w', encoding='utf-8') as f:
        f.write(setup_email_code)
    print(f"Created: {setup_file.name}")
    
    print("\nFILES CREATED SUCCESSFULLY!")
    print("\nNext steps:")
    print("  python setup_email.py        # configure email")
    print("  python test_notifications.py # test notifications")

if __name__ == "__main__":
    create_files()