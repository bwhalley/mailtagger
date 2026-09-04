#!/usr/bin/env python3
"""Unit tests for carrier domain matching."""

import unittest

from carrier_rules import match_carrier, is_carrier_domain, extract_domain_key


class TestCarrierRules(unittest.TestCase):
    def test_fedex_match(self):
        result = match_carrier("tracking@fedex.com", "Your package is on the way", "")
        self.assertIsNotNone(result)
        self.assertEqual(result.carrier_name, "FedEx")

    def test_ups_match(self):
        result = match_carrier("noreply@ups.com", "Shipment notification", "")
        self.assertIsNotNone(result)
        self.assertEqual(result.carrier_name, "UPS")

    def test_usps_match(self):
        result = match_carrier("notify@usps.gov", "Delivery update", "")
        self.assertIsNotNone(result)
        self.assertEqual(result.carrier_name, "USPS")

    def test_amazon_requires_shipping_cues(self):
        marketing = match_carrier(
            "deals@amazon.com",
            "Today's deals for you",
            "Shop now and save",
        )
        self.assertIsNone(marketing)

        shipping = match_carrier(
            "shipment-tracking@amazon.com",
            "Your package has shipped",
            "Track your package",
        )
        self.assertIsNotNone(shipping)
        self.assertEqual(shipping.carrier_name, "Amazon")

    def test_non_carrier_returns_none(self):
        result = match_carrier("news@target.com", "Weekly ad", "")
        self.assertIsNone(result)

    def test_is_carrier_domain(self):
        self.assertTrue(is_carrier_domain("fedex.com"))
        self.assertTrue(is_carrier_domain("notify.usps.gov"))
        self.assertFalse(is_carrier_domain("target.com"))

    def test_subdomain_carrier(self):
        result = match_carrier("alert@email.fedex.com", "Delivery update", "")
        self.assertIsNotNone(result)
        self.assertEqual(result.carrier_name, "FedEx")

    def test_domain_key_extraction(self):
        self.assertEqual(extract_domain_key("notify.usps.gov"), "usps.gov")
        self.assertEqual(extract_domain_key("email.fedex.com"), "fedex.com")


if __name__ == "__main__":
    unittest.main()
