# Prompt Management System - Quick Start

## 🎯 Overview

The prompt management system allows you to edit, test, and monitor your email classification prompts through a simple web interface - no code changes required!

## 🚀 Quick Start

### 1. Start the Services

```bash
# Start all services (Ollama, daemon, API, and web UI)
docker-compose up -d

# Or start just the prompt management services
docker-compose up -d prompt-api prompt-ui
```

### 2. Access the Web Interface

Open your browser and go to:
```
http://localhost:8080
```

### 3. Edit Your Prompt

1. Click the **"✏️ Edit Prompt"** tab
2. Modify the prompt content
3. Click **"💾 Save & Activate"**
4. The new prompt is immediately active!

### 4. Test Before Deploying

1. Click the **"🧪 Test"** tab
2. Set number of emails to test (e.g., 10)
3. Click **"Run Test"**
4. Review the results to see how your prompt performs

### 5. Monitor Performance

1. Click the **"📊 Statistics"** tab
2. View classification breakdown and confidence metrics
3. Adjust time period (1 day, 7 days, 30 days)

---

## 📦 What's Included

### Web Interface (`http://localhost:8080`)
- **Edit Prompt**: Visual editor for prompt content
- **Test**: Test prompts on real emails before deploying
- **Statistics**: Performance metrics and category breakdown

### API (`http://localhost:8000`)
- RESTful API for prompt management
- Automatic API documentation at `http://localhost:8000/docs`
- Health check endpoint at `http://localhost:8000/health`

### Database (`./data/prompts.db`)
- SQLite database storing prompts and test results
- Automatic creation and initialization
- Backed up with `./data` directory

---

## 🔧 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/prompt` | GET | Get active prompt |
| `/api/prompt` | PUT | Update active prompt |
| `/api/test` | POST | Test prompt on emails |
| `/api/test-results` | GET | Get recent test results |
| `/api/stats` | GET | Get performance statistics |
| `/api/reload` | POST | Signal daemon to reload |

---

## 💡 Common Workflows

### Edit and Deploy a New Prompt

```
1. Go to Edit tab
2. Modify prompt content
3. Click "Save & Activate"
4. Daemon automatically uses new prompt on next run
```

### Test a Prompt Before Deploying

```
1. Go to Test tab
2. Enter number of emails (e.g., 20)
3. Optionally specify Gmail query
4. Click "Run Test"
5. Review results - check confidence and accuracy
6. If good, go to Edit tab and save
```

### Monitor Prompt Performance

```
1. Go to Statistics tab
2. Select time period
3. Review:
   - Total classifications
   - Average confidence
   - Category breakdown
4. If performance degrades, edit and test new prompt
```

---

## 🗄️ Database Structure

The system uses a simple SQLite database with 3 tables:

### `prompts`
- Stores prompt configurations
- One prompt is "active" at a time
- Historical prompts are retained

### `test_results`
- Stores results from testing prompts
- Helps evaluate prompt performance
- Linked to specific prompts

### `classification_logs`
- Stores production classifications
- Used for statistics and monitoring
- Automatic cleanup of old data

---

## 🔍 Testing Best Practices

### Sample Size
- **Quick check**: 10 emails
- **Thorough test**: 20-30 emails
- **Comprehensive**: 50 emails (max)

### Test Queries
```bash
# Recent inbox emails
in:inbox newer_than:7d

# Specific sender domain
from:@example.com

# Date range
after:2025/11/01 before:2025/11/10

# Exclude already processed
in:inbox newer_than:7d -label:AI_Triaged
```

### What to Look For
- ✅ **High confidence** (>0.85) on correct classifications
- ✅ **Correct categories** for obvious cases
- ✅ **Reasonable processing time** (<5s per email)
- ⚠️ **Low confidence** (<0.7) may indicate unclear emails
- ❌ **Wrong category** = prompt needs improvement

---

## 🛠️ Troubleshooting

### Web UI won't load
```bash
# Check if services are running
docker-compose ps

# Check logs
docker-compose logs prompt-ui

# Restart services
docker-compose restart prompt-ui prompt-api
```

### API errors during testing
```bash
# Check API logs
docker-compose logs prompt-api

# Verify Ollama is running
docker-compose ps ollama

# Check Gmail credentials
ls -la ./data/credentials.json ./data/token.json
```

### No statistics showing
```bash
# Statistics require the daemon to be processing emails
docker-compose ps mailtagger

# Check daemon logs
docker-compose logs mailtagger

# Make sure daemon is in daemon mode
docker-compose logs mailtagger | grep "Daemon Mode"
```

### Prompt not updating in daemon
```bash
# The daemon reloads prompts on each processing run
# Check when last run occurred
docker-compose logs mailtagger | grep "Run #"

# Or manually restart the daemon
docker-compose restart mailtagger
```

---

## 📊 Example Prompt

Here's the default prompt structure:

```
You are a strict email classifier. Classify an email into exactly ONE of two buckets:

1) 'ecommerce' – marketing or campaign emails from stores/brands about sales, 
   product launches, coupons, promotions, newsletters from retailers.
   Include brand newsletters, 'shop now', seasonal sales, product announcements, 
   abandoned cart promos, discount codes.
   Exclude order receipts or shipping notifications if purely transactional.

2) 'political' – messages from campaigns, candidates, PACs, NGOs/activist orgs 
   soliciting donations, petitions, or political actions. 
   Look for cues like ActBlue/WinRed links, 'chip in', 'end-of-quarter', 
   'paid for by', election/candidate names.

If neither fits, choose 'ecommerce' ONLY if it's clearly a store/brand campaign; 
otherwise return 'none'.

IMPORTANT: Respond with ONLY valid JSON. No additional text, no explanations outside the JSON.

Format: {"category": "ecommerce|political|none", "reason": "short explanation", "confidence": 0.9}

Be conservative and only pick 'political' if clearly political.
```

---

## 🔐 Security Notes

- **No authentication**: System assumes VPN/private network protection
- **Credentials**: Gmail credentials stored in `./data/` (excluded from git)
- **Database**: SQLite file in `./data/` directory
- **Network**: Services on internal Docker network by default

---

## 📁 File Structure

```
mailtagger/
├── prompt_service.py          # Prompt management service
├── api.py                      # FastAPI backend
├── web/
│   ├── index.html              # Web interface
│   ├── style.css               # Styles
│   └── app.js                  # Frontend logic
├── data/
│   ├── prompts.db              # SQLite database (created automatically)
│   ├── credentials.json        # Gmail credentials
│   └── token.json              # Gmail OAuth token
├── requirements-api.txt        # API dependencies
├── Dockerfile.api              # API container
└── docker-compose.yml          # Updated with new services
```

---

## 🎓 Tips & Tricks

### 1. Iterative Improvement
- Start with default prompt
- Test on 20 emails
- Note misclassifications
- Adjust prompt to address issues
- Test again

### 2. Be Specific
- Add examples of edge cases
- Specify what to exclude
- Use clear category definitions

### 3. JSON Format
- Always require JSON response
- Specify exact format
- LLM is more consistent with strict format

### 4. Confidence Scores
- Ask for confidence in response
- Use to filter low-confidence results
- Lower confidence = needs human review

### 5. Monitor Over Time
- Check statistics weekly
- Look for confidence trends
- Adjust if performance degrades

---

## 🚀 Next Steps

1. **Familiarize yourself** with the web interface
2. **Test the default prompt** to see baseline performance
3. **Make small tweaks** and test iteratively
4. **Monitor statistics** after deploying changes
5. **Keep backups** of well-performing prompts (copy text)

---

**Happy prompt crafting! 🎨**

Questions or issues? Check the logs:
```bash
docker-compose logs prompt-api
docker-compose logs mailtagger
```

