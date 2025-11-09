// Mailtagger Prompt Manager - Frontend JavaScript
// Simple vanilla JS - no frameworks

// Configuration
const API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : 'http://localhost:8000';  // Update for production

// ============================================================================
// Tab Management
// ============================================================================

function showTab(tabName) {
    // Hide all tabs
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    // Remove active class from buttons
    const buttons = document.querySelectorAll('.tab-button');
    buttons.forEach(btn => btn.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');
    
    // Load data for the tab
    if (tabName === 'edit') {
        loadPrompt();
    } else if (tabName === 'stats') {
        loadStats();
    }
}

// ============================================================================
// Prompt Management
// ============================================================================

async function loadPrompt() {
    try {
        const response = await fetch(`${API_URL}/api/prompt`);
        if (!response.ok) {
            throw new Error('Failed to load prompt');
        }
        
        const data = await response.json();
        document.getElementById('prompt-name').value = data.name || '';
        document.getElementById('prompt-content').value = data.content || '';
        
        showStatus('save-status', 'Prompt loaded', 'success');
    } catch (error) {
        showStatus('save-status', `Error loading prompt: ${error.message}`, 'error');
    }
}

async function savePrompt() {
    const name = document.getElementById('prompt-name').value.trim();
    const content = document.getElementById('prompt-content').value.trim();
    
    if (!name) {
        showStatus('save-status', 'Please enter a prompt name', 'error');
        return;
    }
    
    if (!content) {
        showStatus('save-status', 'Please enter prompt content', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/prompt`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ name, content })
        });
        
        if (!response.ok) {
            throw new Error('Failed to save prompt');
        }
        
        const data = await response.json();
        showStatus('save-status', 
            `✅ Prompt saved and activated! The daemon will use this prompt on next run.`, 
            'success');
        
        // Optionally signal daemon to reload
        setTimeout(signalDaemonReload, 1000);
        
    } catch (error) {
        showStatus('save-status', `Error saving prompt: ${error.message}`, 'error');
    }
}

async function signalDaemonReload() {
    try {
        const response = await fetch(`${API_URL}/api/reload`, {
            method: 'POST'
        });
        const data = await response.json();
        if (data.success) {
            console.log('Daemon reload signal sent successfully');
        }
    } catch (error) {
        console.log('Could not signal daemon reload:', error.message);
    }
}

// ============================================================================
// Testing
// ============================================================================

async function runTest() {
    const emailCount = parseInt(document.getElementById('email-count').value);
    const query = document.getElementById('test-query').value.trim();
    
    if (emailCount < 1 || emailCount > 50) {
        alert('Please enter a number between 1 and 50');
        return;
    }
    
    // Show loading
    document.getElementById('test-loading').style.display = 'block';
    document.getElementById('test-results').innerHTML = '';
    
    try {
        const response = await fetch(`${API_URL}/api/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                email_count: emailCount,
                query: query || null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Test failed');
        }
        
        const data = await response.json();
        displayTestResults(data);
        
    } catch (error) {
        document.getElementById('test-results').innerHTML = `
            <div class="status status-error">
                Error running test: ${error.message}
            </div>
        `;
    } finally {
        document.getElementById('test-loading').style.display = 'none';
    }
}

function displayTestResults(data) {
    const container = document.getElementById('test-results');
    
    if (data.results.length === 0) {
        container.innerHTML = `
            <div class="status status-error">
                No emails found matching the query.
            </div>
        `;
        return;
    }
    
    // Summary
    const summary = data.summary;
    const html = `
        <div class="test-summary">
            <h3>Test Results Summary</h3>
            <p><strong>Prompt:</strong> ${data.prompt_name}</p>
            <p><strong>Test Date:</strong> ${new Date(data.test_date).toLocaleString()}</p>
            
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">${summary.total}</div>
                    <div class="summary-label">Total Emails</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${summary.ecommerce}</div>
                    <div class="summary-label">Ecommerce</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${summary.political}</div>
                    <div class="summary-label">Political</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${summary.none}</div>
                    <div class="summary-label">None</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${summary.avg_confidence.toFixed(2)}</div>
                    <div class="summary-label">Avg Confidence</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">${summary.avg_processing_time.toFixed(1)}s</div>
                    <div class="summary-label">Avg Time</div>
                </div>
            </div>
        </div>
        
        <h3>Individual Results</h3>
        <div class="result-list">
            ${data.results.map(result => `
                <div class="result-item">
                    <div class="result-header">
                        <span class="result-category category-${result.category}">
                            ${result.category.toUpperCase()}
                        </span>
                        <span class="result-confidence">
                            Confidence: ${(result.confidence * 100).toFixed(0)}% | 
                            ${result.processing_time.toFixed(1)}s
                        </span>
                    </div>
                    <div class="result-subject">${escapeHtml(result.subject)}</div>
                    <div class="result-from">From: ${escapeHtml(result.from_addr)}</div>
                    <div class="result-reason">Reason: ${escapeHtml(result.reason)}</div>
                </div>
            `).join('')}
        </div>
    `;
    
    container.innerHTML = html;
}

// ============================================================================
// Statistics
// ============================================================================

async function loadStats() {
    const days = parseInt(document.getElementById('stats-days').value);
    
    // Show loading
    document.getElementById('stats-loading').style.display = 'block';
    document.getElementById('stats-display').innerHTML = '';
    
    try {
        const response = await fetch(`${API_URL}/api/stats?days=${days}`);
        if (!response.ok) {
            throw new Error('Failed to load statistics');
        }
        
        const data = await response.json();
        displayStats(data);
        
    } catch (error) {
        document.getElementById('stats-display').innerHTML = `
            <div class="status status-error">
                Error loading statistics: ${error.message}
            </div>
        `;
    } finally {
        document.getElementById('stats-loading').style.display = 'none';
    }
}

function displayStats(data) {
    const container = document.getElementById('stats-display');
    
    if (data.error) {
        container.innerHTML = `
            <div class="status status-error">
                ${data.error}
            </div>
        `;
        return;
    }
    
    if (data.total_classifications === 0) {
        container.innerHTML = `
            <div class="status status-error">
                No classification data available for the selected time period.
                <br><br>
                The daemon needs to be running and processing emails to generate statistics.
            </div>
        `;
        return;
    }
    
    // Calculate percentages
    const categories = data.categories || {};
    const total = data.total_classifications;
    const ecommerce = categories.ecommerce || { count: 0, avg_confidence: 0 };
    const political = categories.political || { count: 0, avg_confidence: 0 };
    const none = categories.none || { count: 0, avg_confidence: 0 };
    
    const ecommercePercent = total > 0 ? (ecommerce.count / total * 100).toFixed(0) : 0;
    const politicalPercent = total > 0 ? (political.count / total * 100).toFixed(0) : 0;
    const nonePercent = total > 0 ? (none.count / total * 100).toFixed(0) : 0;
    
    const html = `
        <div class="stats-overview">
            <h3>Active Prompt: ${data.prompt_name}</h3>
            <p>Showing data for the last ${data.days} day(s)</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${total}</div>
                <div class="stat-label">Total Classifications</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${data.avg_confidence}</div>
                <div class="stat-label">Avg Confidence</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${data.avg_processing_time}s</div>
                <div class="stat-label">Avg Processing Time</div>
            </div>
        </div>
        
        <div class="category-breakdown">
            <h3>Category Breakdown</h3>
            
            <div class="category-row">
                <div class="category-label">🛒 Ecommerce</div>
                <div class="category-bar">
                    <div class="category-bar-fill bar-ecommerce" style="width: ${ecommercePercent}%">
                        ${ecommercePercent}%
                    </div>
                </div>
                <div class="category-count">
                    ${ecommerce.count} emails (conf: ${ecommerce.avg_confidence})
                </div>
            </div>
            
            <div class="category-row">
                <div class="category-label">🏛️ Political</div>
                <div class="category-bar">
                    <div class="category-bar-fill bar-political" style="width: ${politicalPercent}%">
                        ${politicalPercent}%
                    </div>
                </div>
                <div class="category-count">
                    ${political.count} emails (conf: ${political.avg_confidence})
                </div>
            </div>
            
            <div class="category-row">
                <div class="category-label">❓ None</div>
                <div class="category-bar">
                    <div class="category-bar-fill bar-none" style="width: ${nonePercent}%">
                        ${nonePercent}%
                    </div>
                </div>
                <div class="category-count">
                    ${none.count} emails (conf: ${none.avg_confidence})
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

// ============================================================================
// Utility Functions
// ============================================================================

function showStatus(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.innerHTML = `
        <div class="status status-${type}">
            ${message}
        </div>
    `;
    
    // Clear after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.innerHTML = '';
        }, 5000);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Initialization
// ============================================================================

// Load prompt on page load
document.addEventListener('DOMContentLoaded', () => {
    loadPrompt();
});

