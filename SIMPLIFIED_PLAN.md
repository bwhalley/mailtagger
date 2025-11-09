# Simplified Prompt Management System

## 🎯 Scope

**Single-user, minimal web interface for:**
1. ✅ Edit prompts visually
2. ✅ Test on sample emails
3. ✅ View performance statistics
4. ❌ No authentication (VPN-protected)
5. ❌ No A/B testing
6. ❌ No version history

---

## 🏗️ Simple Architecture

```
┌─────────────────────────────────────┐
│   Web UI (Plain HTML/CSS/JS)       │
│   - Single page app                 │
│   - 3 tabs: Edit | Test | Stats     │
│   Port: 8080                        │
└─────────────┬───────────────────────┘
              │ REST API
┌─────────────▼───────────────────────┐
│   FastAPI Backend                   │
│   - 6 endpoints (simple CRUD)       │
│   Port: 8000                        │
└─────────────┬───────────────────────┘
              │
┌─────────────▼───────────────────────┐
│   SQLite Database (prompts.db)      │
│   - prompts (1 active at a time)    │
│   - test_results                    │
│   - classification_logs             │
└─────────────────────────────────────┘
              │
┌─────────────▼───────────────────────┐
│   Gmail Daemon (Modified)           │
│   - Loads active prompt from DB     │
│   - Logs classifications            │
└─────────────────────────────────────┘
```

---

## 📊 Minimal Database Schema

```sql
-- Just 3 tables

CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    email_subject TEXT,
    predicted_category VARCHAR(50),
    confidence FLOAT,
    processing_time FLOAT
);

CREATE TABLE classification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(50),
    confidence FLOAT
);
```

---

## 🔌 Simple API (6 endpoints)

```python
GET    /api/prompt              # Get active prompt
PUT    /api/prompt              # Update active prompt
POST   /api/test                # Test prompt on N emails
GET    /api/test-results        # Get recent test results
GET    /api/stats               # Get performance stats
POST   /api/reload              # Signal daemon to reload
```

---

## 🎨 Minimal Web UI (Single HTML Page)

```html
<!DOCTYPE html>
<html>
<head>
    <title>Mailtagger Prompt Manager</title>
    <style>
        /* Simple, clean CSS - no frameworks */
        body { font-family: sans-serif; max-width: 1200px; margin: 0 auto; }
        .tabs { /* Simple tab navigation */ }
        .tab-content { /* Tab panels */ }
        textarea { width: 100%; height: 400px; font-family: monospace; }
    </style>
</head>
<body>
    <h1>Mailtagger Prompt Manager</h1>
    
    <!-- Tab Navigation -->
    <div class="tabs">
        <button onclick="showTab('edit')">Edit Prompt</button>
        <button onclick="showTab('test')">Test</button>
        <button onclick="showTab('stats')">Statistics</button>
    </div>
    
    <!-- Edit Tab -->
    <div id="edit-tab" class="tab-content">
        <h2>Edit Prompt</h2>
        <textarea id="prompt-content"></textarea>
        <button onclick="savePrompt()">Save & Activate</button>
    </div>
    
    <!-- Test Tab -->
    <div id="test-tab" class="tab-content">
        <h2>Test Prompt</h2>
        <label>Email Count: <input type="number" value="10"></label>
        <button onclick="runTest()">Run Test</button>
        <div id="test-results"></div>
    </div>
    
    <!-- Stats Tab -->
    <div id="stats-tab" class="tab-content">
        <h2>Performance Statistics</h2>
        <div id="stats-display"></div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

---

## 📁 Simple File Structure

```
mailtagger/
├── gmail_categorizer.py       # Modified: load prompt from DB
├── prompt_service.py           # NEW: Simple prompt manager
├── api.py                      # NEW: FastAPI app (200 lines)
├── web/
│   ├── index.html              # NEW: Single page UI
│   ├── app.js                  # NEW: Simple JS (no frameworks)
│   └── style.css               # NEW: Minimal styles
├── requirements-api.txt        # NEW: FastAPI, SQLAlchemy
├── Dockerfile.api              # NEW: API container
└── docker-compose.yml          # Updated: add api + web services
```

---

## ⚡ Quick Implementation Plan

### Phase 1: Backend (Day 1-2)
- [ ] Create SQLite schema
- [ ] Build simple FastAPI app (6 endpoints)
- [ ] Add prompt service layer
- [ ] Seed with current prompt

### Phase 2: Web UI (Day 2-3)
- [ ] Create single HTML page
- [ ] Add simple JS for API calls
- [ ] Basic CSS styling
- [ ] Test functionality

### Phase 3: Integration (Day 3)
- [ ] Modify daemon to load from DB
- [ ] Add classification logging
- [ ] Update Docker setup
- [ ] Test end-to-end

**Total time: 3-4 days**

---

## 🐳 Docker Setup

```yaml
# docker-compose.yml additions

services:
  # ... existing ollama, mailtagger ...
  
  prompt-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:rw
    environment:
      - PROMPT_DB_PATH=/app/data/prompts.db
      - GMAIL_CREDENTIALS_PATH=/app/data
  
  prompt-ui:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./web:/usr/share/nginx/html:ro
```

---

## ✅ MVP Features

### Prompt Editor
- Single textarea for prompt content
- Save button activates immediately
- Current prompt loads on page load

### Testing
- Input: number of emails to test
- Output: simple table of results
  - Subject
  - Category
  - Confidence
  - Time
- Summary stats at bottom

### Statistics
- Total classifications (last 7 days)
- Category breakdown (pie chart or bars)
- Average confidence
- Average processing time

---

## 🚀 Let's Start!

I'll begin implementing in this order:
1. Database schema + initialization
2. FastAPI backend
3. Modify daemon
4. Simple web UI
5. Docker configuration

Ready to proceed?

