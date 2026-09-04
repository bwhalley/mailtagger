#!/usr/bin/env python3
"""Unit tests for order extraction regex fallbacks."""

import unittest

from order_extraction import extract_with_regex, should_extract


class TestOrderExtraction(unittest.TestCase):
    def test_ups_tracking_regex(self):
        result = extract_with_regex(
            "Your package shipped",
            "Tracking number: 1Z999AA10123456784",
        )
        self.assertEqual(result["tracking_number"], "1Z999AA10123456784")
        self.assertEqual(result["carrier"], "UPS")

    def test_usps_tracking_regex(self):
        result = extract_with_regex(
            "USPS delivery",
            "Tracking: 9400111899223344556677",
        )
        self.assertEqual(result["tracking_number"], "9400111899223344556677")

    def test_status_from_content(self):
        result = extract_with_regex(
            "Out for delivery today",
            "Your package will arrive soon.",
        )
        self.assertEqual(result["status"], "out_for_delivery")

    def test_should_extract_transactional(self):
        self.assertTrue(
            should_extract(False, "none", "Order confirmed", "Thank you for your order")
        )
        self.assertTrue(should_extract(True, "shipping", "", ""))
        self.assertFalse(should_extract(False, "none", "Weekly newsletter", "Shop our sale"))


if __name__ == "__main__":
    unittest.main()
