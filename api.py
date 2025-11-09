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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import from existing modules
from prompt_service import PromptService

# Try to import gmail categorizer for testing
try:
    import gmail_categorizer
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Configuration
PROMPT_DB_PATH = os.getenv("PROMPT_DB_PATH", "./data/prompts.db")
DAEMON_PID_FILE = os.getenv("DAEMON_PID_FILE", "./data/daemon.pid")

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
        "prompt_db": os.path.exists(PROMPT_DB_PATH)
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

