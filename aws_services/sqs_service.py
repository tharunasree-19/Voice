"""
Amazon SQS Service – queue heavy analytics tasks
"""

from __future__ import annotations
import json
import logging
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION    = os.environ.get("AWS_REGION",    "us-east-1")
QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")


class SQSService:
    def __init__(self):
        try:
            self.sqs = boto3.client("sqs", region_name=REGION)
            logger.info("SQS client ready")
        except (NoCredentialsError, Exception) as e:
            logger.warning("SQS init error: %s", e)
            self.sqs = None

    def enqueue_task(self, task: dict, queue_url: str = QUEUE_URL) -> bool:
        if not self.sqs or not queue_url:
            logger.warning("SQS unavailable or no queue URL – task not queued")
            return False
        try:
            self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(task),
            )
            logger.info("Task enqueued: %s", task.get("query", ""))
            return True
        except ClientError as e:
            logger.error("SQS send_message error: %s", e)
            return False

    def receive_tasks(self, queue_url: str = QUEUE_URL, max_messages: int = 5) -> list[dict]:
        if not self.sqs or not queue_url:
            return []
        try:
            resp = self.sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=5,
            )
            messages = []
            for msg in resp.get("Messages", []):
                messages.append({
                    "receipt_handle": msg["ReceiptHandle"],
                    "body":           json.loads(msg["Body"]),
                })
            return messages
        except ClientError as e:
            logger.error("SQS receive_message error: %s", e)
            return []

    def delete_task(self, receipt_handle: str, queue_url: str = QUEUE_URL) -> bool:
        if not self.sqs or not queue_url:
            return False
        try:
            self.sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
            return True
        except ClientError as e:
            logger.error("SQS delete_message error: %s", e)
            return False

    def create_queue(self, queue_name: str = "analytics-tasks") -> str | None:
        if not self.sqs:
            return None
        try:
            resp = self.sqs.create_queue(
                QueueName=queue_name,
                Attributes={"MessageRetentionPeriod": "86400"},
            )
            url = resp["QueueUrl"]
            logger.info("SQS queue created: %s", url)
            return url
        except ClientError as e:
            logger.error("create_queue error: %s", e)
            return None