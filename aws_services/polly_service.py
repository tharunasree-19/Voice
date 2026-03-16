"""
Amazon Polly Service – text-to-speech synthesis
"""

from __future__ import annotations
import logging
import os
import uuid
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

REGION        = os.environ.get("AWS_REGION",        "us-east-1")
BUCKET        = os.environ.get("S3_BUCKET_NAME",     "voice-ecommerce-reports")
AUDIO_PREFIX  = os.environ.get("S3_AUDIO_PREFIX",    "audio/")
VOICE_ID      = os.environ.get("POLLY_VOICE_ID",     "Joanna")
OUTPUT_FORMAT = "mp3"


class PollyService:
    def __init__(self):
        try:
            self.polly = boto3.client("polly", region_name=REGION)
            self.s3    = boto3.client("s3",    region_name=REGION)
            logger.info("Polly client ready")
        except (NoCredentialsError, Exception) as e:
            logger.warning("Polly init error: %s", e)
            self.polly = self.s3 = None

    def synthesize(self, text: str, voice_id: str = VOICE_ID) -> str | None:
        """
        Convert *text* to speech with Polly, upload MP3 to S3,
        return a pre-signed URL valid for 1 hour.
        """
        if not self.polly:
            logger.warning("Polly unavailable – skipping TTS")
            return None

        # Truncate to Polly's 3,000-character limit
        safe_text = text[:3000]

        try:
            resp  = self.polly.synthesize_speech(
                Text=safe_text,
                OutputFormat=OUTPUT_FORMAT,
                VoiceId=voice_id,
            )
            audio_stream = resp["AudioStream"].read()
        except ClientError as e:
            logger.error("Polly synthesize_speech error: %s", e)
            return None

        # Upload to S3
        key = f"{AUDIO_PREFIX}{uuid.uuid4()}.{OUTPUT_FORMAT}"
        try:
            self.s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=audio_stream,
                ContentType=f"audio/{OUTPUT_FORMAT}",
            )
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": key},
                ExpiresIn=3600,
            )
            logger.info("Polly audio uploaded: s3://%s/%s", BUCKET, key)
            return url
        except ClientError as e:
            logger.error("S3 upload error (Polly audio): %s", e)
            return None

    def list_voices(self, language_code: str = "en-US") -> list[dict]:
        if not self.polly:
            return []
        try:
            resp = self.polly.describe_voices(LanguageCode=language_code)
            return resp.get("Voices", [])
        except ClientError as e:
            logger.error("describe_voices error: %s", e)
            return []