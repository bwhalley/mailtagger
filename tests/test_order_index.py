#!/usr/bin/env python3
"""Unit tests for order index upsert and status merge."""

import os
import tempfile
import unittest

from order_index import OrderIndex


class TestOrderIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.index = OrderIndex(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_create_order(self):
        oid = self.index.upsert_order(
            order_number="ORD-123",
            brand_domain="target.com",
            status="confirmed",
            gmail_id="g1",
            subject="Order confirmed",
        )
        self.assertIsNotNone(oid)
        order = self.index.get_order_by_id(oid)
        self.assertEqual(order["brand_domain"], "target.com")
        self.assertEqual(order["status"], "confirmed")

    def test_create_shipment(self):
        sid = self.index.upsert_shipment(
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="shipped",
            brand_domain="amazon.com",
            gmail_id="g1",
            subject="Shipped",
        )
        self.assertIsNotNone(sid)
        shipment = self.index.get_shipment_by_id(sid)
        self.assertEqual(shipment["brand_domain"], "amazon.com")
        self.assertEqual(shipment["status"], "shipped")

    def test_merge_by_tracking_number(self):
        sid1 = self.index.upsert_shipment(
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="shipped",
            brand_domain="amazon.com",
            gmail_id="g1",
            subject="Shipped",
        )
        sid2 = self.index.upsert_shipment(
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="out_for_delivery",
            brand_domain="amazon.com",
            gmail_id="g2",
            subject="Out for delivery",
        )
        self.assertEqual(sid1, sid2)
        shipment = self.index.get_shipment_by_id(sid1)
        self.assertEqual(shipment["status"], "out_for_delivery")
        self.assertEqual(len(shipment["notifications"]), 2)

    def test_status_does_not_regress(self):
        sid = self.index.upsert_shipment(
            tracking_number="9400111899223344556677",
            status="delivered",
            brand_domain="bestbuy.com",
            gmail_id="g1",
            subject="Delivered",
        )
        self.index.upsert_shipment(
            tracking_number="9400111899223344556677",
            status="shipped",
            brand_domain="bestbuy.com",
            gmail_id="g2",
            subject="Shipped",
        )
        shipment = self.index.get_shipment_by_id(sid)
        self.assertEqual(shipment["status"], "delivered")

    def test_list_open_orders(self):
        self.index.upsert_order(
            order_number="N-100",
            brand_domain="nike.com",
            status="confirmed",
            gmail_id="g1",
            subject="Thanks for your order",
        )
        self.index.upsert_shipment(
            tracking_number="123456789012",
            status="in_transit",
            source_type="carrier",
            gmail_id="g2",
            subject="In transit",
        )
        open_orders = self.index.list_orders(without_shipment=True)
        self.assertEqual(len(open_orders), 1)
        self.assertEqual(open_orders[0]["brand_domain"], "nike.com")

    def test_summary_counts(self):
        self.index.upsert_shipment(
            tracking_number="1Z999AA10123456784",
            status="in_transit",
            gmail_id="g1",
            subject="Transit",
        )
        self.index.upsert_shipment(
            tracking_number="1Z999AA10123456785",
            status="out_for_delivery",
            gmail_id="g2",
            subject="OFD",
        )
        summary = self.index.get_commerce_summary()
        self.assertEqual(summary["in_transit"], 1)
        self.assertEqual(summary["out_for_delivery"], 1)


if __name__ == "__main__":
    unittest.main()
