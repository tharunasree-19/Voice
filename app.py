"""
Voice-Driven eCommerce Analytics Dashboard
Flask Backend Application
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from functools import wraps

from config import Config
from analytics.analytics_engine import AnalyticsEngine
from aws_services.dynamodb_service import DynamoDBService
from aws_services.polly_service import PollyService
from aws_services.s3_service import S3Service
from aws_services.ses_service import SESService
from aws_services.sqs_service import SQSService
from aws_services.rekognition_service import RekognitionService

# ─── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Service Singletons ───────────────────────────────────────────────────────

dynamodb = DynamoDBService()
polly    = PollyService()
s3       = S3Service()
ses      = SESService()
sqs      = SQSService()
rekognition = RekognitionService()
analytics   = AnalyticsEngine(dynamodb)

# ─── Auth Helpers ─────────────────────────────────────────────────────────────

DEMO_USERS = {
    "admin": {"password": "admin123", "name": "Admin User",  "role": "admin"},
    "analyst": {"password": "analyst123", "name": "Data Analyst", "role": "analyst"},
    "demo":  {"password": "demo",     "name": "Demo User",   "role": "viewer"},
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET"])
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    data     = request.get_json() or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = DEMO_USERS.get(username)
    if user and user["password"] == password:
        session["user"]     = username
        session["name"]     = user["name"]
        session["role"]     = user["role"]
        session.permanent   = True
        logger.info("Login success: %s", username)
        return jsonify({"success": True, "redirect": url_for("dashboard")})

    logger.warning("Login failed: %s", username)
    return jsonify({"success": False, "message": "Invalid credentials"}), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        summary = analytics.get_dashboard_summary()
    except Exception as e:
        logger.error("Dashboard summary error: %s", e)
        summary = {}
    return render_template(
        "dashboard.html",
        user=session.get("name"),
        role=session.get("role"),
        summary=summary,
    )


@app.route("/reports")
@login_required
def reports():
    try:
        report_list = s3.list_reports()
    except Exception as e:
        logger.error("List reports error: %s", e)
        report_list = []
    return render_template(
        "reports.html",
        user=session.get("name"),
        role=session.get("role"),
        reports=report_list,
    )


# ─── Analytics API ────────────────────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    """
    Receive a natural-language query, run analytics, optionally
    synthesise speech via Polly, return JSON.
    """
    payload = request.get_json(silent=True) or {}
    query   = payload.get("query", "").strip()
    voice   = payload.get("voice", False)          # bool – caller wants audio

    if not query:
        return jsonify({"error": "No query provided"}), 400

    logger.info("Analyze query from %s: %s", session.get("user"), query)

    try:
        result = analytics.process_query(query)
    except Exception as e:
        logger.error("Analytics error: %s", e)
        return jsonify({"error": str(e)}), 500

    # ── Optional Polly TTS ──────────────────────────────────────────────────
    audio_url = None
    if voice and result.get("text"):
        try:
            audio_url = polly.synthesize(result["text"])
        except Exception as e:
            logger.warning("Polly failed: %s", e)

    # ── Optionally queue heavy task to SQS ──────────────────────────────────
    if result.get("heavy"):
        try:
            sqs.enqueue_task({"query": query, "user": session.get("user")})
        except Exception as e:
            logger.warning("SQS enqueue failed: %s", e)

    return jsonify({**result, "audio_url": audio_url})


@app.route("/api/chart-data/<chart_type>")
@login_required
def chart_data(chart_type):
    """Return chart-ready JSON for Chart.js."""
    try:
        data = analytics.get_chart_data(chart_type)
        return jsonify(data)
    except Exception as e:
        logger.error("Chart data error (%s): %s", chart_type, e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-report", methods=["POST"])
@login_required
def generate_report():
    """Generate a PDF/JSON report, store in S3, notify via SES."""
    payload     = request.get_json(silent=True) or {}
    report_type = payload.get("type", "daily")
    email       = payload.get("email", "")

    try:
        report_data = analytics.generate_report(report_type)
        s3_url      = s3.upload_report(report_data, report_type)

        if email:
            ses.send_report_email(email, report_type, s3_url)

        return jsonify({"success": True, "url": s3_url, "message": "Report generated"})
    except Exception as e:
        logger.error("Report generation error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze-image", methods=["POST"])
@login_required
def analyze_image():
    """Run Rekognition label detection on an uploaded product image."""
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    image_file = request.files["image"]
    try:
        labels = rekognition.detect_labels(image_file.read())
        return jsonify({"labels": labels})
    except Exception as e:
        logger.error("Rekognition error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/load-sample-data", methods=["POST"])
@login_required
def load_sample_data():
    """Load sample_orders.json into DynamoDB (dev/demo only)."""
    sample_file = os.path.join(os.path.dirname(__file__), "data", "sample_orders.json")
    if not os.path.exists(sample_file):
        return jsonify({"error": "Sample data file not found"}), 404

    with open(sample_file) as f:
        orders = json.load(f)

    try:
        count = dynamodb.bulk_load_orders(orders)
        return jsonify({"success": True, "loaded": count})
    except Exception as e:
        logger.error("Data load error: %s", e)
        return jsonify({"error": str(e)}), 500


# ─── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("login.html", error="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)