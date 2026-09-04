#!/usr/bin/env python3
"""
Extract structured order/shipment data from transactional emails.
Uses regex fallbacks plus optional LLM/DSPy extraction.
"""

import json
import os
import re
from typing import Any, Dict, Optional

try:
    import dspy
    from dspy_signatures import OrderExtraction
    from dspy_config import configure_dspy_lm
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None

TRANSACTIONAL_KEYWORDS = [
    "receipt", "receipt for", "order confirm", "order confirmed",
    "shipped", "shipping confirm", "delivery update", "transaction",
    "payment receiv", "purchase confirm", "your order", "tracking number",
]

EXTRACTION_PROMPT = """Extract order and shipment details from this email.
Respond with ONLY valid JSON, no other text.
Format:
{
  "merchant": "store or shipper name",
  "order_number": "",
  "tracking_number": "",
  "carrier": "",
  "status": "ordered|confirmed|shipped|in_transit|out_for_delivery|delivered|unknown",
  "amount": "",
  "currency": "",
  "estimated_delivery": "",
  "tracking_url": "",
  "item_summary": ""
}
Use empty strings for unknown fields. Infer status from email content."""

UPS_PATTERN = re.compile(r"\b(1Z[0-9A-Z]{16})\b", re.IGNORECASE)
USPS_PATTERN = re.compile(r"\b(9[0-9]{20,26})\b")
FEDEX_PATTERN = re.compile(r"\b([0-9]{12,22})\b")
TRACKING_LABEL_PATTERN = re.compile(
    r"tracking\s*(?:#|number|no\.?|:)\s*([A-Z0-9\-]+)",
    re.IGNORECASE,
)
TRACKING_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+(?:fedex\.com/track|ups\.com/track|tools\.usps\.com|"
    r"amazon\.com/progress-tracker|dhl\.com)[^\s<>\"']*",
    re.IGNORECASE,
)
ORDER_NUMBER_PATTERN = re.compile(
    r"(?:order\s*(?:#|number|no\.?|:)\s*)([A-Z0-9\-]+)",
    re.IGNORECASE,
)

_dspy_extractor = None


def should_extract(
    carrier_match: bool,
    category: str,
    subject: str,
    snippet: str,
) -> bool:
    """Return True if this email should run order extraction."""
    if carrier_match:
        return True
    if category in ("receipt", "order", "shipping"):
        return True
    content = f"{subject} {snippet}".lower()
    return any(kw in content for kw in TRANSACTIONAL_KEYWORDS)


def _empty_extraction() -> Dict[str, str]:
    return {
        "merchant": "",
        "order_number": "",
        "tracking_number": "",
        "carrier": "",
        "status": "unknown",
        "amount": "",
        "currency": "",
        "estimated_delivery": "",
        "tracking_url": "",
        "item_summary": "",
    }


def extract_with_regex(subject: str, body: str, carrier_hint: str = "") -> Dict[str, str]:
    """Regex-based extraction for tracking numbers, URLs, order numbers."""
    result = _empty_extraction()
    content = f"{subject}\n{body}"

    ups = UPS_PATTERN.search(content)
    if ups:
        result["tracking_number"] = ups.group(1).upper()
        result["carrier"] = result["carrier"] or "UPS"

    if not result["tracking_number"]:
        usps = USPS_PATTERN.search(content)
        if usps:
            result["tracking_number"] = usps.group(1)
            result["carrier"] = result["carrier"] or "USPS"

    if not result["tracking_number"]:
        label_match = TRACKING_LABEL_PATTERN.search(content)
        if label_match:
            result["tracking_number"] = label_match.group(1).upper()

    if not result["tracking_number"] and "fedex" in content.lower():
        fedex = FEDEX_PATTERN.search(content)
        if fedex:
            result["tracking_number"] = fedex.group(1)
            result["carrier"] = result["carrier"] or "FedEx"

    order_match = ORDER_NUMBER_PATTERN.search(content)
    if order_match:
        result["order_number"] = order_match.group(1)

    url_match = TRACKING_URL_PATTERN.search(content)
    if url_match:
        result["tracking_url"] = url_match.group(0).rstrip(".,)")

    if carrier_hint:
        result["carrier"] = carrier_hint

    content_lower = content.lower()
    if "delivered" in content_lower:
        result["status"] = "delivered"
    elif "out for delivery" in content_lower:
        result["status"] = "out_for_delivery"
    elif "in transit" in content_lower or "on the way" in content_lower:
        result["status"] = "in_transit"
    elif "shipped" in content_lower or "has shipped" in content_lower:
        result["status"] = "shipped"
    elif "order confirm" in content_lower or "thank you for your order" in content_lower:
        result["status"] = "confirmed"
    elif "receipt" in content_lower or "invoice" in content_lower:
        result["status"] = "confirmed"

    return result


def _merge_extraction(base: Dict[str, str], llm: Dict[str, str]) -> Dict[str, str]:
    merged = dict(base)
    for key, value in llm.items():
        if value and str(value).strip() and str(value).strip().lower() not in ("unknown", "n/a"):
            if not merged.get(key) or key in ("status", "merchant", "item_summary"):
                merged[key] = str(value).strip()
    return merged


def _get_dspy_extractor():
    global _dspy_extractor
    if _dspy_extractor is None:
        configure_dspy_lm()
        _dspy_extractor = dspy.ChainOfThought(OrderExtraction)
    return _dspy_extractor


def extract_with_llm(
    sender: str,
    subject: str,
    body: str,
    use_dspy: bool = False,
) -> Dict[str, str]:
    """LLM extraction via DSPy or OpenAI-compatible API."""
    body_snippet = re.sub(r"\s+", " ", body).strip()[:6000]

    if use_dspy and DSPY_AVAILABLE:
        try:
            extractor = _get_dspy_extractor()
            result = extractor(sender=sender, subject=subject, body=body_snippet)
            return {
                "merchant": result.merchant or "",
                "order_number": result.order_number or "",
                "tracking_number": result.tracking_number or "",
                "carrier": result.carrier or "",
                "status": result.status or "unknown",
                "amount": result.amount or "",
                "currency": result.currency or "",
                "estimated_delivery": result.estimated_delivery or "",
                "tracking_url": result.tracking_url or "",
                "item_summary": result.item_summary or "",
            }
        except Exception:
            pass

    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "ollama":
        import requests
        url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
        model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"From: {sender}\nSubject: {subject}\nBody: {body_snippet}"},
            ],
            "temperature": 0,
        }
    else:
        import requests
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return _empty_extraction()
        url = os.getenv("OPENAI_URL", "https://api.openai.com/v1/chat/completions")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"From: {sender}\nSubject: {subject}\nBody: {body_snippet}"},
            ],
        }

    try:
        timeout = float(os.getenv("OPENAI_TIMEOUT", "45"))
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        out = _empty_extraction()
        for key in out:
            if key in parsed and parsed[key]:
                out[key] = str(parsed[key]).strip()
        return out
    except Exception:
        return _empty_extraction()


def extract_order_data(
    sender: str,
    subject: str,
    body: str,
    *,
    carrier_hint: str = "",
    category: str = "none",
    use_dspy: bool = False,
    use_llm: bool = True,
) -> Dict[str, str]:
    """
    Full extraction pipeline: regex first, then optional LLM merge.
    """
    regex_data = extract_with_regex(subject, body, carrier_hint=carrier_hint)

    if not use_llm:
        if not regex_data["merchant"] and sender:
            domain_match = re.search(r"@([\w.-]+)", sender)
            if domain_match:
                regex_data["merchant"] = domain_match.group(1).split(".")[0].title()
        if category == "receipt" and regex_data["status"] == "unknown":
            regex_data["status"] = "confirmed"
        elif category == "order" and regex_data["status"] == "unknown":
            regex_data["status"] = "confirmed"
        elif category == "shipping" and regex_data["status"] == "unknown":
            regex_data["status"] = "shipped"
        return regex_data

    llm_data = extract_with_llm(sender, subject, body, use_dspy=use_dspy)
    merged = _merge_extraction(regex_data, llm_data)

    if not merged["merchant"] and sender:
        domain_match = re.search(r"@([\w.-]+)", sender)
        if domain_match:
            merged["merchant"] = domain_match.group(1).split(".")[0].title()

    if category == "receipt" and merged["status"] == "unknown":
        merged["status"] = "confirmed"
    elif category == "order" and merged["status"] == "unknown":
        merged["status"] = "confirmed"
    elif category == "shipping" and merged["status"] == "unknown" and merged["tracking_number"]:
        merged["status"] = "shipped"

    return merged
