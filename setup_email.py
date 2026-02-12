import os
import sys

def setup_email():
    """Setup email for Windows"""
    print("EMAIL NOTIFICATION SETUP FOR WINDOWS")
    
    print("\nBefore continuing, you need a Gmail App Password:")
    print("  1. Go to: https://myaccount.google.com/security")
    print("  2. Enable 2-Step Verification")
    print("  3. Go to: https://myaccount.google.com/apppasswords")
    print("  4. Select 'Mail' and your device")
    print("  5. Google will generate a 16-character password")
    print("  6. Copy this password (you'll need it below)")
    
    input("\nPress Enter when you have your App Password ready...")
    
    email = input("\nEnter your Gmail address: ").strip()
    password = input("Enter your Gmail App Password (16 characters): ").strip()
    
    print("SETTING UP ENVIRONMENT VARIABLES")
    
    # set for current session
    os.environ['EMAIL_SENDER'] = email
    os.environ['EMAIL_PASSWORD'] = password
    
    print(f"\nEMAIL_SENDER set to: {email}")
    print(f"EMAIL_PASSWORD set to: {'*' * len(password)}")
    
    print("\nNOTE: These are set only for this session!")

    print("TESTING EMAIL SETUP")
    
    test = input("\nWould you like to test email now? (yes/no): ").lower()
    
    if test == 'yes':
        print("\nRunning test...")
        import subprocess
        subprocess.run([sys.executable, 'test_notifications.py'])
    else:
        print("\nYou can test later by running:")
        print("  python test_notifications.py")

if __name__ == "__main__":
    setup_email()
