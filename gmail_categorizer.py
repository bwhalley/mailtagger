#!/usr/bin/env python3
import os, sys, time, json, base64, re, argparse, signal, logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Gmail API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# HTTP
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except ImportError:
    from requests.packages.urllib3.util.retry import Retry

# Optional .env support
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# DSPy support (optional)
try:
    import dspy
    from dspy_signatures import EmailClassification
    from dspy_config import configure_dspy_lm
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# ------- Configuration -------
# LLM selection
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

# Processing settings
DEFAULT_QUERY   = os.getenv("GMAIL_QUERY", "in:inbox newer_than:14d -label:%s" % LABEL_TRIAGED)
MAX_RESULTS     = int(os.getenv("MAX_RESULTS", "40"))
SLEEP_SECONDS   = float(os.getenv("SLEEP_SECONDS", "0.5"))
TIMEOUT_SEC     = float(os.getenv("OPENAI_TIMEOUT", "45"))

# Daemon mode settings
DAEMON_INTERVAL = int(os.getenv("DAEMON_INTERVAL", "300"))  # 5 minutes default
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", ".")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Retry settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))

# DSPy settings
USE_DSPY = os.getenv("USE_DSPY", "false").lower() in ("true", "1", "yes")

# ------- Global State -------
shutdown_requested = False

# ------- Logging Setup -------
def setup_logging(level: str = "INFO"):
    """Configure structured logging for the application."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from Google API libraries
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger('gmail_categorizer')

logger = setup_logging(LOG_LEVEL)

# ------- Signal Handlers -------
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    sig_name = signal.Signals(signum).name
    logger.info(f"Received signal {sig_name}, initiating graceful shutdown...")
    shutdown_requested = True

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ------- Health Check Functions -------
def check_ollama_health() -> bool:
    """Check if Ollama service is reachable and responsive."""
    if LLM_PROVIDER != "ollama":
        return True
    
    try:
        # Extract base URL from OLLAMA_URL
        base_url = OLLAMA_URL.replace('/v1/chat/completions', '')
        health_url = f"{base_url}/api/tags"
        
        logger.debug(f"Checking Ollama health at {health_url}")
        response = requests.get(health_url, timeout=5)
        response.raise_for_status()
        
        # Check if the configured model is available
        data = response.json()
        models = [m.get('name', '') for m in data.get('models', [])]
        
        if models:
            logger.info(f"Ollama is healthy. Available models: {', '.join(models)}")
            if OLLAMA_MODEL not in models:
                logger.warning(f"Configured model '{OLLAMA_MODEL}' not found. Available: {models}")
                logger.warning(f"You may need to run: ollama pull {OLLAMA_MODEL}")
        else:
            logger.warning("Ollama is running but no models are loaded")
        
        return True
    except requests.RequestException as e:
        logger.error(f"Ollama health check failed: {e}")
        return False

def check_credentials() -> bool:
    """Check if Gmail credentials files exist."""
    token_path = Path(CREDENTIALS_PATH) / 'token.json'
    creds_path = Path(CREDENTIALS_PATH) / 'credentials.json'
    
    if not creds_path.exists():
        logger.error(f"credentials.json not found at {creds_path}")
        logger.error("Please create Gmail API credentials. See README for instructions.")
        return False
    
    if not token_path.exists():
        logger.warning(f"token.json not found at {token_path}")
        logger.warning("OAuth flow will be triggered on first run")
    
    logger.debug(f"Credentials path verified: {CREDENTIALS_PATH}")
    return True

def perform_startup_health_checks() -> bool:
    """Perform all startup health checks."""
    logger.info("Performing startup health checks...")
    
    all_checks_passed = True
    
    # Check credentials
    if not check_credentials():
        all_checks_passed = False
    
    # Check Ollama if using it
    if LLM_PROVIDER == "ollama":
        if not check_ollama_health():
            logger.error("Ollama health check failed")
            all_checks_passed = False
    elif LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY is not set")
            all_checks_passed = False
        else:
            logger.info("OpenAI API key is configured")
    
    if all_checks_passed:
        logger.info("✓ All startup health checks passed")
    else:
        logger.error("✗ Some health checks failed")
    
    return all_checks_passed

# ------- Retry Logic -------
def create_retry_session(retries: int = MAX_RETRIES, backoff: float = RETRY_BACKOFF) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# ------- Gmail API -------
def gmail_service(skip_auth_flow: bool = False) -> Any:
    """
    Initialize and return Gmail API service.
    
    Args:
        skip_auth_flow: If True, don't attempt OAuth flow. Just raise exception if no valid token.
                       Useful for daemon mode where web-based auth should be used.
    """
    creds = None
    token_path = Path(CREDENTIALS_PATH) / 'token.json'
    creds_path = Path(CREDENTIALS_PATH) / 'credentials.json'
    
    if token_path.exists():
        logger.debug(f"Loading token from {token_path}")
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token...")
            try:
                creds.refresh(Request())
                logger.info("Token refreshed successfully")
                # Save refreshed token
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise
        else:
            if not creds_path.exists():
                logger.error(f"credentials.json not found at {creds_path}")
                logger.error("See README to create Gmail API credentials")
                raise RuntimeError("credentials.json not found")
            
            # Check if we should skip the auth flow (daemon mode)
            if skip_auth_flow:
                logger.warning("=" * 80)
                logger.warning("Gmail not authorized! Please authorize via web interface:")
                logger.warning("1. Open your Mailtagger web interface")
                logger.warning("2. Go to 'Gmail Auth' tab")
                logger.warning("3. Click 'Authorize Gmail'")
                logger.warning("=" * 80)
                raise RuntimeError("Gmail not authorized. Please use web interface to authorize.")
            
            logger.info("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            
            # Check if we're in a headless environment (Docker, no display, etc.)
            is_headless = (
                not os.getenv('DISPLAY') or  # No X11 display
                os.path.exists('/.dockerenv') or  # Docker container
                os.getenv('DOCKER_CONTAINER') == 'true' or  # Explicit Docker flag
                not os.getenv('TERM')  # No terminal (unlikely but possible)
            )
            
            if is_headless:
                # Use console flow for headless environments
                logger.info("Detected headless environment, using console-based OAuth flow")
                logger.info("=" * 80)
                logger.info("Please visit the following URL to authorize the application:")
                logger.info("=" * 80)
                creds = flow.run_console()
                logger.info("=" * 80)
                logger.info("OAuth flow completed successfully")
            else:
                # Try to run local server (opens browser), fall back to console if it fails
                try:
                    creds = flow.run_local_server(port=0)
                    logger.info("OAuth flow completed successfully")
                except Exception as e:
                    # If browser can't be opened, use console flow
                    logger.warning(f"Could not open browser: {e}")
                    logger.info("Falling back to console-based OAuth flow...")
                    logger.info("=" * 80)
                    logger.info("Please visit the following URL to authorize the application:")
                    logger.info("=" * 80)
                    creds = flow.run_console()
                    logger.info("=" * 80)
                    logger.info("OAuth flow completed successfully")
            
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            logger.debug(f"Token saved to {token_path}")
    
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
    """
    Extract plain text content from email payload.
    Prioritizes text/plain over text/html to avoid processing HTML/CSS markup.
    
    This optimization significantly reduces LLM token usage by:
    - Preferring plain text versions when available (most marketing emails include both)
    - Only falling back to stripped HTML if no plain text exists
    - Skipping non-text MIME parts (images, attachments, etc.)
    
    Typical token savings: 50-80% reduction for HTML-heavy marketing emails.
    """
    if not payload:
        return ""
    
    mime = payload.get('mimeType', '').lower()
    body_data = payload.get('body', {}).get('data')
    
    # Handle multipart messages - prefer text/plain over text/html
    if 'parts' in payload:
        plain_texts = []
        html_texts = []
        
        # Recursively collect text from all parts, separating plain and html
        for part in payload['parts']:
            part_mime = part.get('mimeType', '').lower()
            
            # Skip non-text parts (images, attachments, etc.)
            if not part_mime.startswith('text/') and not part_mime.startswith('multipart/'):
                continue
            
            # Recursively process nested multipart structures
            if 'parts' in part:
                text = extract_text_from_payload(part)
                if text:
                    # Try to determine if this came from plain or html
                    if 'text/plain' in part_mime or 'multipart/alternative' in part_mime:
                        plain_texts.append(text)
                    else:
                        html_texts.append(text)
            elif 'text/plain' in part_mime:
                part_data = part.get('body', {}).get('data')
                if part_data:
                    plain_text = decode_part(part_data)
                    if plain_text:
                        plain_texts.append(plain_text)
            elif 'text/html' in part_mime:
                part_data = part.get('body', {}).get('data')
                if part_data:
                    html_text = decode_part(part_data)
                    if html_text:
                        html_texts.append(strip_html(html_text))
        
        # Prefer plain text over HTML
        if plain_texts:
            return "\n".join(plain_texts)
        elif html_texts:
            return "\n".join(html_texts)
        else:
            return ""
    
    # Handle single-part messages
    if body_data:
        text = decode_part(body_data)
        if 'text/html' in mime:
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

def log_performance_metrics(provider: str, elapsed_time: float, total_tokens: int = 0, 
                            prompt_tokens: int = 0, completion_tokens: int = 0, 
                            verbose: bool = False) -> Dict[str, Any]:
    """Log performance metrics in a consistent format. Returns metrics dict for aggregation."""
    if not verbose:
        return {}
    
    logger.info("=" * 60)
    logger.info(f"LLM Performance Metrics ({provider})")
    logger.info("=" * 60)
    logger.info(f"  Total latency:     {elapsed_time:.3f}s")
    
    if total_tokens > 0:
        tokens_per_second = total_tokens / elapsed_time if elapsed_time > 0 else 0
        logger.info(f"  Total tokens:       {total_tokens:,}")
        logger.info(f"  Throughput:         {tokens_per_second:.2f} tokens/sec")
        
        if prompt_tokens > 0 or completion_tokens > 0:
            logger.info(f"  Prompt tokens:      {prompt_tokens:,}")
            logger.info(f"  Completion tokens:  {completion_tokens:,}")
            if prompt_tokens > 0:
                prompt_time = elapsed_time * (prompt_tokens / total_tokens) if total_tokens > 0 else 0
                completion_time = elapsed_time * (completion_tokens / total_tokens) if total_tokens > 0 else 0
                logger.info(f"  Prompt time:        {prompt_time:.3f}s")
                logger.info(f"  Generation time:    {completion_time:.3f}s")
                if completion_tokens > 0:
                    gen_speed = completion_tokens / completion_time if completion_time > 0 else 0
                    logger.info(f"  Generation speed:   {gen_speed:.2f} tokens/sec")
    else:
        logger.info(f"  Token info:         Not available")
    
    logger.info("=" * 60)
    
    # Return metrics for aggregation
    return {
        'latency': elapsed_time,
        'total_tokens': total_tokens,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens
    }

def call_openai_classifier(subject: str, body: str, sender: str, verbose: bool = False) -> Dict[str, Any]:
    """Classify email using OpenAI API."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or environment.")

    logger.debug(f"Calling OpenAI classifier for subject: {subject[:50]}...")
    
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
    
    session = create_retry_session()
    start_time = time.time()
    
    try:
        r = session.post(OPENAI_URL, headers=headers, json=payload, timeout=TIMEOUT_SEC)
        r.raise_for_status()
        elapsed = time.time() - start_time
        
        response_json = r.json()
        content = response_json["choices"][0]["message"]["content"]
        
        # Extract token usage if available
        usage = response_json.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        # Log performance metrics and return for aggregation
        metrics = log_performance_metrics(
            provider="OpenAI",
            elapsed_time=elapsed,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            verbose=verbose
        )
        
        logger.debug(f"OpenAI response received in {elapsed:.2f}s")
        
        try:
            data = json.loads(content)
            if verbose:
                logger.debug(f"Parsed result: {data}")
                # Attach metrics to result for aggregation
                data['_metrics'] = metrics
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            logger.debug(f"Raw content: {content}")
            return {"category": "none", "reason": "parse_error", "confidence": 0.0}
    except requests.RequestException as e:
        logger.error(f"OpenAI API request failed: {e}")
        raise

def call_ollama_classifier(subject: str, body: str, sender: str, verbose: bool = False) -> Dict[str, Any]:
    """Classify email using Ollama local LLM."""
    logger.debug(f"Calling Ollama classifier for subject: {subject[:50]}...")
    start_time = time.time()
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role":"system","content": PROMPT_RULES},
            {"role":"user","content": f"From: {sender}\nSubject: {subject}\nBody: {body}"}
        ],
        "temperature": 0
    }
    
    session = create_retry_session()
    
    try:
        r = session.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SEC)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Ollama API request failed: {e}")
        raise
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    logger.debug(f"Ollama response received in {elapsed_time:.2f}s")
    if verbose:
        logger.debug(f"Ollama HTTP status: {r.status_code}")
        logger.debug(f"Ollama response headers: {dict(r.headers)}")
    
    # Handle streaming NDJSON response from Ollama
    if r.headers.get('Content-Type') == 'application/x-ndjson':
        # Parse streaming response line by line
        content = ""
        final_content = ""
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        first_token_time = None
        
        for line in r.text.strip().split('\n'):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
                if chunk.get('done', False):
                    # Final chunk, extract the complete content and token count
                    if 'message' in chunk and 'content' in chunk['message']:
                        final_content = chunk['message']['content']
                    # Extract token count if available
                    if 'usage' in chunk:
                        total_tokens = chunk['usage'].get('total_tokens', 0)
                        prompt_tokens = chunk['usage'].get('prompt_tokens', 0)
                        completion_tokens = chunk['usage'].get('completion_tokens', 0)
                    break
                elif 'message' in chunk and 'content' in chunk['message']:
                    # Track time to first token
                    if first_token_time is None:
                        first_token_time = time.time()
                    # Accumulate content from streaming chunks
                    chunk_content = chunk['message']['content']
                    if chunk_content:  # Only add non-empty content
                        content += chunk_content
            except json.JSONDecodeError:
                continue
        
        # Use final_content if available, otherwise use accumulated content
        if final_content:
            content = final_content
            if verbose:
                logger.debug(f"Using final_content: {repr(final_content)}")
        elif not content:
            # If no content was found, try to extract from the last chunk
            lines = r.text.strip().split('\n')
            if lines:
                try:
                    last_chunk = json.loads(lines[-1])
                    if 'message' in last_chunk and 'content' in last_chunk['message']:
                        content = last_chunk['message']['content']
                        if verbose:
                            logger.debug(f"Using last chunk content: {repr(content)}")
                except json.JSONDecodeError:
                    pass
        
        # Log performance metrics
        metrics = log_performance_metrics(
            provider="Ollama (streaming)",
            elapsed_time=elapsed_time,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            verbose=verbose
        )
        
        if verbose and first_token_time:
            time_to_first_token = first_token_time - start_time
            logger.info(f"  Time to first token: {time_to_first_token:.3f}s")
        
        if verbose:
            logger.debug(f"Final extracted content: {repr(content)}")
            logger.debug(f"Content length: {len(content)}")
        
        if content:
            try:
                result = json.loads(content)
                if verbose:
                    result['_metrics'] = metrics
                return result
            except json.JSONDecodeError as e:
                if verbose:
                    logger.debug(f"JSON parse error: {e}")
                # Try to extract JSON from content that might have extra text
                if "Extra data" in str(e):
                    # Look for JSON content between curly braces
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            json_content = json_match.group(0)
                            if verbose:
                                logger.debug(f"Extracted JSON: {json_content}")
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            pass
                # If JSON parsing fails, try fallback extraction
                logger.warning(f"Failed to parse JSON from Ollama, using fallback extraction")
                return extract_category_fallback(content)
    
    # Fallback to regular JSON parsing for non-streaming responses
    try:
        j = r.json()
    except json.JSONDecodeError as e:
        logger.error(f"Ollama API returned malformed JSON: {e}")
        if verbose:
            logger.debug(f"Raw response text: {repr(r.text)}")
        return {"category": "none", "reason": "api_json_error", "confidence": 0.0}
    
    # Chat Completions API returns the same structure as OpenAI
    if "choices" in j and len(j["choices"]) > 0:
        content = j["choices"][0].get("message", {}).get("content", "")
        
        # Extract token usage if available
        usage = j.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        # Log performance metrics for non-streaming response
        metrics = log_performance_metrics(
            provider="Ollama (non-streaming)",
            elapsed_time=elapsed_time,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            verbose=verbose
        )
        
        if content:
            if verbose:
                logger.debug(f"Raw Ollama response: {repr(content)}")
            try:
                result = json.loads(content)
                if verbose:
                    result['_metrics'] = metrics
                return result
            except json.JSONDecodeError as e:
                if verbose:
                    logger.debug(f"JSON parse error: {e}")
                # Try to extract JSON from content that might have extra text
                if "Extra data" in str(e):
                    # Look for JSON content between curly braces
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            json_content = json_match.group(0)
                            if verbose:
                                logger.debug(f"Extracted JSON: {json_content}")
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            pass
                # If JSON parsing fails, try fallback extraction
                logger.warning(f"Failed to parse JSON from Ollama, using fallback extraction")
                return extract_category_fallback(content)
    
    logger.warning("Ollama returned empty response")
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

# ------- DSPy Classifier -------
# Global DSPy classifier instance (lazy-initialized)
_dspy_lm = None
_dspy_classifier = None

def get_dspy_classifier():
    """Lazy-initialize DSPy classifier.
    
    Returns:
        Initialized DSPy ChainOfThought classifier
        
    Raises:
        RuntimeError: If DSPy is not available or configuration fails
    """
    global _dspy_lm, _dspy_classifier
    
    if not DSPY_AVAILABLE:
        raise RuntimeError(
            "DSPy is not available. Install it with: pip install dspy-ai>=2.5.0"
        )
    
    if _dspy_classifier is None:
        logger.info("Initializing DSPy classifier...")
        try:
            _dspy_lm = configure_dspy_lm()
            # Use ChainOfThought for better reasoning
            _dspy_classifier = dspy.ChainOfThought(EmailClassification)
            logger.info("DSPy classifier initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DSPy classifier: {e}")
            raise RuntimeError(f"DSPy initialization failed: {e}")
    
    return _dspy_classifier

def call_llm_classifier_dspy(subject: str, body: str, sender: str, verbose: bool = False) -> Dict[str, Any]:
    """Classify email using DSPy.
    
    This uses DSPy's ChainOfThought module which automatically handles:
    - Structured input/output via signatures
    - Chain-of-thought reasoning for better accuracy
    - Type-safe outputs with validation
    
    Args:
        subject: Email subject line
        body: Email body text
        sender: Email sender address
        verbose: If True, log detailed information
        
    Returns:
        Dict with keys: category, reason, confidence, _reasoning (optional), _elapsed
    """
    classifier = get_dspy_classifier()
    
    start_time = time.time()
    
    try:
        # Truncate body to avoid token limits
        body_snippet = safe_snippet(body, max_chars=6000)
        
        if verbose:
            logger.debug(f"DSPy classifying email from {sender}")
            logger.debug(f"  Subject: {subject[:100]}...")
            logger.debug(f"  Body length: {len(body_snippet)} chars")
        
        # Call DSPy classifier
        result = classifier(
            sender=sender,
            subject=subject,
            body=body_snippet
        )
        
        elapsed = time.time() - start_time
        
        # Extract results
        response = {
            "category": result.category,
            "reason": result.reason,
            "confidence": float(result.confidence),
            "_elapsed": elapsed
        }
        
        # Include chain-of-thought reasoning if available
        if hasattr(result, 'reasoning') and result.reasoning:
            response["_reasoning"] = result.reasoning
            if verbose:
                logger.debug(f"  Reasoning: {result.reasoning[:200]}...")
        
        if verbose:
            logger.info(f"DSPy classification: {result.category} "
                       f"(confidence: {result.confidence:.2f}, "
                       f"elapsed: {elapsed:.2f}s)")
        
        return response
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"DSPy classifier error: {e}")
        if verbose:
            logger.exception("Full DSPy error traceback:")
        
        # Return error result
        return {
            "category": "none",
            "reason": f"dspy_error: {str(e)[:100]}",
            "confidence": 0.0,
            "_elapsed": elapsed,
            "_error": str(e)
        }

def call_llm_classifier(subject: str, body: str, sender: str, verbose: bool = False) -> Dict[str, Any]:
    """Main entry point for LLM classification.
    
    Routes to DSPy or legacy implementation based on USE_DSPY environment variable.
    
    Args:
        subject: Email subject line
        body: Email body text
        sender: Email sender address
        verbose: If True, log detailed information
        
    Returns:
        Dict with keys: category, reason, confidence
    """
    # Route to DSPy if enabled
    if USE_DSPY:
        if not DSPY_AVAILABLE:
            logger.warning("USE_DSPY=true but DSPy not available, falling back to legacy")
        else:
            return call_llm_classifier_dspy(subject, body, sender, verbose)
    
    # Legacy implementation
    provider = LLM_PROVIDER
    if provider == "ollama":
        return call_ollama_classifier(subject, body, sender, verbose)
    return call_openai_classifier(subject, body, sender, verbose)

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

def run_once(dry_run=False, max_results=MAX_RESULTS, query=DEFAULT_QUERY, verbose=False, daemon_mode=False) -> int:
    """
    Run one iteration of email processing. Returns number of processed emails.
    
    Args:
        daemon_mode: If True, skip interactive OAuth and just report auth needed.
    """
    global shutdown_requested
    
    logger.info(f"Starting email processing run (dry_run={dry_run}, max_results={max_results})")
    logger.debug(f"Query: {query}")
    
    # Performance tracking
    run_start_time = time.time()
    performance_stats = {
        'total_calls': 0,
        'total_latency': 0.0,
        'total_tokens': 0,
        'total_prompt_tokens': 0,
        'total_completion_tokens': 0,
        'latencies': []
    }
    
    try:
        svc = gmail_service(skip_auth_flow=daemon_mode)
    except Exception as e:
        logger.error(f"Failed to initialize Gmail service: {e}")
        if daemon_mode and "not authorized" in str(e).lower():
            logger.info("Waiting for Gmail authorization via web interface...")
        return 0
    
    want_labels = [LABEL_ECOMMERCE, LABEL_POLITICAL, LABEL_TRIAGED]
    try:
        labels_map = ensure_labels_map(svc, want_labels)
        logger.debug(f"Labels ensured: {list(labels_map.keys())}")
    except Exception as e:
        logger.error(f"Failed to ensure labels: {e}")
        return 0
    
    try:
        threads = list_threads(svc, query, max_results)
    except HttpError as e:
        logger.error(f"Failed to list threads: {e}")
        return 0
    
    if not threads:
        logger.info("No threads to process for query")
        return 0
    
    logger.info(f"Found {len(threads)} thread(s) to process")

    processed = 0
    errors = 0
    
    for idx, t in enumerate(threads, 1):
        if shutdown_requested:
            logger.info("Shutdown requested, stopping processing")
            break
        
        tid = t['id']
        logger.debug(f"Processing thread {idx}/{len(threads)}: {tid}")
        
        try:
            th = get_thread(svc, tid)
            msgs = th.get('messages', [])
            if not msgs:
                logger.debug(f"Thread {tid} has no messages, skipping")
                continue

            first = msgs[0]
            payload = first.get('payload', {})
            headers = payload.get('headers', [])
            subject, sender = get_subject_and_from(headers)
            text = extract_text_from_payload(payload) or ""
            snippet = safe_snippet(text, 4000)
            
            if verbose:
                logger.debug(f"Extracted text length: {len(text)} chars, snippet: {len(snippet)} chars")

            logger.debug(f"Classifying: '{subject[:60]}...' from {sender}")
            result = call_llm_classifier(subject, snippet, sender, verbose)
            
            # Collect performance metrics if available (stored in result metadata)
            if verbose and isinstance(result, dict) and '_metrics' in result:
                metrics = result.pop('_metrics')  # Remove from result before processing
                performance_stats['total_calls'] += 1
                performance_stats['total_latency'] += metrics.get('latency', 0)
                performance_stats['total_tokens'] += metrics.get('total_tokens', 0)
                performance_stats['total_prompt_tokens'] += metrics.get('prompt_tokens', 0)
                performance_stats['total_completion_tokens'] += metrics.get('completion_tokens', 0)
                performance_stats['latencies'].append(metrics.get('latency', 0))
            category = (result.get("category") or "none").lower()
            confidence = float(result.get("confidence", 0))
            reason = result.get("reason", "")

            add_ids = [labels_map[LABEL_TRIAGED]]
            if category == "political":
                add_ids.append(labels_map[LABEL_POLITICAL])
            elif category == "ecommerce":
                add_ids.append(labels_map[LABEL_ECOMMERCE])

            log_msg = f"[{category:10}] conf={confidence:.2f}  {subject[:90]}  (reason: {reason})"
            if category in ["political", "ecommerce"]:
                logger.info(log_msg)
            else:
                logger.debug(log_msg)

            if not dry_run:
                try:
                    label_thread(svc, tid, add_ids)
                    logger.debug(f"Applied labels to thread {tid}")
                    time.sleep(SLEEP_SECONDS)
                except HttpError as e:
                    logger.error(f"Failed to label thread {tid}: {e}")
                    errors += 1
                    continue

            processed += 1
            
        except HttpError as e:
            logger.error(f"Gmail API error processing thread {tid}: {e}")
            errors += 1
        except requests.RequestException as e:
            logger.error(f"LLM request error processing thread {tid}: {e}")
            errors += 1
        except Exception as e:
            logger.error(f"Unexpected error processing thread {tid}: {e}", exc_info=True)
            errors += 1

    # Log aggregate performance statistics
    run_elapsed = time.time() - run_start_time
    logger.info(f"Processing complete. Processed: {processed}, Errors: {errors}")
    
    if verbose and performance_stats['total_calls'] > 0:
        avg_latency = performance_stats['total_latency'] / performance_stats['total_calls']
        avg_tokens = performance_stats['total_tokens'] / performance_stats['total_calls'] if performance_stats['total_calls'] > 0 else 0
        avg_throughput = performance_stats['total_tokens'] / performance_stats['total_latency'] if performance_stats['total_latency'] > 0 else 0
        
        logger.info("=" * 60)
        logger.info("Run Performance Summary")
        logger.info("=" * 60)
        logger.info(f"  Total run time:        {run_elapsed:.2f}s")
        logger.info(f"  LLM calls made:        {performance_stats['total_calls']}")
        logger.info(f"  Total LLM latency:     {performance_stats['total_latency']:.2f}s")
        logger.info(f"  Average latency:       {avg_latency:.3f}s per call")
        if performance_stats['latencies']:
            min_latency = min(performance_stats['latencies'])
            max_latency = max(performance_stats['latencies'])
            logger.info(f"  Latency range:         {min_latency:.3f}s - {max_latency:.3f}s")
        logger.info(f"  Total tokens:          {performance_stats['total_tokens']:,}")
        logger.info(f"  Average tokens/call:    {avg_tokens:.1f}")
        logger.info(f"  Average throughput:     {avg_throughput:.2f} tokens/sec")
        if performance_stats['total_prompt_tokens'] > 0:
            logger.info(f"  Total prompt tokens:    {performance_stats['total_prompt_tokens']:,}")
            logger.info(f"  Total completion tokens: {performance_stats['total_completion_tokens']:,}")
        logger.info(f"  Emails per second:      {processed / run_elapsed:.2f}" if run_elapsed > 0 else "  Emails per second:      N/A")
        logger.info("=" * 60)
    
    return processed

def run_daemon(dry_run=False, max_results=MAX_RESULTS, query=DEFAULT_QUERY, 
               interval=DAEMON_INTERVAL, verbose=False):
    """Run in daemon mode, continuously processing emails at regular intervals."""
    global shutdown_requested
    
    logger.info("=" * 80)
    logger.info("Gmail Email Categorizer - Daemon Mode")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  LLM Provider: {LLM_PROVIDER}")
    if LLM_PROVIDER == "ollama":
        logger.info(f"  Ollama URL: {OLLAMA_URL}")
        logger.info(f"  Ollama Model: {OLLAMA_MODEL}")
    else:
        logger.info(f"  OpenAI Model: {OPENAI_MODEL}")
    logger.info(f"  Interval: {interval}s ({interval/60:.1f} minutes)")
    logger.info(f"  Max results per run: {max_results}")
    logger.info(f"  Dry run: {dry_run}")
    logger.info(f"  Credentials path: {CREDENTIALS_PATH}")
    logger.info("=" * 80)
    
    # Perform startup health checks
    if not perform_startup_health_checks():
        logger.error("Startup health checks failed, exiting")
        sys.exit(1)
    
    logger.info("Daemon started successfully")
    logger.info(f"Press Ctrl+C to stop")
    
    run_count = 0
    total_processed = 0
    
    while not shutdown_requested:
        run_count += 1
        start_time = time.time()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Run #{run_count} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")
        
        try:
            processed = run_once(
                dry_run=dry_run,
                max_results=max_results,
                query=query,
                verbose=verbose,
                daemon_mode=True
            )
            total_processed += processed
            
            elapsed = time.time() - start_time
            logger.info(f"Run #{run_count} completed in {elapsed:.1f}s")
            logger.info(f"Total emails processed since startup: {total_processed}")
            
        except Exception as e:
            logger.error(f"Error in run #{run_count}: {e}", exc_info=True)
        
        if shutdown_requested:
            break
        
        # Calculate next run time
        next_run = datetime.now().timestamp() + interval
        next_run_str = datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"Next run scheduled at {next_run_str} (in {interval}s)")
        
        # Sleep with periodic checks for shutdown
        sleep_interval = 5  # Check every 5 seconds
        slept = 0
        while slept < interval and not shutdown_requested:
            time.sleep(min(sleep_interval, interval - slept))
            slept += sleep_interval
    
    logger.info("=" * 80)
    logger.info("Daemon shutting down gracefully")
    logger.info(f"Total runs: {run_count}")
    logger.info(f"Total emails processed: {total_processed}")
    logger.info("=" * 80)

def run_optimize(
    train_data: str,
    val_data: str,
    output: str = "./data/optimized_classifier.json",
    optimizer: str = "bootstrap",
    metric: str = "accuracy",
    max_demos: int = 5,
    use_cot: bool = True
):
    """Run DSPy optimization on evaluation datasets.
    
    Args:
        train_data: Path to training dataset (JSON)
        val_data: Path to validation dataset (JSON)
        output: Output path for optimized classifier
        optimizer: Optimization algorithm ('bootstrap', 'random_search', 'mipro')
        metric: Metric to optimize ('accuracy', 'weighted', 'combined')
        max_demos: Maximum few-shot examples in prompts
        use_cot: If True, use chain-of-thought reasoning
    """
    if not DSPY_AVAILABLE:
        logger.error("DSPy is not available. Install it with: pip install dspy-ai>=2.5.0")
        sys.exit(1)
    
    from evaluation.create_dataset import load_dataset
    from dspy_optimizer import (
        optimize_with_bootstrap_fewshot,
        optimize_with_random_search,
        optimize_with_mipro,
        save_optimized_classifier,
        compare_classifiers,
        EmailClassifierModule
    )
    from dspy_metrics import classification_accuracy, weighted_accuracy, combined_metric
    
    logger.info("=" * 80)
    logger.info("DSPy Classifier Optimization")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  LLM Provider: {LLM_PROVIDER}")
    if LLM_PROVIDER == "ollama":
        logger.info(f"  Ollama Model: {OLLAMA_MODEL}")
    else:
        logger.info(f"  OpenAI Model: {OPENAI_MODEL}")
    logger.info(f"  Optimizer: {optimizer}")
    logger.info(f"  Metric: {metric}")
    logger.info(f"  Max demos: {max_demos}")
    logger.info(f"  Use CoT: {use_cot}")
    logger.info("=" * 80)
    
    # Load datasets
    logger.info(f"Loading training data from {train_data}...")
    train_examples = load_dataset(train_data)
    logger.info(f"  Loaded {len(train_examples)} training examples")
    
    logger.info(f"Loading validation data from {val_data}...")
    val_examples = load_dataset(val_data)
    logger.info(f"  Loaded {len(val_examples)} validation examples")
    
    if not train_examples or not val_examples:
        logger.error("No examples found in datasets")
        sys.exit(1)
    
    # Select metric
    metric_map = {
        'accuracy': classification_accuracy,
        'weighted': weighted_accuracy,
        'combined': combined_metric
    }
    metric_fn = metric_map.get(metric, classification_accuracy)
    
    # Run optimization
    logger.info(f"\nStarting {optimizer} optimization...")
    logger.info("This may take several minutes...")
    
    start_time = time.time()
    
    if optimizer == 'bootstrap':
        optimized = optimize_with_bootstrap_fewshot(
            train_examples, val_examples,
            metric=metric_fn,
            max_bootstrapped_demos=max_demos,
            use_cot=use_cot
        )
    elif optimizer == 'random_search':
        optimized = optimize_with_random_search(
            train_examples, val_examples,
            metric=metric_fn,
            max_bootstrapped_demos=max_demos,
            use_cot=use_cot
        )
    elif optimizer == 'mipro':
        optimized = optimize_with_mipro(
            train_examples, val_examples,
            metric=metric_fn,
            use_cot=use_cot
        )
    else:
        logger.error(f"Unknown optimizer: {optimizer}")
        sys.exit(1)
    
    elapsed = time.time() - start_time
    logger.info(f"✓ Optimization completed in {elapsed:.1f}s")
    
    # Save optimized classifier
    save_optimized_classifier(optimized, output)
    logger.info(f"✓ Saved optimized classifier to {output}")
    
    # Compare baseline vs optimized
    logger.info("\nComparing baseline vs optimized...")
    baseline = EmailClassifierModule(use_cot=use_cot)
    compare_classifiers(baseline, optimized, val_examples, verbose=True)
    
    logger.info("=" * 80)
    logger.info("Optimization Complete!")
    logger.info("=" * 80)
    logger.info(f"\nTo use the optimized classifier:")
    logger.info(f"  1. Set USE_DSPY=true in your environment")
    logger.info(f"  2. Run: python gmail_categorizer.py")
    logger.info("=" * 80)

def main():
    global CREDENTIALS_PATH
    
    ap = argparse.ArgumentParser(
        description="Gmail LLM categorizer (Ecommerce vs Political)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run once (one-time processing)
  %(prog)s --dry-run
  %(prog)s --max 50
  
  # Run in daemon mode (continuous processing)
  %(prog)s --daemon
  %(prog)s --daemon --interval 600  # Check every 10 minutes
  
  # Optimize DSPy classifier
  %(prog)s --optimize --train-data data/train.json --val-data data/val.json
  %(prog)s --optimize --optimizer mipro --max-demos 8
  
  # Docker mode
  %(prog)s --daemon --credentials-path /app/data
        """
    )
    
    # Mode selection
    ap.add_argument("--daemon", action="store_true", 
                    help="Run in daemon mode (continuous processing)")
    ap.add_argument("--optimize", action="store_true",
                    help="Run DSPy optimization (requires train/val datasets)")
    
    # Common options
    ap.add_argument("--dry-run", action="store_true", 
                    help="Don't apply labels, just print decisions")
    ap.add_argument("--max", type=int, default=MAX_RESULTS, 
                    help=f"Max threads per run (default: {MAX_RESULTS})")
    ap.add_argument("--query", type=str, default=DEFAULT_QUERY, 
                    help="Gmail search query")
    ap.add_argument("--verbose", action="store_true", 
                    help="Enable verbose output for LLM calls")
    
    # Daemon mode options
    ap.add_argument("--interval", type=int, default=DAEMON_INTERVAL,
                    help=f"Interval between runs in seconds (daemon mode, default: {DAEMON_INTERVAL})")
    
    # Optimization options
    ap.add_argument("--train-data", type=str,
                    help="Path to training dataset JSON (optimize mode)")
    ap.add_argument("--val-data", type=str,
                    help="Path to validation dataset JSON (optimize mode)")
    ap.add_argument("--optimizer", type=str, default="bootstrap",
                    choices=['bootstrap', 'random_search', 'mipro'],
                    help="Optimization algorithm (optimize mode, default: bootstrap)")
    ap.add_argument("--metric", type=str, default="accuracy",
                    choices=['accuracy', 'weighted', 'combined'],
                    help="Optimization metric (optimize mode, default: accuracy)")
    ap.add_argument("--max-demos", type=int, default=5,
                    help="Max few-shot examples in prompts (optimize mode, default: 5)")
    ap.add_argument("--output", type=str, default="./data/optimized_classifier.json",
                    help="Output path for optimized classifier (optimize mode)")
    ap.add_argument("--no-cot", action="store_true",
                    help="Disable chain-of-thought reasoning (optimize mode)")
    
    # Configuration options
    ap.add_argument("--credentials-path", type=str, default=CREDENTIALS_PATH,
                    help=f"Path to credentials directory (default: {CREDENTIALS_PATH})")
    ap.add_argument("--log-level", type=str, default=LOG_LEVEL,
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                    help=f"Logging level (default: {LOG_LEVEL})")
    
    args = ap.parse_args()
    
    # Update global configuration from args
    if args.credentials_path != CREDENTIALS_PATH:
        CREDENTIALS_PATH = args.credentials_path
        logger.info(f"Credentials path set to {CREDENTIALS_PATH}")
    
    # Update logging level if different
    if args.log_level != LOG_LEVEL:
        logger.setLevel(getattr(logging, args.log_level))
        logger.info(f"Log level set to {args.log_level}")
    
    # Run in optimize, daemon, or one-time mode
    if args.optimize:
        # Validate required arguments for optimization
        if not args.train_data or not args.val_data:
            logger.error("--optimize requires --train-data and --val-data arguments")
            logger.error("Example: python gmail_categorizer.py --optimize --train-data data/train.json --val-data data/val.json")
            sys.exit(1)
        
        run_optimize(
            train_data=args.train_data,
            val_data=args.val_data,
            output=args.output,
            optimizer=args.optimizer,
            metric=args.metric,
            max_demos=args.max_demos,
            use_cot=not args.no_cot
        )
    elif args.daemon:
        run_daemon(
            dry_run=args.dry_run,
            max_results=args.max,
            query=args.query,
            interval=args.interval,
            verbose=args.verbose
        )
    else:
        run_once(
            dry_run=args.dry_run,
            max_results=args.max,
            query=args.query,
            verbose=args.verbose
        )

if __name__ == "__main__":
    main()
