"""
Amazon Rekognition Service – product image analysis
"""

from __future__ import annotations
import logging
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION         = os.environ.get("AWS_REGION",               "us-east-1")
MAX_LABELS     = int(os.environ.get("REKOGNITION_MAX_LABELS",     "10"))
MIN_CONFIDENCE = float(os.environ.get("REKOGNITION_MIN_CONFIDENCE","75.0"))


class RekognitionService:
    def __init__(self):
        try:
            self.rekog = boto3.client("rekognition", region_name=REGION)
            logger.info("Rekognition client ready")
        except (NoCredentialsError, Exception) as e:
            logger.warning("Rekognition init error: %s", e)
            self.rekog = None

    def detect_labels(self, image_bytes: bytes) -> list[dict]:
        if not self.rekog:
            return self._mock_labels()
        try:
            resp = self.rekog.detect_labels(
                Image={"Bytes": image_bytes},
                MaxLabels=MAX_LABELS,
                MinConfidence=MIN_CONFIDENCE,
            )
            return [
                {"name": lbl["Name"], "confidence": round(lbl["Confidence"], 2)}
                for lbl in resp.get("Labels", [])
            ]
        except ClientError as e:
            logger.error("detect_labels error: %s", e)
            return []

    def detect_text(self, image_bytes: bytes) -> list[str]:
        if not self.rekog:
            return []
        try:
            resp = self.rekog.detect_text(Image={"Bytes": image_bytes})
            return [d["DetectedText"] for d in resp.get("TextDetections", [])
                    if d["Type"] == "LINE"]
        except ClientError as e:
            logger.error("detect_text error: %s", e)
            return []

    def detect_faces(self, image_bytes: bytes) -> dict:
        if not self.rekog:
            return {"count": 0, "details": []}
        try:
            resp = self.rekog.detect_faces(
                Image={"Bytes": image_bytes},
                Attributes=["ALL"],
            )
            faces = resp.get("FaceDetails", [])
            return {
                "count":   len(faces),
                "details": [
                    {
                        "confidence": round(f.get("Confidence", 0), 2),
                        "age_range":  f.get("AgeRange", {}),
                        "emotions":   [e["Type"] for e in f.get("Emotions", [])
                                       if e["Confidence"] > 50],
                    }
                    for f in faces
                ],
            }
        except ClientError as e:
            logger.error("detect_faces error: %s", e)
            return {"count": 0, "details": []}

    @staticmethod
    def _mock_labels() -> list[dict]:
        return [
            {"name": "Electronics", "confidence": 98.5},
            {"name": "Device",      "confidence": 96.2},
            {"name": "Gadget",      "confidence": 91.0},
        ]