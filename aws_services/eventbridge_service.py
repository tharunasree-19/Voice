"""
Amazon EventBridge Service – schedule daily analytics workflows
"""

from __future__ import annotations
import json
import logging
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION = os.environ.get("AWS_REGION",       "us-east-1")
BUS    = os.environ.get("EVENTBRIDGE_BUS",  "default")


class EventBridgeService:
    def __init__(self):
        try:
            self.events = boto3.client("events", region_name=REGION)
            logger.info("EventBridge client ready")
        except (NoCredentialsError, Exception) as e:
            logger.warning("EventBridge init error: %s", e)
            self.events = None

    def put_event(self, detail: dict, source: str = "ecommerce.analytics",
                  detail_type: str = "AnalyticsEvent") -> bool:
        if not self.events:
            return False
        try:
            self.events.put_events(
                Entries=[{
                    "Source":       source,
                    "DetailType":   detail_type,
                    "Detail":       json.dumps(detail),
                    "EventBusName": BUS,
                }]
            )
            logger.info("EventBridge event sent: %s", detail_type)
            return True
        except ClientError as e:
            logger.error("put_event error: %s", e)
            return False

    def create_daily_report_rule(self, lambda_arn: str, hour: int = 7) -> bool:
        """Create a cron rule to trigger daily report generation at *hour*:00 UTC."""
        if not self.events:
            return False
        rule_name = "daily-analytics-report"
        try:
            self.events.put_rule(
                Name=rule_name,
                ScheduleExpression=f"cron(0 {hour} * * ? *)",
                State="ENABLED",
                Description="Daily eCommerce analytics report generation",
            )
            self.events.put_targets(
                Rule=rule_name,
                Targets=[{"Id": "DailyReportLambda", "Arn": lambda_arn}],
            )
            logger.info("EventBridge daily rule created: %s", rule_name)
            return True
        except ClientError as e:
            logger.error("create_daily_report_rule error: %s", e)
            return False

    def list_rules(self) -> list[dict]:
        if not self.events:
            return []
        try:
            return self.events.list_rules().get("Rules", [])
        except ClientError as e:
            logger.error("list_rules error: %s", e)
            return []