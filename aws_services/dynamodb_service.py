"""
DynamoDB Service – orders, products, customers tables
"""

from __future__ import annotations
import logging
import os
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

ORDERS_TABLE    = os.environ.get("DYNAMODB_ORDERS_TABLE",    "ecommerce_orders")
PRODUCTS_TABLE  = os.environ.get("DYNAMODB_PRODUCTS_TABLE",  "ecommerce_products")
CUSTOMERS_TABLE = os.environ.get("DYNAMODB_CUSTOMERS_TABLE", "ecommerce_customers")
REGION          = os.environ.get("AWS_REGION", "us-east-1")


class DynamoDBService:
    def __init__(self):
        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=REGION)
            self.orders_table    = self.dynamodb.Table(ORDERS_TABLE)
            self.products_table  = self.dynamodb.Table(PRODUCTS_TABLE)
            self.customers_table = self.dynamodb.Table(CUSTOMERS_TABLE)
            logger.info("DynamoDB connected (region=%s)", REGION)
        except (NoCredentialsError, Exception) as e:
            logger.warning("DynamoDB init error: %s", e)
            self.dynamodb = self.orders_table = self.products_table = self.customers_table = None

    # ── Orders ────────────────────────────────────────────────────────────────

    def scan_orders(self) -> list[dict]:
        if not self.orders_table:
            raise RuntimeError("DynamoDB not available")
        response = self.orders_table.scan()
        items    = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.orders_table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items   += response.get("Items", [])
        return items

    def put_order(self, order: dict) -> bool:
        if not self.orders_table:
            return False
        try:
            self.orders_table.put_item(Item=self._sanitize(order))
            return True
        except ClientError as e:
            logger.error("put_order error: %s", e)
            return False

    def get_order(self, order_id: str) -> dict | None:
        if not self.orders_table:
            return None
        try:
            resp = self.orders_table.get_item(Key={"order_id": order_id})
            return resp.get("Item")
        except ClientError as e:
            logger.error("get_order error: %s", e)
            return None

    @staticmethod
    def _sanitize(obj):
        """Recursively convert floats → Decimal for DynamoDB compatibility."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        if isinstance(obj, dict):
            return {k: DynamoDBService._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DynamoDBService._sanitize(i) for i in obj]
        return obj

    def bulk_load_orders(self, orders: list[dict]) -> int:
        if not self.orders_table:
            raise RuntimeError("DynamoDB not available")
        count = 0
        with self.orders_table.batch_writer() as batch:
            for order in orders:
                batch.put_item(Item=self._sanitize(order))
                count += 1
        return count

    # ── Products ─────────────────────────────────────────────────────────────

    def scan_products(self) -> list[dict]:
        if not self.products_table:
            raise RuntimeError("DynamoDB not available")
        return self.products_table.scan().get("Items", [])

    def put_product(self, product: dict) -> bool:
        if not self.products_table:
            return False
        try:
            self.products_table.put_item(Item=self._sanitize(product))
            return True
        except ClientError as e:
            logger.error("put_product error: %s", e)
            return False

    # ── Table provisioning (called from deployment scripts) ──────────────────

    @staticmethod
    def create_tables(region: str = REGION):
        client = boto3.client("dynamodb", region_name=region)

        tables = [
            {
                "TableName": ORDERS_TABLE,
                "KeySchema": [{"AttributeName": "order_id", "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": "order_id", "AttributeType": "S"}],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": PRODUCTS_TABLE,
                "KeySchema": [{"AttributeName": "product_id", "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": "product_id", "AttributeType": "S"}],
                "BillingMode": "PAY_PER_REQUEST",
            },
            {
                "TableName": CUSTOMERS_TABLE,
                "KeySchema": [{"AttributeName": "customer_id", "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": "customer_id", "AttributeType": "S"}],
                "BillingMode": "PAY_PER_REQUEST",
            },
        ]

        existing = {t["TableName"] for t in client.list_tables().get("TableNames", [])}
        for tdef in tables:
            if tdef["TableName"] not in existing:
                client.create_table(**tdef)
                logger.info("Created table: %s", tdef["TableName"])
            else:
                logger.info("Table already exists: %s", tdef["TableName"])
