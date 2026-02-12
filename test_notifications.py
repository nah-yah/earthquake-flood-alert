import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.utils.helpers import setup_logging, load_config
from src.alert_system.alert_manager import Alert, AlertLevel, AlertGenerator
from src.alert_system.notifier import NotificationHandler

def test_email_notification():
    """Test email notifications"""
    
    print("TESTING EMAIL NOTIFICATIONS")
    
    # create test alert
    alert_gen = AlertGenerator()
    
    # create a high severity earthquake alert
    test_alert = alert_gen.generate_earthquake_alert(
        probability=0.85,
        location="San Francisco Bay Area, California",
        magnitude=6.2,
        depth=12.5
    )
    
    if test_alert:
        print(f"\nTest Alert Created:")
        print(f"  Type: {test_alert.hazard_type}")
        print(f"  Level: {test_alert.level.name}")
        print(f"  Location: {test_alert.location}")
        print(f"  Probability: {test_alert.probability:.1%}")
        print(f"  Message: {test_alert.message}")
        
        # initialize notifier
        notifier = NotificationHandler()
        
        print("Attempting to send email...")
        
        # check if email is configured
        import os
        sender = os.environ.get('EMAIL_SENDER')
        password = os.environ.get('EMAIL_PASSWORD')
        
        if not sender or not password:
            print("\nEMAIL NOT CONFIGURED")
            print("\nTo enable email notifications, set environment variables:")
            print("  - EMAIL_SENDER: Your email address")
            print("  - EMAIL_PASSWORD: Your email password/app password")
            print("\nFor Gmail users:")
            print("  1. Enable 2-factor authentication")
            print("  2. Generate an app password: https://myaccount.google.com/apppasswords")
            print("  3. Use the app password (not your regular password)")
            print("\nExample (Windows Command Prompt):")
            print('  set EMAIL_SENDER=your_email@gmail.com')
            print('  set EMAIL_PASSWORD=your_app_password')
            print("\nExample (Windows PowerShell):")
            print('  $env:EMAIL_SENDER="your_email@gmail.com"')
            print('  $env:EMAIL_PASSWORD="your_app_password"')
            return False
        
        print(f"\nEmail configured: {sender}")
        
        # get recipients
        config = load_config()
        recipients = config['alerts'].get('recipients', [])
        
        if not recipients:
            print("\nNo recipients configured in config.yaml")
            print("\nUsing sender email as recipient for testing...")
            recipients = [sender]
        
        print(f"Recipients: {recipients}")
        
        # send test email
        success = notifier.send_email_alert(test_alert, recipients)
        
        if success:
            print("\nEMAIL SENT SUCCESSFULLY!")
            print(f"Check your inbox: {recipients}")
        else:
            print("\nEMAIL FAILED")
            print("Check the logs for error details")
        
        return success
    
    return False

def test_log_notification():
    """Test log-based notifications"""
    
    print("TESTING LOG NOTIFICATIONS")
    
    # create test alerts of different types
    alert_gen = AlertGenerator()
    notifier = NotificationHandler()
    
    # earthquake alert
    eq_alert = alert_gen.generate_earthquake_alert(
        probability=0.72,
        location="Los Angeles, California",
        magnitude=5.8,
        depth=8.3
    )
    
    # flood alert
    flood_alert = alert_gen.generate_flood_alert(
        probability=0.88,
        site_id='07374000',
        site_name='Mississippi River at Baton Rouge, LA',
        current_discharge=920000,
        threshold=750000
    )
    
    print("\nLogging test alerts...")
    
    if eq_alert:
        notifier.log_alert(eq_alert)
        print(f"Logged earthquake alert: {eq_alert.alert_id}")
    
    if flood_alert:
        notifier.log_alert(flood_alert)
        print(f"Logged flood alert: {flood_alert.alert_id}")
    
    # check log file
    log_file = Path.cwd() / 'logs' / 'alerts.log'
    
    if log_file.exists():
        print(f"\nAlert log file created: {log_file}")
        print("\nLast 5 log entries:")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-5:]:
                print(f"  {line.strip()}")
    else:
        print(f"\nLog file not found: {log_file}")
    
    return True

def main():
    """Run all notification tests"""
    
    setup_logging()
    
    print("NOTIFICATION SYSTEM TEST SUITE")
    
    # test menu
    print("SELECT TEST TO RUN:")
    print("1. Test Email Notification (requires setup)")
    print("2. Test Log Notification (always works)")
    print("3. Run Both Tests")
    print("0. Exit")
    
    choice = input("\nEnter choice (0-3): ").strip()
    
    if choice == '1':
        test_email_notification()
    elif choice == '2':
        test_log_notification()
    elif choice == '3':
        print("\nRunning all tests...")
        test_log_notification()
        test_email_notification()
    elif choice == '0':
        print("\nExiting...")
        return
    else:
        print("\nInvalid choice!")
    
    print("TEST COMPLETE")

if __name__ == "__main__":
    main()
