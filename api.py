#!/usr/bin/env python3
"""
Simple FastAPI backend for mailtagger prompt management.
No authentication - single user, VPN-protected deployment.
"""

import os
import time
import signal
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

# Import from existing modules
from prompt_service import PromptService

# Try to import gmail categorizer for testing
try:
    import gmail_categorizer
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Import Google OAuth libraries
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

# Configuration
PROMPT_DB_PATH = os.getenv("PROMPT_DB_PATH", "./data/prompts.db")
DAEMON_PID_FILE = os.getenv("DAEMON_PID_FILE", "./data/daemon.pid")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", ".")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# OAuth redirect URI (will be configured dynamically)
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")

# Initialize app and services
app = FastAPI(
    title="Mailtagger Prompt API",
    description="Simple API for managing email classification prompts",
    version="1.0.0"
)

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # VPN-protected, no auth needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize prompt service
prompt_service = PromptService(PROMPT_DB_PATH)

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class PromptUpdate(BaseModel):
    """Model for updating a prompt."""
    name: str
    content: str


class TestRequest(BaseModel):
    """Model for testing a prompt."""
    email_count: int = 10
    query: Optional[str] = None
    prompt_content: Optional[str] = None  # If provided, test this instead of active


class TestResult(BaseModel):
    """Model for a single test result."""
    subject: str
    from_addr: str
    category: str
    confidence: float
    reason: str
    processing_time: float


class TestResponse(BaseModel):
    """Model for test response."""
    prompt_id: Optional[int]
    prompt_name: Optional[str]
    test_date: str
    results: List[TestResult]
    summary: Dict[str, Any]


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Mailtagger Prompt API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/prompt": "Get active prompt",
            "PUT /api/prompt": "Update active prompt",
            "POST /api/test": "Test prompt on sample emails",
            "GET /api/test-results": "Get recent test results",
            "GET /api/stats": "Get performance statistics",
            "POST /api/reload": "Signal daemon to reload prompt"
        }
    }


@app.get("/api/prompt")
async def get_prompt():
    """Get the currently active prompt."""
    prompt = prompt_service.get_active_prompt()
    if not prompt:
        raise HTTPException(status_code=404, detail="No active prompt found")
    return prompt


@app.put("/api/prompt")
async def update_prompt(prompt: PromptUpdate):
    """Update the active prompt."""
    try:
        updated = prompt_service.update_prompt(prompt.name, prompt.content)
        return {
            "success": True,
            "prompt": updated,
            "message": "Prompt updated and activated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/test")
async def test_prompt(request: TestRequest):
    """Test a prompt on sample emails from Gmail."""
    if not GMAIL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Gmail categorizer not available. Check imports."
        )
    
    try:
        # Get the prompt to test
        if request.prompt_content:
            # Testing a draft prompt (not saved)
            test_prompt = request.prompt_content
            prompt_id = None
            prompt_name = "Draft (unsaved)"
        else:
            # Testing the active prompt
            active = prompt_service.get_active_prompt()
            if not active:
                raise HTTPException(status_code=404, detail="No active prompt found")
            test_prompt = active["content"]
            prompt_id = active["id"]
            prompt_name = active["name"]
        
        # Get Gmail service
        svc = gmail_categorizer.gmail_service()
        
        # Get sample emails
        query = request.query or gmail_categorizer.DEFAULT_QUERY
        threads = gmail_categorizer.list_threads(svc, query, request.email_count)
        
        if not threads:
            return {
                "prompt_id": prompt_id,
                "prompt_name": prompt_name,
                "test_date": datetime.now().isoformat(),
                "results": [],
                "summary": {"total": 0, "message": "No emails found matching query"}
            }
        
        # Test each email
        results = []
        category_counts = {"ecommerce": 0, "political": 0, "none": 0}
        total_confidence = 0
        total_time = 0
        
        for t in threads[:request.email_count]:
            try:
                th = gmail_categorizer.get_thread(svc, t['id'])
                msgs = th.get('messages', [])
                if not msgs:
                    continue
                
                first = msgs[0]
                payload = first.get('payload', {})
                headers = payload.get('headers', [])
                subject, sender = gmail_categorizer.get_subject_and_from(headers)
                text = gmail_categorizer.extract_text_from_payload(payload) or ""
                snippet = gmail_categorizer.safe_snippet(text, 4000)
                
                print(f"  Extracted {len(text)} chars, using {len(snippet)} char snippet")
                
                # Classify with the test prompt (temporarily override PROMPT_RULES)
                start_time = time.time()
                
                # Create a temporary prompt for testing
                original_prompt = gmail_categorizer.PROMPT_RULES
                gmail_categorizer.PROMPT_RULES = test_prompt
                
                try:
                    result = gmail_categorizer.call_llm_classifier(subject, snippet, sender, False)
                finally:
                    # Restore original prompt
                    gmail_categorizer.PROMPT_RULES = original_prompt
                
                elapsed = time.time() - start_time
                
                category = (result.get("category") or "none").lower()
                confidence = float(result.get("confidence", 0))
                reason = result.get("reason", "")
                
                # Track counts
                category_counts[category] = category_counts.get(category, 0) + 1
                total_confidence += confidence
                total_time += elapsed
                
                # Save test result if testing active prompt
                if prompt_id:
                    prompt_service.save_test_result(
                        prompt_id, subject, sender, category,
                        confidence, reason, elapsed
                    )
                
                results.append(TestResult(
                    subject=subject[:100],
                    from_addr=sender,
                    category=category,
                    confidence=round(confidence, 3),
                    reason=reason,
                    processing_time=round(elapsed, 2)
                ))
                
            except Exception as e:
                print(f"Error processing email: {e}")
                continue
        
        # Calculate summary
        total = len(results)
        summary = {
            "total": total,
            "ecommerce": category_counts.get("ecommerce", 0),
            "political": category_counts.get("political", 0),
            "none": category_counts.get("none", 0),
            "avg_confidence": round(total_confidence / total, 3) if total > 0 else 0,
            "avg_processing_time": round(total_time / total, 2) if total > 0 else 0
        }
        
        return TestResponse(
            prompt_id=prompt_id,
            prompt_name=prompt_name,
            test_date=datetime.now().isoformat(),
            results=results,
            summary=summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@app.get("/api/test-results")
async def get_test_results(limit: int = 50):
    """Get recent test results."""
    try:
        results = prompt_service.get_recent_test_results(limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats(days: int = 7):
    """Get performance statistics."""
    try:
        stats = prompt_service.get_statistics(days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reload")
async def reload_daemon():
    """Signal the daemon to reload the prompt."""
    try:
        # Try to read PID file
        if not os.path.exists(DAEMON_PID_FILE):
            return {
                "success": False,
                "message": "Daemon PID file not found. Daemon may not be running."
            }
        
        with open(DAEMON_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGHUP signal
        os.kill(pid, signal.SIGHUP)
        
        return {
            "success": True,
            "message": f"Sent SIGHUP signal to daemon (PID: {pid})"
        }
        
    except ProcessLookupError:
        return {
            "success": False,
            "message": "Daemon process not found. It may have stopped."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to signal daemon: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "gmail_available": GMAIL_AVAILABLE,
        "prompt_db": os.path.exists(PROMPT_DB_PATH),
        "oauth_available": OAUTH_AVAILABLE
    }


# ============================================================================
# Gmail OAuth Endpoints
# ============================================================================

@app.get("/api/gmail/status")
async def gmail_auth_status():
    """Check Gmail authorization status."""
    token_path = Path(CREDENTIALS_PATH) / 'token.json'
    creds_path = Path(CREDENTIALS_PATH) / 'credentials.json'
    
    status = {
        "credentials_exists": creds_path.exists(),
        "token_exists": token_path.exists(),
        "authorized": False,
        "email": None,
        "token_valid": False
    }
    
    # Check if credentials.json exists
    if not creds_path.exists():
        status["message"] = "credentials.json not found. Please upload Gmail API credentials."
        return status
    
    # Check if token exists and is valid
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            
            if creds and creds.valid:
                status["authorized"] = True
                status["token_valid"] = True
                status["message"] = "Gmail is authorized and ready!"
                
                # Try to get email address
                try:
                    from googleapiclient.discovery import build
                    service = build('gmail', 'v1', credentials=creds)
                    profile = service.users().getProfile(userId='me').execute()
                    status["email"] = profile.get('emailAddress')
                except Exception as e:
                    logger.warning(f"Could not fetch email address: {e}")
                    
            elif creds and creds.expired and creds.refresh_token:
                # Try to refresh
                try:
                    creds.refresh(GoogleRequest())
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                    status["authorized"] = True
                    status["token_valid"] = True
                    status["message"] = "Token refreshed successfully!"
                except Exception as e:
                    status["message"] = f"Token expired and refresh failed: {str(e)}"
            else:
                status["message"] = "Token exists but is invalid. Please reauthorize."
        except Exception as e:
            status["message"] = f"Error reading token: {str(e)}"
    else:
        status["message"] = "Not authorized. Please click 'Authorize Gmail' to begin."
    
    return status


@app.get("/api/oauth/start")
async def start_oauth_flow(request: Request):
    """Start Gmail OAuth flow."""
    if not OAUTH_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OAuth libraries not available. Install google-auth-oauthlib."
        )
    
    creds_path = Path(CREDENTIALS_PATH) / 'credentials.json'
    
    if not creds_path.exists():
        raise HTTPException(
            status_code=404,
            detail="credentials.json not found. Please upload Gmail API credentials first."
        )
    
    try:
        # Determine redirect URI based on request headers
        # Check X-Forwarded-Proto and X-Forwarded-Host first (set by nginx)
        proto = request.headers.get('x-forwarded-proto', 'https')
        host = request.headers.get('x-forwarded-host') or request.headers.get('host', '')
        
        if host and 'hanweir.146sharon.com' in host:
            # Use the forwarded host (from nginx)
            redirect_uri = f"{proto}://{host}/api/oauth/callback"
        else:
            # Fallback to configured value
            redirect_uri = OAUTH_REDIRECT_URI
        
        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            str(creds_path),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Generate authorization URL
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to get refresh token
        )
        
        # Store state for verification (in production, use session or cache)
        # For simplicity, we'll store in a file
        state_path = Path(CREDENTIALS_PATH) / 'oauth_state.txt'
        with open(state_path, 'w') as f:
            f.write(state)
        
        return {
            "auth_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start OAuth flow: {str(e)}"
        )


@app.get("/api/oauth/callback")
async def oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handle OAuth callback from Google."""
    if error:
        return RedirectResponse(
            url=f"/?oauth_error={error}",
            status_code=302
        )
    
    if not code or not state:
        return RedirectResponse(
            url="/?oauth_error=missing_code_or_state",
            status_code=302
        )
    
    try:
        creds_path = Path(CREDENTIALS_PATH) / 'credentials.json'
        state_path = Path(CREDENTIALS_PATH) / 'oauth_state.txt'
        token_path = Path(CREDENTIALS_PATH) / 'token.json'
        
        # Verify state
        if state_path.exists():
            with open(state_path, 'r') as f:
                expected_state = f.read().strip()
            if state != expected_state:
                return RedirectResponse(
                    url="/?oauth_error=invalid_state",
                    status_code=302
                )
            # Clean up state file
            state_path.unlink()
        
        # Determine redirect URI (must match what was used in start_oauth_flow)
        proto = request.headers.get('x-forwarded-proto', 'https')
        host = request.headers.get('x-forwarded-host') or request.headers.get('host', '')
        
        if host and 'hanweir.146sharon.com' in host:
            redirect_uri = f"{proto}://{host}/api/oauth/callback"
        else:
            # Try to construct from request URL
            redirect_uri = str(request.url).split('?')[0]
        
        # Exchange code for token
        flow = Flow.from_client_secrets_file(
            str(creds_path),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
            state=state
        )
        
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save credentials
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        
        logger.info("Gmail OAuth completed successfully!")
        
        # Redirect back to main page with success message
        return RedirectResponse(
            url="/?oauth_success=true",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/?oauth_error={str(e)}",
            status_code=302
        )


@app.post("/api/gmail/revoke")
async def revoke_gmail_auth():
    """Revoke Gmail authorization (delete token)."""
    token_path = Path(CREDENTIALS_PATH) / 'token.json'
    
    if token_path.exists():
        token_path.unlink()
        return {"success": True, "message": "Authorization revoked"}
    else:
        return {"success": False, "message": "No authorization to revoke"}


# ============================================================================
# DSPy Optimization & Evaluation Endpoints
# ============================================================================

class OptimizeRequest(BaseModel):
    """Request model for optimization."""
    train_data_path: str
    val_data_path: str
    optimizer: str = "bootstrap"
    metric: str = "accuracy"
    max_demos: int = 5
    use_cot: bool = True


class EvaluateRequest(BaseModel):
    """Request model for evaluation."""
    dataset_path: str
    use_optimized: bool = False


@app.post("/api/optimize")
async def optimize_classifier(request: OptimizeRequest):
    """Trigger DSPy classifier optimization.
    
    This runs the DSPy optimization process to improve the classifier
    using training and validation datasets.
    """
    try:
        # Check if DSPy is available
        try:
            import dspy
            from evaluation.create_dataset import load_dataset
            from dspy_optimizer import (
                optimize_with_bootstrap_fewshot,
                optimize_with_random_search,
                optimize_with_mipro,
                save_optimized_classifier,
                EmailClassifierModule
            )
            from dspy_metrics import classification_accuracy, weighted_accuracy, combined_metric
            from dspy_config import configure_dspy_lm
        except ImportError as e:
            return {
                "success": False,
                "error": f"DSPy not available: {str(e)}"
            }
        
        # Validate paths
        if not Path(request.train_data_path).exists():
            return {"success": False, "error": f"Training data not found: {request.train_data_path}"}
        if not Path(request.val_data_path).exists():
            return {"success": False, "error": f"Validation data not found: {request.val_data_path}"}
        
        # Load datasets
        logger.info(f"Loading datasets for optimization...")
        train_examples = load_dataset(request.train_data_path)
        val_examples = load_dataset(request.val_data_path)
        
        if not train_examples or not val_examples:
            return {"success": False, "error": "No examples found in datasets"}
        
        # Configure DSPy
        configure_dspy_lm()
        
        # Select metric
        metric_map = {
            'accuracy': classification_accuracy,
            'weighted': weighted_accuracy,
            'combined': combined_metric
        }
        metric_fn = metric_map.get(request.metric, classification_accuracy)
        
        # Run optimization
        logger.info(f"Starting {request.optimizer} optimization...")
        
        if request.optimizer == 'bootstrap':
            optimized = optimize_with_bootstrap_fewshot(
                train_examples, val_examples,
                metric=metric_fn,
                max_bootstrapped_demos=request.max_demos,
                use_cot=request.use_cot
            )
        elif request.optimizer == 'random_search':
            optimized = optimize_with_random_search(
                train_examples, val_examples,
                metric=metric_fn,
                max_bootstrapped_demos=request.max_demos,
                use_cot=request.use_cot
            )
        elif request.optimizer == 'mipro':
            optimized = optimize_with_mipro(
                train_examples, val_examples,
                metric=metric_fn,
                use_cot=request.use_cot
            )
        else:
            return {"success": False, "error": f"Unknown optimizer: {request.optimizer}"}
        
        # Save optimized classifier
        output_path = "./data/optimized_classifier.json"
        save_optimized_classifier(optimized, output_path)
        
        logger.info(f"Optimization complete, saved to {output_path}")
        
        return {
            "success": True,
            "message": "Optimization completed successfully",
            "output_path": output_path,
            "train_examples": len(train_examples),
            "val_examples": len(val_examples),
            "optimizer": request.optimizer
        }
        
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/evaluate")
async def evaluate_classifier(request: EvaluateRequest):
    """Evaluate classifier on a dataset.
    
    Returns accuracy, F1 scores, and other metrics.
    """
    try:
        # Check if DSPy is available
        try:
            import dspy
            from evaluation.create_dataset import load_dataset
            from dspy_optimizer import EmailClassifierModule, load_optimized_classifier
            from dspy_metrics import evaluate_classifier
            from dspy_config import configure_dspy_lm
        except ImportError as e:
            return {
                "success": False,
                "error": f"DSPy not available: {str(e)}"
            }
        
        # Validate path
        if not Path(request.dataset_path).exists():
            return {"success": False, "error": f"Dataset not found: {request.dataset_path}"}
        
        # Load dataset
        logger.info(f"Loading evaluation dataset...")
        examples = load_dataset(request.dataset_path)
        
        if not examples:
            return {"success": False, "error": "No examples found in dataset"}
        
        # Configure DSPy
        configure_dspy_lm()
        
        # Load classifier
        if request.use_optimized:
            optimized_path = "./data/optimized_classifier.json"
            if not Path(optimized_path).exists():
                return {"success": False, "error": "No optimized classifier found"}
            classifier = load_optimized_classifier(optimized_path)
        else:
            classifier = EmailClassifierModule(use_cot=True)
        
        # Evaluate
        logger.info(f"Evaluating classifier...")
        results = evaluate_classifier(classifier, examples)
        
        return {
            "success": True,
            "results": results,
            "num_examples": len(examples),
            "classifier_type": "optimized" if request.use_optimized else "baseline"
        }
        
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/few-shot-examples")
async def get_few_shot_examples(limit: int = 10, category: Optional[str] = None):
    """Get few-shot examples from the example store."""
    try:
        from prompt_service import ExampleStore
        
        example_store = ExampleStore(PROMPT_DB_PATH)
        
        if category:
            examples = example_store.get_best_examples(category=category, k=limit)
        else:
            examples = example_store.get_all_examples(limit=limit)
        
        return {
            "success": True,
            "examples": examples,
            "count": len(examples)
        }
        
    except Exception as e:
        logger.error(f"Error fetching examples: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/few-shot-examples")
async def add_few_shot_example(
    sender: str,
    subject: str,
    body: str,
    category: str,
    confidence: float = 1.0,
    verified: bool = False,
    notes: Optional[str] = None
):
    """Add a new few-shot example to the store."""
    try:
        from prompt_service import ExampleStore
        
        example_store = ExampleStore(PROMPT_DB_PATH)
        
        example_id = example_store.add_example(
            sender=sender,
            subject=subject,
            body=body,
            category=category,
            confidence=confidence,
            verified=verified,
            notes=notes
        )
        
        return {
            "success": True,
            "example_id": example_id,
            "message": "Example added successfully"
        }
        
    except Exception as e:
        logger.error(f"Error adding example: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.delete("/api/few-shot-examples/{example_id}")
async def delete_few_shot_example(example_id: int):
    """Delete a few-shot example."""
    try:
        from prompt_service import ExampleStore
        
        example_store = ExampleStore(PROMPT_DB_PATH)
        example_store.delete_example(example_id)
        
        return {
            "success": True,
            "message": f"Example {example_id} deleted"
        }
        
    except Exception as e:
        logger.error(f"Error deleting example: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/example-store-stats")
async def get_example_store_stats():
    """Get statistics about the example store."""
    try:
        from prompt_service import ExampleStore
        
        example_store = ExampleStore(PROMPT_DB_PATH)
        stats = example_store.get_statistics()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    print("🚀 Mailtagger Prompt API starting...")
    print(f"   Database: {PROMPT_DB_PATH}")
    print(f"   Gmail available: {GMAIL_AVAILABLE}")
    
    # Ensure database is initialized
    prompt_service._ensure_database()
    
    active = prompt_service.get_active_prompt()
    if active:
        print(f"   Active prompt: {active['name']}")
    else:
        print("   ⚠️  No active prompt found")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("👋 Mailtagger Prompt API shutting down...")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting API server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

