"""
AWS Lambda Function – Analytics Processor
Triggered by:
  1. EventBridge scheduled rule (daily report generation)
  2. SQS queue messages (heavy analytics tasks)
"""

import json
import os
import logging
import boto3
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION           = os.environ.get("AWS_REGION",            "us-east-1")
ORDERS_TABLE     = os.environ.get("DYNAMODB_ORDERS_TABLE", "ecommerce_orders")
S3_BUCKET        = os.environ.get("S3_BUCKET_NAME",        "voice-ecommerce-reports")
SES_SENDER       = os.environ.get("SES_SENDER_EMAIL",      "analytics@yourdomain.com")
REPORT_RECIPIENT = os.environ.get("REPORT_RECIPIENT_EMAIL","admin@yourdomain.com")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
s3       = boto3.client("s3",         region_name=REGION)
ses      = boto3.client("ses",        region_name=REGION)


# ── Step 1: Get all orders from DynamoDB ─────────────────────────────────────

def scan_all_orders():
    table    = dynamodb.Table(ORDERS_TABLE)
    response = table.scan()
    items    = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items   += response.get("Items", [])
    return items


# ── Step 2: Calculate analytics from orders ───────────────────────────────────

def compute_analytics(orders):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    today_orders = [o for o in orders if o.get("order_date", "").startswith(today)]
    month_orders = [o for o in orders if o.get("order_date", "").startswith(month)]

    def revenue(lst):
        return round(sum(float(o.get("price", 0)) * int(o.get("quantity", 1)) for o in lst), 2)

    cat_totals = defaultdict(float)
    for o in orders:
        cat_totals[o.get("category", "Other")] += float(o.get("price", 0)) * int(o.get("quantity", 1))

    prod_counts = defaultdict(int)
    for o in orders:
        prod_counts[o.get("product_name", "Unknown")] += int(o.get("quantity", 1))

    top_product = max(prod_counts, key=lambda k: prod_counts[k]) if prod_counts else "N/A"

    return {
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "total_orders":     len(orders),
        "today_revenue":    revenue(today_orders),
        "today_orders":     len(today_orders),
        "monthly_revenue":  revenue(month_orders),
        "monthly_orders":   len(month_orders),
        "category_revenue": {k: round(v, 2) for k, v in cat_totals.items()},
        "top_product":      top_product,
        "top_product_qty":  prod_counts.get(top_product, 0),
        "avg_order_value":  round(revenue(orders) / len(orders), 2) if orders else 0,
    }


# ── Step 3: Save report to S3 ─────────────────────────────────────────────────

def save_report_to_s3(report, report_type="daily"):
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = f"reports/{report_type}_{ts}.json"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(report, indent=2),
        ContentType="application/json",
    )

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=86400,
    )

    logger.info("Report saved: s3://%s/%s", S3_BUCKET, key)
    return url


# ── Step 4: Send email via SES ────────────────────────────────────────────────

def send_report_email(report, report_url, report_type="daily"):
    subject = f"Analytics Report - {report_type.capitalize()} Summary"

    body_html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px">
      <h2 style="color:#10b981">Analytics Report Ready</h2>
      <table style="width:100%;border-collapse:collapse">
        <tr style="background:#f4f4f4">
          <td style="padding:10px;border:1px solid #ddd"><strong>Today Revenue</strong></td>
          <td style="padding:10px;border:1px solid #ddd">${report['today_revenue']:,.2f}</td>
        </tr>
        <tr>
          <td style="padding:10px;border:1px solid #ddd"><strong>Monthly Revenue</strong></td>
          <td style="padding:10px;border:1px solid #ddd">${report['monthly_revenue']:,.2f}</td>
        </tr>
        <tr style="background:#f4f4f4">
          <td style="padding:10px;border:1px solid #ddd"><strong>Total Orders</strong></td>
          <td style="padding:10px;border:1px solid #ddd">{report['total_orders']}</td>
        </tr>
        <tr>
          <td style="padding:10px;border:1px solid #ddd"><strong>Top Product</strong></td>
          <td style="padding:10px;border:1px solid #ddd">{report['top_product']}</td>
        </tr>
        <tr style="background:#f4f4f4">
          <td style="padding:10px;border:1px solid #ddd"><strong>Avg Order Value</strong></td>
          <td style="padding:10px;border:1px solid #ddd">${report['avg_order_value']:,.2f}</td>
        </tr>
      </table>
      <br>
      <a href="{report_url}"
         style="background:#10b981;color:white;padding:12px 24px;
                text-decoration:none;border-radius:6px;display:inline-block">
        Download Full Report
      </a>
      <p style="color:#999;font-size:12px;margin-top:20px">
        Sent by Voice-Driven eCommerce Analytics Dashboard
      </p>
    </body>
    </html>
    """

    body_text = f"""
    Analytics Report - {report_type}
    
    Today Revenue   : ${report['today_revenue']:,.2f}
    Monthly Revenue : ${report['monthly_revenue']:,.2f}
    Total Orders    : {report['total_orders']}
    Top Product     : {report['top_product']}
    Avg Order Value : ${report['avg_order_value']:,.2f}
    
    Download: {report_url}
    """

    try:
        ses.send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [REPORT_RECIPIENT]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": body_html},
                    "Text": {"Data": body_text},
                },
            },
        )
        logger.info("Email sent to %s", REPORT_RECIPIENT)
    except Exception as e:
        logger.error("Email failed: %s", e)


# ── Main Lambda Handler ───────────────────────────────────────────────────────

def lambda_handler(event, context):
    logger.info("Lambda triggered. Event: %s", json.dumps(event))

    # ── Triggered by EventBridge (daily schedule) ─────────────────────────
    if "source" in event and event.get("source") == "aws.events":
        logger.info("EventBridge trigger - generating daily report")
        try:
            orders = scan_all_orders()
            report = compute_analytics(orders)
            url    = save_report_to_s3(report, "daily")
            send_report_email(report, url, "daily")
            return {
                "statusCode": 200,
                "body": json.dumps({"status": "ok", "url": url})
            }
        except Exception as e:
            logger.error("Daily report error: %s", e)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)})
            }

    # ── Triggered by SQS ──────────────────────────────────────────────────
    if "Records" in event:
        results = []
        for record in event["Records"]:
            try:
                body  = json.loads(record.get("body", "{}"))
                query = body.get("query", "")
                logger.info("SQS task received: %s", query)
                orders = scan_all_orders()
                report = compute_analytics(orders)
                url    = save_report_to_s3(report, "on-demand")
                results.append({"query": query, "url": url})
            except Exception as e:
                logger.error("SQS record error: %s", e)
        return {
            "statusCode": 200,
            "body": json.dumps(results)
        }

    # ── Direct test invocation ────────────────────────────────────────────
    try:
        orders = scan_all_orders()
        report = compute_analytics(orders)
        url    = save_report_to_s3(report, "manual")
        send_report_email(report, url, "manual")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status":  "ok",
                "url":     url,
                "report":  report
            })
        }
    except Exception as e:
        logger.error("Direct invocation error: %s", e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
