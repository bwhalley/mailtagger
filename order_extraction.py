#!/usr/bin/env python3
"""
Extract structured order and shipment data from transactional emails.
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
  "order_number": "",
  "tracking_number": "",
  "carrier": "",
  "order_status": "ordered|confirmed|cancelled|unknown",
  "shipment_status": "shipped|in_transit|out_for_delivery|delivered|unknown",
  "estimated_delivery": "",
  "tracking_url": ""
}
Use empty strings for unknown fields."""

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


def normalize_tracking_number(raw: str) -> str:
    if not raw:
        return ""
    normalized = re.sub(r"[\s\-]", "", raw.strip()).upper()
    if len(normalized) < 8:
        return ""
    if len(set(normalized)) == 1:
        return ""
    return normalized


def normalize_order_number(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s+", "", raw.strip()).upper()


def should_extract(
    carrier_match: bool,
    category: str,
    subject: str,
    snippet: str,
) -> bool:
    if carrier_match:
        return True
    if category in ("receipt", "order", "shipping"):
        return True
    content = f"{subject} {snippet}".lower()
    return any(kw in content for kw in TRANSACTIONAL_KEYWORDS)


def _empty_commerce() -> Dict[str, str]:
    return {
        "order_number": "",
        "tracking_number": "",
        "carrier": "",
        "order_status": "unknown",
        "shipment_status": "unknown",
        "estimated_delivery": "",
        "tracking_url": "",
    }


def _map_legacy_status(status: str, category: str) -> Dict[str, str]:
    status = (status or "unknown").lower()
    order_status = "unknown"
    shipment_status = "unknown"
    if status in ("ordered", "confirmed", "cancelled"):
        order_status = status
    elif status in ("shipped", "in_transit", "out_for_delivery", "delivered"):
        shipment_status = status
    elif status == "unknown":
        if category in ("receipt", "order"):
            order_status = "confirmed"
        elif category == "shipping":
            shipment_status = "shipped"
    return {"order_status": order_status, "shipment_status": shipment_status}


def extract_with_regex(subject: str, body: str, carrier_hint: str = "") -> Dict[str, str]:
    result = _empty_commerce()
    content = f"{subject}\n{body}"

    ups = UPS_PATTERN.search(content)
    if ups:
        result["tracking_number"] = normalize_tracking_number(ups.group(1))
        result["carrier"] = result["carrier"] or "UPS"

    if not result["tracking_number"]:
        usps = USPS_PATTERN.search(content)
        if usps:
            result["tracking_number"] = normalize_tracking_number(usps.group(1))
            result["carrier"] = result["carrier"] or "USPS"

    if not result["tracking_number"]:
        label_match = TRACKING_LABEL_PATTERN.search(content)
        if label_match:
            result["tracking_number"] = normalize_tracking_number(label_match.group(1))

    if not result["tracking_number"] and "fedex" in content.lower():
        fedex = FEDEX_PATTERN.search(content)
        if fedex:
            result["tracking_number"] = normalize_tracking_number(fedex.group(1))
            result["carrier"] = result["carrier"] or "FedEx"

    order_match = ORDER_NUMBER_PATTERN.search(content)
    if order_match:
        result["order_number"] = normalize_order_number(order_match.group(1))

    url_match = TRACKING_URL_PATTERN.search(content)
    if url_match:
        result["tracking_url"] = url_match.group(0).rstrip(".,)")

    if carrier_hint:
        result["carrier"] = carrier_hint

    content_lower = content.lower()
    if "delivered" in content_lower:
        result["shipment_status"] = "delivered"
    elif "out for delivery" in content_lower:
        result["shipment_status"] = "out_for_delivery"
    elif "in transit" in content_lower or "on the way" in content_lower:
        result["shipment_status"] = "in_transit"
    elif "shipped" in content_lower or "has shipped" in content_lower:
        result["shipment_status"] = "shipped"
    elif "order confirm" in content_lower or "thank you for your order" in content_lower:
        result["order_status"] = "confirmed"
    elif "receipt" in content_lower or "invoice" in content_lower:
        result["order_status"] = "confirmed"

    return result


def _merge_extraction(base: Dict[str, str], llm: Dict[str, str]) -> Dict[str, str]:
    merged = dict(base)
    for key, value in llm.items():
        if value and str(value).strip() and str(value).strip().lower() not in ("unknown", "n/a"):
            merged[key] = str(value).strip()
    if merged.get("tracking_number"):
        merged["tracking_number"] = normalize_tracking_number(merged["tracking_number"])
    if merged.get("order_number"):
        merged["order_number"] = normalize_order_number(merged["order_number"])
    return merged


def _get_dspy_extractor():
    global _dspy_extractor
    if _dspy_extractor is None:
        configure_dspy_lm()
        _dspy_extractor = dspy.ChainOfThought(OrderExtraction)
    return _dspy_extractor


def extract_with_llm(sender: str, subject: str, body: str, use_dspy: bool = False) -> Dict[str, str]:
    body_snippet = re.sub(r"\s+", " ", body).strip()[:6000]

    if use_dspy and DSPY_AVAILABLE:
        try:
            extractor = _get_dspy_extractor()
            result = extractor(sender=sender, subject=subject, body=body_snippet)
            mapped = _map_legacy_status(result.status, "shipping")
            return {
                "order_number": normalize_order_number(result.order_number or ""),
                "tracking_number": normalize_tracking_number(result.tracking_number or ""),
                "carrier": result.carrier or "",
                "order_status": mapped["order_status"],
                "shipment_status": mapped["shipment_status"] if result.tracking_number else "unknown",
                "estimated_delivery": result.estimated_delivery or "",
                "tracking_url": result.tracking_url or "",
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
            return _empty_commerce()
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
        content = r.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        out = _empty_commerce()
        for key in out:
            if key in parsed and parsed[key]:
                out[key] = str(parsed[key]).strip()
        if out.get("tracking_number"):
            out["tracking_number"] = normalize_tracking_number(out["tracking_number"])
        if out.get("order_number"):
            out["order_number"] = normalize_order_number(out["order_number"])
        return out
    except Exception:
        return _empty_commerce()


def extract_commerce_data(
    sender: str,
    subject: str,
    body: str,
    *,
    carrier_hint: str = "",
    category: str = "none",
    use_dspy: bool = False,
    use_llm: bool = True,
) -> Dict[str, str]:
    regex_data = extract_with_regex(subject, body, carrier_hint=carrier_hint)

    if use_llm:
        llm_data = extract_with_llm(sender, subject, body, use_dspy=use_dspy)
        merged = _merge_extraction(regex_data, llm_data)
    else:
        merged = regex_data

    if category in ("receipt", "order") and merged["order_status"] == "unknown":
        merged["order_status"] = "confirmed"
    if category == "shipping" and merged["shipment_status"] == "unknown" and merged["tracking_number"]:
        merged["shipment_status"] = "shipped"

    return merged


# Backward compatibility
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
    data = extract_commerce_data(
        sender, subject, body,
        carrier_hint=carrier_hint,
        category=category,
        use_dspy=use_dspy,
        use_llm=use_llm,
    )
    status = data.get("shipment_status") if data.get("tracking_number") else data.get("order_status")
    return {
        "merchant": "",
        "order_number": data.get("order_number", ""),
        "tracking_number": data.get("tracking_number", ""),
        "carrier": data.get("carrier", ""),
        "status": status or "unknown",
        "amount": "",
        "currency": "",
        "estimated_delivery": data.get("estimated_delivery", ""),
        "tracking_url": data.get("tracking_url", ""),
        "item_summary": "",
        "order_status": data.get("order_status", "unknown"),
        "shipment_status": data.get("shipment_status", "unknown"),
    }
