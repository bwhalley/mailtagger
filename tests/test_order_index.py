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

    def test_create_shipment(self):
        sid = self.index.upsert_shipment(
            email_id=1,
            gmail_id="g1",
            thread_id="t1",
            merchant="Target",
            order_number="ORD-123",
            tracking_number="",
            carrier="",
            status="confirmed",
            subject="Order confirmed",
        )
        self.assertIsNotNone(sid)
        shipment = self.index.get_by_id(sid)
        self.assertEqual(shipment["merchant"], "Target")
        self.assertEqual(shipment["status"], "confirmed")

    def test_merge_by_tracking_number(self):
        sid1 = self.index.upsert_shipment(
            email_id=1,
            gmail_id="g1",
            thread_id="t1",
            merchant="Amazon",
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="shipped",
            subject="Shipped",
        )
        sid2 = self.index.upsert_shipment(
            email_id=2,
            gmail_id="g2",
            thread_id="t1",
            merchant="Amazon",
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="out_for_delivery",
            subject="Out for delivery",
        )
        self.assertEqual(sid1, sid2)
        shipment = self.index.get_by_id(sid1)
        self.assertEqual(shipment["status"], "out_for_delivery")
        self.assertEqual(len(shipment["linked_emails"]), 2)

    def test_status_does_not_regress(self):
        sid = self.index.upsert_shipment(
            email_id=1,
            gmail_id="g1",
            thread_id="t1",
            merchant="Best Buy",
            tracking_number="9400111899223344556677",
            status="delivered",
            subject="Delivered",
        )
        self.index.upsert_shipment(
            email_id=2,
            gmail_id="g2",
            thread_id="t1",
            merchant="Best Buy",
            tracking_number="9400111899223344556677",
            status="shipped",
            subject="Shipped",
        )
        shipment = self.index.get_by_id(sid)
        self.assertEqual(shipment["status"], "delivered")

    def test_list_recent_orders(self):
        self.index.upsert_shipment(
            email_id=1,
            gmail_id="g1",
            thread_id="t1",
            merchant="Nike",
            order_number="N-100",
            status="confirmed",
            subject="Thanks for your order",
        )
        self.index.upsert_shipment(
            email_id=2,
            gmail_id="g2",
            thread_id="t2",
            merchant="FedEx",
            tracking_number="123456789012",
            status="in_transit",
            subject="In transit",
        )
        recent = self.index.list_recent_orders()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["merchant"], "Nike")

    def test_summary_counts(self):
        self.index.upsert_shipment(
            email_id=1,
            gmail_id="g1",
            thread_id="t1",
            merchant="A",
            tracking_number="1Z999AA10123456784",
            status="in_transit",
            subject="Transit",
        )
        self.index.upsert_shipment(
            email_id=2,
            gmail_id="g2",
            thread_id="t2",
            merchant="B",
            tracking_number="1Z999AA10123456785",
            status="out_for_delivery",
            subject="OFD",
        )
        summary = self.index.get_summary()
        self.assertEqual(summary["in_transit"], 1)
        self.assertEqual(summary["out_for_delivery"], 1)


if __name__ == "__main__":
    unittest.main()
