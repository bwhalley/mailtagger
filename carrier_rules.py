#!/usr/bin/env python3
"""
Carrier domain matching for Tier 1b email classification.
Matches known shipping carrier senders without LLM calls.
"""

import re
from dataclasses import dataclass
from typing import Optional

CARRIER_DOMAINS = {
    "fedex.com": "FedEx",
    "ups.com": "UPS",
    "usps.gov": "USPS",
    "usps.com": "USPS",
    "dhl.com": "DHL",
    "ontrac.com": "OnTrac",
    "lasership.com": "LaserShip",
    "purolator.com": "Purolator",
}

AMAZON_DOMAIN = "amazon.com"

SHIPPING_CUES = (
    "shipped",
    "shipping",
    "delivery",
    "delivered",
    "tracking",
    "out for delivery",
    "package",
    "on its way",
    "arriving",
)


@dataclass
class CarrierMatch:
    """Result of carrier domain matching."""

    carrier_name: str
    domain_key: str
    is_amazon: bool = False


def extract_domain(sender: str) -> str:
    """Extract domain from an email From header or address."""
    if not sender:
        return ""
    match = re.search(r"@([\w.-]+)", sender)
    return match.group(1).lower() if match else ""


def extract_domain_key(sender_domain: str) -> str:
    """
    Extract registrable domain key (mail.fedex.com -> fedex.com).
    Mirrors email_index._extract_domain_key logic.
    """
    domain = (sender_domain or "").strip().lower()
    if not domain:
        return ""
    parts = [p for p in domain.split(".") if p]
    if len(parts) <= 2:
        return domain
    second_level_suffixes = {
        "co.uk", "org.uk", "ac.uk", "gov.uk",
        "com.au", "net.au", "org.au",
        "co.nz", "com.br", "com.mx",
        "co.jp", "co.kr", "com.sg",
    }
    tail2 = ".".join(parts[-2:])
    if tail2 in second_level_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _has_shipping_cues(subject: str, snippet: str) -> bool:
    content = f"{subject} {snippet}".lower()
    return any(cue in content for cue in SHIPPING_CUES)


def match_carrier(
    sender: str,
    subject: str = "",
    snippet: str = "",
) -> Optional[CarrierMatch]:
    """
    Match sender against known carrier domains.

    Amazon requires shipping cues in subject/snippet to avoid marketing false positives.
    Returns CarrierMatch if matched, else None.
    """
    sender_domain = extract_domain(sender)
    domain_key = extract_domain_key(sender_domain)
    if not domain_key:
        return None

    if domain_key == AMAZON_DOMAIN or domain_key.endswith(".amazon.com"):
        if not _has_shipping_cues(subject, snippet):
            return None
        return CarrierMatch(carrier_name="Amazon", domain_key=domain_key, is_amazon=True)

    for carrier_domain, carrier_name in CARRIER_DOMAINS.items():
        if domain_key == carrier_domain or domain_key.endswith(f".{carrier_domain}"):
            return CarrierMatch(carrier_name=carrier_name, domain_key=domain_key)

    return None


def is_carrier_domain(sender_domain: str) -> bool:
    """Check if a sender domain belongs to a known carrier (including Amazon)."""
    domain_key = extract_domain_key(sender_domain)
    if not domain_key:
        return False
    if domain_key == AMAZON_DOMAIN or domain_key.endswith(".amazon.com"):
        return True
    return any(
        domain_key == d or domain_key.endswith(f".{d}")
        for d in CARRIER_DOMAINS
    )
