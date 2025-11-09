# Prompt Management System - Architecture Plan

## 🎯 Overview

Add a web-based prompt management and testing system to replace hardcoded prompts in the email categorizer. This will enable:
- **Visual prompt editing** via web interface
- **Prompt versioning** and rollback capability
- **A/B testing** of different prompts
- **Live testing** on real emails before deployment
- **Performance tracking** of prompt effectiveness

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Interface (Port 8080)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Prompt Editor│  │ Test Console │  │ History View │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API
┌─────────────────────────▼───────────────────────────────────┐
│              Prompt Management API (FastAPI)                 │
│  ┌────────────────────────────────────────────────────────┐│
│  │ Endpoints:                                             ││
│  │ - GET/POST/PUT /api/prompts                           ││
│  │ - POST /api/prompts/test (test on emails)            ││
│  │ - POST /api/prompts/activate                          ││
│  │ - GET /api/prompts/history                            ││
│  │ - GET /api/stats (effectiveness metrics)              ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Prompt Storage (SQLite)                     │
│  Tables:                                                     │
│  - prompts (id, name, content, version, created, active)   │
│  - test_results (prompt_id, email_sample, result, metrics) │
│  - prompt_stats (prompt_id, success_rate, avg_confidence)  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│          Gmail Categorizer (Daemon - Modified)               │
│  - Loads active prompt from DB on startup                   │
│  - Reloads on SIGHUP signal                                │
│  - Logs classification results for analysis                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Database Schema

### SQLite Schema

```sql
-- Prompts table
CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    category_types TEXT  -- JSON: ["ecommerce", "political", "none"]
);

-- Test results table
CREATE TABLE test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    email_subject TEXT,
    email_from TEXT,
    email_snippet TEXT,
    predicted_category VARCHAR(50),
    confidence FLOAT,
    reason TEXT,
    processing_time FLOAT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- Prompt statistics table
CREATE TABLE prompt_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    total_tests INTEGER DEFAULT 0,
    avg_confidence FLOAT,
    category_distribution TEXT,  -- JSON: {"ecommerce": 40, "political": 30, "none": 30}
    avg_processing_time FLOAT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- Production usage logs (for effectiveness tracking)
CREATE TABLE classification_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(50),
    confidence FLOAT,
    processing_time FLOAT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- Prompt versions (for rollback)
CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER,
    version_number INTEGER,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changelog TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);
```

---

## 🔌 API Design (FastAPI)

### REST Endpoints

```python
# Prompt Management
GET    /api/prompts                    # List all prompts
GET    /api/prompts/{id}              # Get specific prompt
POST   /api/prompts                    # Create new prompt
PUT    /api/prompts/{id}              # Update prompt
DELETE /api/prompts/{id}              # Delete prompt
POST   /api/prompts/{id}/activate     # Set as active prompt

# Testing
POST   /api/prompts/{id}/test         # Test prompt on sample emails
GET    /api/test-results/{prompt_id}  # Get test results for prompt

# Versioning
GET    /api/prompts/{id}/versions     # Get version history
POST   /api/prompts/{id}/rollback     # Rollback to previous version

# Statistics
GET    /api/stats/prompt/{id}         # Get prompt performance stats
GET    /api/stats/overall             # Overall system stats

# Email Sampling
GET    /api/emails/sample/{count}     # Get sample emails for testing
```

### Example Request/Response

```json
// POST /api/prompts
{
  "name": "Enhanced Ecommerce Detector v2",
  "content": "You are a strict email classifier...",
  "description": "Improved detection for seasonal sales",
  "category_types": ["ecommerce", "political", "none"]
}

// Response
{
  "id": 5,
  "name": "Enhanced Ecommerce Detector v2",
  "version": 1,
  "is_active": false,
  "created_at": "2025-11-09T15:30:00Z"
}

// POST /api/prompts/5/test
{
  "email_count": 20,
  "query": "in:inbox newer_than:7d"
}

// Response
{
  "prompt_id": 5,
  "test_date": "2025-11-09T15:35:00Z",
  "results": [
    {
      "subject": "Black Friday Sale!",
      "from": "store@example.com",
      "category": "ecommerce",
      "confidence": 0.95,
      "reason": "promotional_sale",
      "processing_time": 2.3
    },
    // ... more results
  ],
  "summary": {
    "total": 20,
    "ecommerce": 12,
    "political": 5,
    "none": 3,
    "avg_confidence": 0.87,
    "avg_processing_time": 2.1
  }
}
```

---

## 🎨 Web Interface Design

### Pages/Views

#### 1. Prompt Library (`/`)
```
┌────────────────────────────────────────────────┐
│ Mailtagger - Prompt Management                 │
├────────────────────────────────────────────────┤
│ [+ New Prompt]                    [Stats] [Logs]│
│                                                 │
│ Active Prompt:                                  │
│ ┌──────────────────────────────────────────┐  │
│ │ ✓ Standard Classifier v1                  │  │
│ │   Version 3 | 87% avg confidence           │  │
│ │   [Edit] [Test] [History]                  │  │
│ └──────────────────────────────────────────┘  │
│                                                 │
│ All Prompts:                                    │
│ ┌──────────────────────────────────────────┐  │
│ │ Enhanced Detector v2 (Draft)              │  │
│ │   Version 1 | Tested on 50 emails         │  │
│ │   [Edit] [Test] [Activate]                 │  │
│ └──────────────────────────────────────────┘  │
│ ┌──────────────────────────────────────────┐  │
│ │ Seasonal Sales Focus (Archived)           │  │
│ │   Version 2 | 85% avg confidence           │  │
│ │   [View] [Clone]                           │  │
│ └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

#### 2. Prompt Editor (`/prompts/{id}/edit`)
```
┌────────────────────────────────────────────────┐
│ Edit Prompt: Enhanced Detector v2              │
├────────────────────────────────────────────────┤
│ Name: [Enhanced Detector v2____________]       │
│                                                 │
│ Description:                                    │
│ [Improved detection for seasonal sales____]    │
│                                                 │
│ Prompt Content:                                 │
│ ┌──────────────────────────────────────────┐  │
│ │You are a strict email classifier.        │  │
│ │Classify an email into exactly ONE of:    │  │
│ │1) 'ecommerce' - marketing emails from    │  │
│ │   stores/brands about sales...           │  │
│ │2) 'political' - messages from campaigns  │  │
│ │   ...                                     │  │
│ │                                           │  │
│ │[Markdown/syntax highlighting enabled]     │  │
│ └──────────────────────────────────────────┘  │
│                                                 │
│ Category Types:                                 │
│ [x] ecommerce  [x] political  [x] none         │
│                                                 │
│ [Save Draft] [Test on Emails] [Activate]       │
└────────────────────────────────────────────────┘
```

#### 3. Test Console (`/prompts/{id}/test`)
```
┌────────────────────────────────────────────────┐
│ Test Prompt: Enhanced Detector v2              │
├────────────────────────────────────────────────┤
│ Test Configuration:                             │
│ Email Count: [20▼]  Query: [in:inbox newer_..] │
│ LLM: [○ Ollama ● OpenAI]  [Run Test]           │
│                                                 │
│ Test Results: (20 emails processed)             │
│ ┌──────────────────────────────────────────┐  │
│ │ ✓ ecommerce (conf: 0.95) - 2.1s          │  │
│ │   Subject: Black Friday Sale!             │  │
│ │   From: store@example.com                 │  │
│ │   Reason: promotional_sale                │  │
│ │   [View Email] [Details]                   │  │
│ ├──────────────────────────────────────────┤  │
│ │ ✓ political (conf: 0.88) - 2.3s          │  │
│ │   Subject: Help us reach our goal         │  │
│ │   From: campaign@example.org              │  │
│ │   Reason: fundraising_request             │  │
│ │   [View Email] [Details]                   │  │
│ └──────────────────────────────────────────┘  │
│                                                 │
│ Summary:                                        │
│ Ecommerce: 12 (60%) | Political: 5 (25%)      │
│ None: 3 (15%)                                   │
│ Avg Confidence: 0.87 | Avg Time: 2.1s         │
│                                                 │
│ [Export Results] [Compare with Other Prompt]   │
└────────────────────────────────────────────────┘
```

#### 4. Statistics Dashboard (`/stats`)
```
┌────────────────────────────────────────────────┐
│ Performance Statistics                          │
├────────────────────────────────────────────────┤
│ Active Prompt: Standard Classifier v1           │
│ Running since: Nov 1, 2025 (8 days)            │
│                                                 │
│ [Chart: Classifications over time]              │
│   Ecommerce: ████████████░░ 60%               │
│   Political: █████░░░░░░░░ 25%                │
│   None:      ███░░░░░░░░░░ 15%                │
│                                                 │
│ Performance Metrics:                            │
│ • Total emails processed: 1,234                 │
│ • Avg confidence: 0.87                          │
│ • Avg processing time: 2.3s                     │
│ • Success rate: 94% (user feedback)             │
│                                                 │
│ Comparison with Previous Prompts:               │
│ [Chart: Confidence trends over different prompts]│
└────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Plan

### Phase 1: Backend Infrastructure (Week 1)
- [ ] Create SQLite database schema
- [ ] Build FastAPI backend with core endpoints
- [ ] Implement prompt CRUD operations
- [ ] Add database migration system (Alembic)
- [ ] Create prompt storage service layer

### Phase 2: Prompt Testing System (Week 1-2)
- [ ] Modify gmail_categorizer.py to load prompts from DB
- [ ] Create prompt testing endpoint
- [ ] Implement email sampling functionality
- [ ] Add test result storage and retrieval
- [ ] Build prompt comparison tools

### Phase 3: Web Interface (Week 2-3)
- [ ] Set up frontend framework (React or plain HTML/JS)
- [ ] Build prompt library view
- [ ] Create prompt editor with syntax highlighting
- [ ] Implement test console interface
- [ ] Add statistics dashboard

### Phase 4: Integration (Week 3)
- [ ] Connect daemon to prompt management system
- [ ] Implement hot-reload of prompts (SIGHUP signal)
- [ ] Add production logging for effectiveness tracking
- [ ] Create Docker configuration for web interface
- [ ] Update docker-compose.yml with new service

### Phase 5: Advanced Features (Week 4)
- [ ] Add prompt versioning and rollback
- [ ] Implement A/B testing capability
- [ ] Add user authentication (optional)
- [ ] Create prompt templates library
- [ ] Add export/import functionality

---

## 🐳 Docker Architecture

### Updated docker-compose.yml

```yaml
version: '3.8'

services:
  # Ollama - LLM inference
  ollama:
    image: ollama/ollama:latest
    # ... existing config ...

  # Mailtagger daemon - Email processor
  mailtagger:
    build: .
    # ... existing config ...
    environment:
      - PROMPT_DB_PATH=/app/data/prompts.db
    volumes:
      - ./data:/app/data:rw
  
  # NEW: Prompt Management API
  prompt-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: mailtagger-api
    ports:
      - "8000:8000"
    environment:
      - PROMPT_DB_PATH=/app/data/prompts.db
      - GMAIL_CREDENTIALS_PATH=/app/data
    volumes:
      - ./data:/app/data:rw
    depends_on:
      - ollama
  
  # NEW: Web Interface
  prompt-ui:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: mailtagger-ui
    ports:
      - "8080:80"
    depends_on:
      - prompt-api
    environment:
      - API_URL=http://prompt-api:8000
```

---

## 📁 File Structure

```
mailtagger/
├── gmail_categorizer.py          # Modified to load prompts from DB
├── prompt_manager.py              # NEW - Prompt management service
├── api/
│   ├── __init__.py
│   ├── main.py                    # NEW - FastAPI app
│   ├── models.py                  # NEW - Pydantic models
│   ├── database.py                # NEW - SQLAlchemy setup
│   ├── crud.py                    # NEW - Database operations
│   └── routers/
│       ├── prompts.py             # NEW - Prompt endpoints
│       ├── testing.py             # NEW - Test endpoints
│       └── stats.py               # NEW - Statistics endpoints
├── web/
│   ├── public/
│   │   ├── index.html             # NEW - Main UI
│   │   ├── editor.html            # NEW - Prompt editor
│   │   ├── test.html              # NEW - Test console
│   │   └── stats.html             # NEW - Dashboard
│   ├── src/
│   │   ├── app.js                 # NEW - Main JS
│   │   ├── api.js                 # NEW - API client
│   │   └── components/
│   │       ├── PromptEditor.js    # NEW - Editor component
│   │       └── TestConsole.js     # NEW - Test component
│   ├── styles/
│   │   └── main.css               # NEW - Styles
│   └── Dockerfile                 # NEW - Web UI container
├── Dockerfile.api                 # NEW - API container
├── alembic/                       # NEW - DB migrations
│   ├── versions/
│   └── env.py
├── tests/
│   ├── test_api.py                # NEW - API tests
│   └── test_prompts.py            # NEW - Prompt tests
├── requirements-api.txt           # NEW - API dependencies
└── docker-compose.yml             # Updated with new services
```

---

## 🔒 Security Considerations

### Authentication & Authorization
- Add JWT-based authentication for API
- Role-based access control (viewer, editor, admin)
- Secure prompt editing (prevent injection attacks)

### API Security
- Rate limiting on test endpoints
- Input validation and sanitization
- CORS configuration
- API key for daemon-to-API communication

### Data Protection
- Encrypt sensitive test data
- Limit email content storage
- Regular cleanup of old test results
- Audit logging for prompt changes

---

## 📊 Monitoring & Metrics

### Key Metrics to Track
- **Prompt Performance**
  - Average confidence per category
  - Processing time trends
  - Error rates
  
- **System Usage**
  - API request rates
  - Active users
  - Test frequency
  
- **Classification Quality**
  - Category distribution over time
  - Confidence score trends
  - Manual feedback (if implemented)

---

## 🎯 Success Criteria

### MVP (Minimum Viable Product)
- [ ] Web UI can create/edit/delete prompts
- [ ] Test prompt on 10-50 sample emails
- [ ] View test results with confidence scores
- [ ] Activate prompt for production use
- [ ] Daemon loads active prompt on startup

### Production Ready
- [ ] Prompt versioning and rollback
- [ ] Performance statistics dashboard
- [ ] A/B testing capability
- [ ] Authentication and authorization
- [ ] Comprehensive API documentation

### Nice to Have
- [ ] Real-time classification monitoring
- [ ] Prompt templates library
- [ ] Export/import prompts
- [ ] Collaborative editing
- [ ] Machine learning feedback loop

---

## 💡 Technical Decisions

### Why FastAPI?
- Modern, fast Python web framework
- Automatic API documentation (Swagger)
- Type hints and validation (Pydantic)
- Async support for better performance
- Easy integration with existing Python code

### Why SQLite?
- Zero configuration
- File-based (easy backups)
- Sufficient for single-instance deployment
- Can migrate to PostgreSQL later if needed

### Why Plain HTML/JS (or React)?
- **Plain HTML/JS**: Simpler, no build step, easier to maintain
- **React**: Better UX, component reusability, easier for complex features
- Decision: Start with plain HTML/JS, migrate to React if needed

---

## 🚀 Getting Started

### Development Workflow

1. **Set up database**
   ```bash
   python -m alembic upgrade head
   ```

2. **Seed with default prompt**
   ```bash
   python scripts/seed_prompts.py
   ```

3. **Run API locally**
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

4. **Run web UI**
   ```bash
   cd web && python -m http.server 8080
   ```

5. **Test integration**
   ```bash
   curl http://localhost:8000/api/prompts
   ```

---

## 📖 Documentation Plan

### User Documentation
- [ ] Prompt editing guide
- [ ] Testing best practices
- [ ] Performance optimization tips
- [ ] Troubleshooting guide

### Developer Documentation
- [ ] API reference (auto-generated)
- [ ] Database schema documentation
- [ ] Contributing guide
- [ ] Architecture decisions

### Operations Documentation
- [ ] Deployment guide
- [ ] Backup procedures
- [ ] Monitoring setup
- [ ] Performance tuning

---

## 🔄 Migration Strategy

### Transitioning from Hardcoded Prompts

1. **Extract current prompt**
   - Export PROMPT_RULES to database
   - Set as active prompt v1
   - Keep code fallback for compatibility

2. **Update daemon**
   - Add prompt loading from DB
   - Implement hot-reload (SIGHUP)
   - Maintain backward compatibility

3. **Gradual adoption**
   - Deploy API and UI alongside existing system
   - Test with sample emails
   - Switch active prompt when ready
   - Monitor performance

---

## 📅 Timeline Estimate

**Total: 3-4 weeks (one developer, part-time)**

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1: Backend | 3-4 days | API, database, CRUD operations |
| Phase 2: Testing | 3-4 days | Test system, email sampling |
| Phase 3: Web UI | 5-7 days | Full web interface |
| Phase 4: Integration | 2-3 days | Docker, daemon integration |
| Phase 5: Advanced | 3-5 days | Versioning, A/B testing |

---

## 🎨 UI/UX Mockups

*(Would create actual mockups using Figma or similar tool)*

Key design principles:
- **Simple**: Easy to understand and use
- **Fast**: Quick loading, responsive
- **Clear**: Visual feedback on actions
- **Safe**: Confirmation for destructive actions
- **Helpful**: Tooltips, examples, documentation

---

## 🧪 Testing Strategy

### Unit Tests
- Prompt CRUD operations
- Test result calculations
- Statistics aggregation

### Integration Tests
- API endpoint testing
- Database operations
- Daemon integration

### E2E Tests
- Full workflow: create → test → activate
- Email sampling and classification
- Performance monitoring

---

## 🎉 Benefits of This System

### For Developers
- ✅ Iterate on prompts without code changes
- ✅ Test before deploying
- ✅ Version control for prompts
- ✅ A/B testing capability

### For Operations
- ✅ Monitor prompt performance
- ✅ Quick rollback if needed
- ✅ No downtime for prompt updates
- ✅ Historical performance data

### For Users
- ✅ Better classification accuracy
- ✅ Faster improvements
- ✅ Transparent system behavior
- ✅ Easy customization

---

**Ready to implement? Let's start with Phase 1!**

