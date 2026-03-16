"""
Amazon SES Service – send analytics reports via email
"""

from __future__ import annotations
import logging
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION       = os.environ.get("AWS_REGION",       "us-east-1")
SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "analytics@yourdomain.com")


class SESService:
    def __init__(self):
        try:
            self.ses = boto3.client("ses", region_name=REGION)
            logger.info("SES client ready")
        except (NoCredentialsError, Exception) as e:
            logger.warning("SES init error: %s", e)
            self.ses = None

    def send_report_email(self, to_email: str, report_type: str, report_url: str) -> bool:
        if not self.ses:
            logger.warning("SES unavailable – email not sent")
            return False

        subject = f"Analytics Report: {report_type.capitalize()} Summary"
        body_html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px">
        <div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:8px">
          <h2 style="color:#10b981">📊 {subject}</h2>
          <p>Your <strong>{report_type}</strong> analytics report is ready.</p>
          <a href="{report_url}" style="display:inline-block;padding:12px 24px;
             background:#10b981;color:#fff;border-radius:6px;text-decoration:none">
            Download Report
          </a>
          <p style="color:#666;font-size:12px;margin-top:24px">
            Sent by Voice-Driven eCommerce Analytics Dashboard
          </p>
        </div>
        </body></html>
        """
        body_text = f"{subject}\n\nDownload your report: {report_url}"

        try:
            self.ses.send_email(
                Source=SENDER_EMAIL,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Html": {"Data": body_html},
                        "Text": {"Data": body_text},
                    },
                },
            )
            logger.info("Report email sent to %s", to_email)
            return True
        except ClientError as e:
            logger.error("SES send_email error: %s", e)
            return False

    def send_alert_email(self, to_email: str, alert_type: str, message: str) -> bool:
        if not self.ses:
            return False
        subject = f"Analytics Alert: {alert_type}"
        try:
            self.ses.send_email(
                Source=SENDER_EMAIL,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": message}},
                },
            )
            return True
        except ClientError as e:
            logger.error("SES alert error: %s", e)
            return False