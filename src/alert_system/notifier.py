# src/alert_system/notifier.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import sys
import os
from datetime import datetime

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.utils.helpers import load_config
from src.alert_system.alert_manager import Alert
import logging

class NotificationHandler:
    """Handle alert notifications via multiple channels"""

    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config or load_config()

        # email configuration
        self.email_config = self.config.get("alerts", {}).get("email", {})
        self.recipients = self.config.get("alerts", {}).get("recipients", [])

    def send_email_alert(self, alert, recipients=None):
        """
        Send email alert

        Args:
            alert: Alert object
            recipients: List of email addresses (default: from config)
        """
        if not self.email_config.get("enabled", False):
            self.logger.info("Email notifications disabled in config")
            return False

        recipients = recipients or self.recipients
        if not recipients:
            self.logger.warning("No email recipients configured")
            return False

        try:
            # credentials from environment variables
            sender_email = os.getenv("EMAIL_SENDER", "disaster.example@prevention.com")
            sender_password = os.getenv("EMAIL_PASSWORD")

            if not sender_password:
                self.logger.warning("EMAIL_PASSWORD environment variable not set")
                return False

            # build email
            msg = MIMEMultipart("alternative")
            msg["From"] = sender_email
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = self._create_email_subject(alert)

            text_body = self._create_email_body_text(alert)
            html_body = self._create_email_body_html(alert)

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # send email
            with smtplib.SMTP(
                self.email_config.get("smtp_server", "smtp.gmail.com"),
                self.email_config.get("smtp_port", 587),
            ) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)

            self.logger.info(f"Email alert sent to {len(recipients)} recipient(s)")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}", exc_info=True)
            return False
    
    def _create_email_subject(self, alert):
        """Create email subject line"""
        return f"{alert.level.name} {alert.hazard_type.upper()} ALERT - {alert.location}"
    
    def _create_email_body_text(self, alert):
        """Create plain text email body"""
        body = f"""
DISASTER ALERT NOTIFICATION

Alert ID: {alert.alert_id}
Hazard type: {alert.hazard_type.upper()}
Alert level: {alert.level.name}
Location: {alert.location}
Probability: {alert.probability:.1%}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

MESSAGE

{alert.message}

ADDITIONAL INFORMATION

"""
        
        # metadata
        for key, value in alert.metadata.items():
            body += f"{key.replace('_', ' ').capitalize()}: {value}\n"
        
        body += f"""

This is an automated alert from the Earthquake & Flood Early Warning System.
Please take appropriate precautions based on the alert level.

For more information, contact your local emergency management office.
"""
        
        return body
    
    def _create_email_body_html(self, alert):
        """Create HTML email body"""
        
        # Color scheme based on alert level
        colors = {
            'SEVERE': '#dc3545',
            'HIGH': '#fd7e14',
            'MODERATE': '#ffc107',
            'LOW': '#17a2b8'
        }
        color = colors.get(alert.level.name, '#6c757d')
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; }}
                .footer {{ background-color: #e9ecef; padding: 15px; text-align: center; border-radius: 0 0 5px 5px; font-size: 12px; }}
                .info-box {{ background-color: white; padding: 15px; margin: 10px 0; border-left: 4px solid {color}; }}
                .alert-message {{ background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 15px 0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                td {{ padding: 8px; border-bottom: 1px solid #dee2e6; }}
                td:first-child {{ font-weight: bold; width: 40%; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{alert.level.name} {alert.hazard_type.upper()} ALERT</h1>
                    <p style="margin: 0; font-size: 18px;">{alert.location}</p>
                </div>
                
                <div class="content">
                    <div class="info-box">
                        <table>
                            <tr><td>Alert ID</td><td>{alert.alert_id}</td></tr>
                            <tr><td>Hazard type</td><td>{alert.hazard_type.title()}</td></tr>
                            <tr><td>Alert level</td><td><strong style="color: {color};">{alert.level.name}</strong></td></tr>
                            <tr><td>Risk probability</td><td>{alert.probability:.1%}</td></tr>
                            <tr><td>Timestamp</td><td>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                        </table>
                    </div>
                    
                    <div class="alert-message">
                        <h3 style="margin-top: 0;">Alert Message</h3>
                        <p>{alert.message}</p>
                    </div>
                    
                    <div class="info-box">
                        <h3 style="margin-top: 0;">Additional Information</h3>
                        <table>
        """
        
        # metadata
        for key, value in alert.metadata.items():
            html += f"<tr><td>{key.replace('_', ' ').capitalize()}</td><td>{value}</td></tr>"
        
        html += """
                        </table>
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Earthquake & Flood Early Warning System</strong></p>
                    <p>This is an automated alert. Please take appropriate precautions based on the alert level.</p>
                    <p>For more information, contact your local emergency management office.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def log_alert(self, alert, log_file='logs/alerts.log'):
        log_path = Path.cwd() / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        log_entry = (
            f"{alert.timestamp.isoformat()} | "
            f"{alert.level.name:8s} | "
            f"{alert.hazard_type:10s} | "
            f"{alert.location:30s} | "
            f"{alert.probability:.3f} | "
            f"{alert.alert_id}\n"
        )
        
        with open(log_path, 'a') as f:
            f.write(log_entry)
        
        self.logger.debug(f"Alert logged to {log_path}")
    
    def send_alert(self, alert, channels=['email', 'log']):
        results = {}
        
        if 'email' in channels:
            results['email'] = self.send_email_alert(alert)
        
        if 'log' in channels:
            self.log_alert(alert)
            results['log'] = True
        
        return results