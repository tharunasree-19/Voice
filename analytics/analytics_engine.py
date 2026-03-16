"""
Analytics Engine
Processes natural-language queries and returns structured results.
Falls back to in-memory sample data when DynamoDB is unreachable.
"""

from __future__ import annotations

import json
import os
import re
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Fallback sample data path ──────────────────────────────────────────────────
_SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sample_orders.json")


def _load_sample() -> list[dict]:
    try:
        with open(_SAMPLE_FILE) as f:
            return json.load(f)
    except Exception:
        return []


class AnalyticsEngine:
    def __init__(self, dynamodb_service=None):
        self.db = dynamodb_service
        self._sample: list[dict] | None = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _data(self) -> list[dict]:
        """Return orders from DynamoDB or fall back to sample JSON."""
        if self.db:
            try:
                return self.db.scan_orders()
            except Exception as e:
                logger.warning("DynamoDB unavailable, using sample data: %s", e)
        if self._sample is None:
            self._sample = _load_sample()
        return self._sample

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _this_month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    # ── Core analytics ────────────────────────────────────────────────────────

    def total_sales_today(self) -> dict:
        today  = self._today()
        orders = [o for o in self._data() if o.get("order_date", "").startswith(today)]
        revenue = sum(float(o.get("price", 0)) * int(o.get("quantity", 1)) for o in orders)
        return {
            "type": "total_sales_today",
            "value": round(revenue, 2),
            "count": len(orders),
            "text": f"Today's total revenue is {revenue:,.2f} dollars from {len(orders)} orders.",
        }

    def top_selling_product(self) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for o in self._data():
            counts[o.get("product_name", "Unknown")] += int(o.get("quantity", 1))
        if not counts:
            return {"type": "top_product", "text": "No product data available.", "value": None}
        top = max(counts, key=lambda k: counts[k])
        return {
            "type": "top_product",
            "value": top,
            "quantity": counts[top],
            "text": f"The top selling product is {top} with {counts[top]} units sold.",
        }

    def monthly_revenue(self) -> dict:
        month  = self._this_month()
        orders = [o for o in self._data() if o.get("order_date", "").startswith(month)]
        revenue = sum(float(o.get("price", 0)) * int(o.get("quantity", 1)) for o in orders)
        return {
            "type": "monthly_revenue",
            "value": round(revenue, 2),
            "count": len(orders),
            "text": f"This month's total revenue is {revenue:,.2f} dollars from {len(orders)} orders.",
        }

    def category_sales(self) -> dict:
        totals: dict[str, float] = defaultdict(float)
        for o in self._data():
            cat = o.get("category", "Other")
            totals[cat] += float(o.get("price", 0)) * int(o.get("quantity", 1))
        totals = {k: round(v, 2) for k, v in totals.items()}
        top_cat = max(totals, key=lambda k: totals[k]) if totals else "N/A"
        return {
            "type": "category_sales",
            "data": totals,
            "top_category": top_cat,
            "text": f"Top category by revenue is {top_cat} with ${totals.get(top_cat, 0):,.2f}.",
        }

    def total_orders(self) -> dict:
        count = len(self._data())
        return {
            "type": "total_orders",
            "value": count,
            "text": f"There are {count} total orders in the system.",
        }

    def revenue_last_7_days(self) -> dict:
        result = {}
        for i in range(6, -1, -1):
            day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            orders = [o for o in self._data() if o.get("order_date", "").startswith(day)]
            result[day] = round(
                sum(float(o.get("price", 0)) * int(o.get("quantity", 1)) for o in orders), 2
            )
        return {"type": "revenue_7days", "data": result,
                "text": "Here is the revenue trend for the last 7 days."}

    def average_order_value(self) -> dict:
        orders = self._data()
        if not orders:
            return {"type": "avg_order", "value": 0, "text": "No orders found."}
        total = sum(float(o.get("price", 0)) * int(o.get("quantity", 1)) for o in orders)
        avg   = round(total / len(orders), 2)
        return {
            "type": "avg_order",
            "value": avg,
            "text": f"The average order value is {avg} dollars.",
        }

    # ── Query router ──────────────────────────────────────────────────────────

    def process_query(self, query: str) -> dict:
        q = query.lower()

        if re.search(r"today.*(sale|revenue|total)", q) or re.search(r"(sale|revenue).*today", q):
            return self.total_sales_today()
        if re.search(r"top.*product|best.*sell|most.*sold", q):
            return self.top_selling_product()
        if re.search(r"month.*revenue|revenue.*month|monthly", q):
            return self.monthly_revenue()
        if re.search(r"categor", q):
            return self.category_sales()
        if re.search(r"(total|how many|number of).*order|order.*total", q):
            return self.total_orders()
        if re.search(r"7 day|week|trend|last.*(week|7)", q):
            return self.revenue_last_7_days()
        if re.search(r"average|avg|mean", q):
            return self.average_order_value()
        if re.search(r"summary|overview|dashboard", q):
            return self.get_dashboard_summary()

        return {
            "type": "unknown",
            "text": (
                "I can answer questions about: today's sales, top products, "
                "monthly revenue, category sales, total orders, 7-day trend, "
                "and average order value."
            ),
            "suggestions": [
                "What are today's total sales?",
                "Which product sold the most?",
                "Show monthly revenue",
                "Show revenue by category",
            ],
        }

    # ── Dashboard summary ─────────────────────────────────────────────────────

    def get_dashboard_summary(self) -> dict:
        try:
            return {
                "total_sales_today": self.total_sales_today()["value"],
                "top_product":       self.top_selling_product()["value"],
                "monthly_revenue":   self.monthly_revenue()["value"],
                "total_orders":      self.total_orders()["value"],
                "avg_order_value":   self.average_order_value()["value"],
                "category_sales":    self.category_sales()["data"],
            }
        except Exception as e:
            logger.error("Dashboard summary error: %s", e)
            return {}

    # ── Chart data ────────────────────────────────────────────────────────────

    def get_chart_data(self, chart_type: str) -> dict:
        if chart_type == "revenue_7days":
            raw = self.revenue_last_7_days()["data"]
            return {
                "labels":   list(raw.keys()),
                "datasets": [{"label": "Revenue ($)", "data": list(raw.values()),
                               "borderColor": "#6ee7b7", "backgroundColor": "rgba(110,231,183,0.15)",
                               "fill": True, "tension": 0.4}],
            }
        if chart_type == "category":
            raw = self.category_sales()["data"]
            colors = ["#6ee7b7","#34d399","#10b981","#059669","#047857","#065f46","#a7f3d0"]
            return {
                "labels":   list(raw.keys()),
                "datasets": [{"label": "Revenue by Category", "data": list(raw.values()),
                               "backgroundColor": colors[:len(raw)]}],
            }
        if chart_type == "top_products":
            counts: dict[str, int] = defaultdict(int)
            for o in self._data():
                counts[o.get("product_name", "Unknown")] += int(o.get("quantity", 1))
            top10 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "labels":   [t[0] for t in top10],
                "datasets": [{"label": "Units Sold", "data": [t[1] for t in top10],
                               "backgroundColor": "#6ee7b7"}],
            }
        return {}

    # ── Report generation ─────────────────────────────────────────────────────

    def generate_report(self, report_type: str = "daily") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "type":              report_type,
            "generated_at":      now,
            "total_sales_today": self.total_sales_today(),
            "monthly_revenue":   self.monthly_revenue(),
            "top_product":       self.top_selling_product(),
            "category_sales":    self.category_sales(),
            "total_orders":      self.total_orders(),
            "avg_order_value":   self.average_order_value(),
        }