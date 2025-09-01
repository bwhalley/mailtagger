#!/usr/bin/env python3
import os, sys, time, json, base64, re, argparse
from typing import Dict, Any, Optional, Tuple

# Gmail API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# HTTP
import requests

# Optional .env support
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# ------- LLM selection -------
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "openai").lower()  # 'openai' or 'ollama'

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL     = os.getenv("OPENAI_URL", "https://api.openai.com/v1/chat/completions")

# Ollama
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

# Labels
LABEL_ECOMMERCE = os.getenv("LABEL_ECOMMERCE", "AI_Ecommerce")
LABEL_POLITICAL = os.getenv("LABEL_POLITICAL", "AI_Political")
LABEL_TRIAGED   = os.getenv("LABEL_TRIAGED",   "AI_Triaged")

DEFAULT_QUERY   = os.getenv("GMAIL_QUERY", "in:inbox newer_than:14d -label:%s" % LABEL_TRIAGED)
MAX_RESULTS     = int(os.getenv("MAX_RESULTS", "40"))
SLEEP_SECONDS   = float(os.getenv("SLEEP_SECONDS", "0.5"))
TIMEOUT_SEC     = float(os.getenv("OPENAI_TIMEOUT", "45"))

def gmail_service() -> Any:
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found. See README to create it.", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def list_threads(svc, query: str, max_results: int):
    resp = svc.users().threads().list(userId='me', q=query, maxResults=max_results).execute()
    return resp.get('threads', [])

def get_thread(svc, thread_id: str):
    return svc.users().threads().get(userId='me', id=thread_id, format='full').execute()

def get_subject_and_from(headers) -> Tuple[str, str]:
    subject, from_ = "", ""
    for h in headers:
        name = h.get('name', '').lower()
        if name == 'subject':
            subject = h.get('value', '')
        elif name == 'from':
            from_ = h.get('value', '')
    return subject, from_

def strip_html(html: str) -> str:
    html = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', html)
    html = re.sub(r'(?s)<.*?>', ' ', html)
    html = re.sub(r'\s+', ' ', html).strip()
    return html

def decode_part(data: Optional[str]) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_text_from_payload(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""
    mime = payload.get('mimeType', '')
    body_data = payload.get('body', {}).get('data')

    if 'parts' in payload:
        texts = [extract_text_from_payload(p) for p in payload['parts']]
        texts = [t for t in texts if t]
        return "\n".join(texts)

    if body_data:
        text = decode_part(body_data)
        if 'text/html' in mime.lower():
            text = strip_html(text)
        return text

    return ""

def safe_snippet(text: str, max_chars: int = 6000) -> str:
    t = re.sub(r'\s+', ' ', text).strip()
    return t[:max_chars]

PROMPT_RULES = (
    "You are a strict email classifier. Classify an email into exactly ONE of two buckets:\n"
    "1) 'ecommerce' – marketing or campaign emails from stores/brands about sales, product launches, coupons, promotions, newsletters from retailers.\n"
    "   Include brand newsletters, 'shop now', seasonal sales, product announcements, abandoned cart promos, discount codes.\n"
    "   Exclude order receipts or shipping notifications if purely transactional.\n"
    "2) 'political' – messages from campaigns, candidates, PACs, NGOs/activist orgs soliciting donations, petitions, or political actions. "
    "   Look for cues like ActBlue/WinRed links, 'chip in', 'end-of-quarter', 'paid for by', election/candidate names.\n"
    "If neither fits, choose 'ecommerce' ONLY if it's clearly a store/brand campaign; otherwise return 'none'.\n"
    "IMPORTANT: Respond with ONLY valid JSON. No additional text, no explanations outside the JSON.\n"
    "Format: {\"category\": \"ecommerce|political|none\", \"reason\": \"short explanation\", \"confidence\": 0.9}\n"
    "Be conservative and only pick 'political' if clearly political."
)

def call_openai_classifier(subject: str, body: str, sender: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or environment.")

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": OPENAI_MODEL,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "messages": [
            {"role":"system","content": PROMPT_RULES},
            {"role":"user","content": f"From: {sender}\nSubject: {subject}\nBody: {body}"}
        ]
    }
    r = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=TIMEOUT_SEC)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except Exception:
        data = {"category": "none", "reason": "parse_error", "confidence": 0.0}
    return data

def call_ollama_classifier(subject: str, body: str, sender: str) -> Dict[str, Any]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role":"system","content": PROMPT_RULES},
            {"role":"user","content": f"From: {sender}\nSubject: {subject}\nBody: {body}"}
        ],
        "temperature": 0
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SEC)
    r.raise_for_status()
    
    print(f"DEBUG: Ollama HTTP status: {r.status_code}")
    print(f"DEBUG: Ollama response headers: {dict(r.headers)}")
    
    # Handle streaming NDJSON response from Ollama
    if r.headers.get('Content-Type') == 'application/x-ndjson':
        # Parse streaming response line by line
        content = ""
        final_content = ""
        for line in r.text.strip().split('\n'):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                if chunk.get('done', False):
                    # Final chunk, extract the complete content
                    if 'message' in chunk and 'content' in chunk['message']:
                        final_content = chunk['message']['content']
                        break
                elif 'message' in chunk and 'content' in chunk['message']:
                    # Accumulate content from streaming chunks
                    chunk_content = chunk['message']['content']
                    if chunk_content:  # Only add non-empty content
                        content += chunk_content
            except json.JSONDecodeError:
                continue
        
        # Use final_content if available, otherwise use accumulated content
        if final_content:
            content = final_content
            print(f"DEBUG: Using final_content: {repr(final_content)}")
        elif not content:
            # If no content was found, try to extract from the last chunk
            lines = r.text.strip().split('\n')
            if lines:
                try:
                    last_chunk = json.loads(lines[-1])
                    if 'message' in last_chunk and 'content' in last_chunk['message']:
                        content = last_chunk['message']['content']
                        print(f"DEBUG: Using last chunk content: {repr(content)}")
                except json.JSONDecodeError:
                    pass
        
        print(f"DEBUG: Final extracted content: {repr(content)}")
        print(f"DEBUG: Content length: {len(content)}")
        
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON parse error: {e}")
                # Try to extract JSON from content that might have extra text
                if "Extra data" in str(e):
                    # Look for JSON content between curly braces
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            json_content = json_match.group(0)
                            print(f"DEBUG: Extracted JSON: {json_content}")
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            pass
                # If JSON parsing fails, try fallback extraction
                return extract_category_fallback(content)
    
    # Fallback to regular JSON parsing for non-streaming responses
    try:
        j = r.json()
    except json.JSONDecodeError as e:
        print(f"DEBUG: Ollama API returned malformed JSON: {e}")
        print(f"DEBUG: Raw response text: {repr(r.text)}")
        return {"category": "none", "reason": "api_json_error", "confidence": 0.0}
    
    # Chat Completions API returns the same structure as OpenAI
    if "choices" in j and len(j["choices"]) > 0:
        content = j["choices"][0].get("message", {}).get("content", "")
        if content:
            print(f"DEBUG: Raw Ollama response: {repr(content)}")
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON parse error: {e}")
                # Try to extract JSON from content that might have extra text
                if "Extra data" in str(e):
                    # Look for JSON content between curly braces
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            json_content = json_match.group(0)
                            print(f"DEBUG: Extracted JSON: {json_content}")
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            pass
                # If JSON parsing fails, try fallback extraction
                return extract_category_fallback(content)
    
    return {"category": "none", "reason": "empty_response", "confidence": 0.0}

def extract_category_fallback(content: str) -> Dict[str, Any]:
    """Fallback method to extract category when JSON parsing fails"""
    content_lower = content.lower()
    
    # Look for category indicators
    if any(word in content_lower for word in ['"category":', "'category':", "category:"]):
        if '"ecommerce"' in content_lower or "'ecommerce'" in content_lower:
            return {"category": "ecommerce", "reason": "extracted_from_text", "confidence": 0.7}
        elif '"political"' in content_lower or "'political'" in content_lower:
            return {"category": "political", "reason": "extracted_from_text", "confidence": 0.7}
        elif '"none"' in content_lower or "'none'" in content_lower:
            return {"category": "none", "reason": "extracted_from_text", "confidence": 0.7}
    
    # Look for category words in the text
    if any(word in content_lower for word in ['ecommerce', 'marketing', 'store', 'brand', 'sale', 'coupon']):
        return {"category": "ecommerce", "reason": "keyword_match", "confidence": 0.6}
    elif any(word in content_lower for word in ['political', 'campaign', 'fundraising', 'donation', 'actblue', 'winred']):
        return {"category": "political", "reason": "keyword_match", "confidence": 0.6}
    
    return {"category": "none", "reason": "fallback_no_match", "confidence": 0.0}

def call_llm_classifier(subject: str, body: str, sender: str) -> Dict[str, Any]:
    provider = LLM_PROVIDER
    if provider == "ollama":
        return call_ollama_classifier(subject, body, sender)
    return call_openai_classifier(subject, body, sender)

def ensure_labels_map(svc, want_names):
    existing = svc.users().labels().list(userId='me').execute().get('labels', [])
    id_by_name = {lab['name']: lab['id'] for lab in existing}
    for name in want_names:
        if name not in id_by_name:
            body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
            lab = svc.users().labels().create(userId='me', body=body).execute()
            id_by_name[name] = lab['id']
    return id_by_name

def label_thread(svc, thread_id: str, add_label_ids):
    body = {"addLabelIds": add_label_ids, "removeLabelIds": []}
    return svc.users().threads().modify(userId='me', id=thread_id, body=body).execute()

def run_once(dry_run=False, max_results=MAX_RESULTS, query=DEFAULT_QUERY):
    svc = gmail_service()
    want_labels = [LABEL_ECOMMERCE, LABEL_POLITICAL, LABEL_TRIAGED]
    labels_map = ensure_labels_map(svc, want_labels)

    threads = list_threads(svc, query, max_results)
    if not threads:
        print("No threads to process for query:", query)
        return

    processed = 0
    for t in threads:
        tid = t['id']
        try:
            th = get_thread(svc, tid)
            msgs = th.get('messages', [])
            if not msgs:
                continue

            first = msgs[0]
            payload = first.get('payload', {})
            headers = payload.get('headers', [])
            subject, sender = get_subject_and_from(headers)
            text = extract_text_from_payload(payload) or ""
            snippet = safe_snippet(text, 4000)

            result = call_llm_classifier(subject, snippet, sender)
            category = (result.get("category") or "none").lower()
            confidence = float(result.get("confidence", 0))
            reason = result.get("reason", "")

            add_ids = [labels_map[LABEL_TRIAGED]]
            if category == "political":
                add_ids.append(labels_map[LABEL_POLITICAL])
            elif category == "ecommerce":
                add_ids.append(labels_map[LABEL_ECOMMERCE])

            print(f"[{category:10}] conf={confidence:.2f}  {subject[:90]}  (reason: {reason})")

            if not dry_run:
                label_thread(svc, tid, add_ids)
                time.sleep(SLEEP_SECONDS)

            processed += 1
        except HttpError as e:
            print("Gmail API error:", e, file=sys.stderr)
        except requests.RequestException as e:
            print("LLM request error:", e, file=sys.stderr)
        except Exception as e:
            print("Error:", e, file=sys.stderr)

    print(f"Done. Processed {processed} thread(s).")

def main():
    ap = argparse.ArgumentParser(description="Gmail LLM categorizer (Ecommerce vs Political)")
    ap.add_argument("--dry-run", action="store_true", help="Don't apply labels, just print decisions")
    ap.add_argument("--max", type=int, default=MAX_RESULTS, help="Max threads per run")
    ap.add_argument("--query", type=str, default=DEFAULT_QUERY, help="Gmail search query")
    args = ap.parse_args()

    run_once(dry_run=args.dry_run, max_results=args.max, query=args.query)

if __name__ == "__main__":
    main()
