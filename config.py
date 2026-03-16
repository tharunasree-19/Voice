"""
Configuration for Voice-Driven eCommerce Analytics Dashboard
"""

import os
from datetime import timedelta


class Config:
    # ── Flask Core ──────────────────────────────────────────────────────────
    SECRET_KEY            = os.environ.get("SECRET_KEY", "change-me-in-production-abc123")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = "Lax"

    # ── AWS General ─────────────────────────────────────────────────────────
    AWS_REGION            = os.environ.get("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID     = os.environ.get("AWS_ACCESS_KEY_ID")      # leave None → IAM role
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

    # ── DynamoDB ────────────────────────────────────────────────────────────
    DYNAMODB_ORDERS_TABLE    = os.environ.get("DYNAMODB_ORDERS_TABLE",    "ecommerce_orders")
    DYNAMODB_PRODUCTS_TABLE  = os.environ.get("DYNAMODB_PRODUCTS_TABLE",  "ecommerce_products")
    DYNAMODB_CUSTOMERS_TABLE = os.environ.get("DYNAMODB_CUSTOMERS_TABLE", "ecommerce_customers")

    # ── S3 ──────────────────────────────────────────────────────────────────
    S3_BUCKET_NAME   = os.environ.get("S3_BUCKET_NAME",   "voice-ecommerce-reports")
    S3_REPORTS_PREFIX = os.environ.get("S3_REPORTS_PREFIX", "reports/")
    S3_AUDIO_PREFIX   = os.environ.get("S3_AUDIO_PREFIX",   "audio/")

    # ── Amazon Polly ────────────────────────────────────────────────────────
    POLLY_VOICE_ID   = os.environ.get("POLLY_VOICE_ID",  "Joanna")
    POLLY_OUTPUT_FORMAT = "mp3"

    # ── SES ─────────────────────────────────────────────────────────────────
    SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "analytics@yourdomain.com")

    # ── SQS ─────────────────────────────────────────────────────────────────
    SQS_QUEUE_URL    = os.environ.get("SQS_QUEUE_URL", "")

    # ── EventBridge ─────────────────────────────────────────────────────────
    EVENTBRIDGE_BUS  = os.environ.get("EVENTBRIDGE_BUS", "default")

    # ── Rekognition ─────────────────────────────────────────────────────────
    REKOGNITION_MAX_LABELS     = 10
    REKOGNITION_MIN_CONFIDENCE = 75.0

    # ── Application ─────────────────────────────────────────────────────────
    APP_NAME     = "Voice Analytics Dashboard"
    APP_VERSION  = "1.0.0"
    DEBUG        = os.environ.get("FLASK_ENV") == "development"