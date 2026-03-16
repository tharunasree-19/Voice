"""
Amazon S3 Service – report storage and retrieval
"""

from __future__ import annotations
import json
import logging
import os
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION         = os.environ.get("AWS_REGION",         "us-east-1")
BUCKET         = os.environ.get("S3_BUCKET_NAME",      "voice-ecommerce-reports")
REPORTS_PREFIX = os.environ.get("S3_REPORTS_PREFIX",   "reports/")


class S3Service:
    def __init__(self):
        try:
            self.s3 = boto3.client("s3", region_name=REGION)
            logger.info("S3 client ready (bucket=%s)", BUCKET)
        except (NoCredentialsError, Exception) as e:
            logger.warning("S3 init error: %s", e)
            self.s3 = None

    # ── Bucket provisioning ───────────────────────────────────────────────────

    def ensure_bucket(self) -> bool:
        if not self.s3:
            return False
        try:
            if REGION == "us-east-1":
                self.s3.create_bucket(Bucket=BUCKET)
            else:
                self.s3.create_bucket(
                    Bucket=BUCKET,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )
            # Block all public access
            self.s3.put_public_access_block(
                Bucket=BUCKET,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True, "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
                },
            )
            logger.info("Bucket created: %s", BUCKET)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
                return True
            logger.error("ensure_bucket error: %s", e)
            return False

    # ── Report operations ─────────────────────────────────────────────────────

    def upload_report(self, report_data: dict, report_type: str = "daily") -> str:
        if not self.s3:
            raise RuntimeError("S3 not available")

        ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"{REPORTS_PREFIX}{report_type}_{ts}_{uuid.uuid4().hex[:6]}.json"

        self.s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(report_data, indent=2, default=str),
            ContentType="application/json",
        )

        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=86400,        # 24 h
        )
        logger.info("Report uploaded: s3://%s/%s", BUCKET, key)
        return url

    def list_reports(self, prefix: str = REPORTS_PREFIX) -> list[dict]:
        if not self.s3:
            return self._mock_reports()

        try:
            resp  = self.s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
            items = []
            for obj in resp.get("Contents", []):
                url = self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": BUCKET, "Key": obj["Key"]},
                    ExpiresIn=3600,
                )
                items.append({
                    "key":           obj["Key"],
                    "size":          obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "url":           url,
                    "name":          os.path.basename(obj["Key"]),
                })
            return sorted(items, key=lambda x: x["last_modified"], reverse=True)
        except ClientError as e:
            logger.error("list_reports error: %s", e)
            return self._mock_reports()

    def download_report(self, key: str) -> bytes | None:
        if not self.s3:
            return None
        try:
            resp = self.s3.get_object(Bucket=BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            logger.error("download_report error: %s", e)
            return None

    # ── Fallback ──────────────────────────────────────────────────────────────

    @staticmethod
    def _mock_reports() -> list[dict]:
        return [
            {"name": "daily_20250101_120000.json", "key": "reports/daily_20250101.json",
             "size": 2048, "last_modified": "2025-01-01T12:00:00+00:00", "url": "#"},
            {"name": "monthly_20241201_080000.json", "key": "reports/monthly_20241201.json",
             "size": 8192, "last_modified": "2024-12-01T08:00:00+00:00", "url": "#"},
        ]