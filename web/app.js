// Mailtagger Prompt Manager - Frontend JavaScript
// Simple vanilla JS - no frameworks

// Configuration
// Use same origin as the page (works with nginx proxy or direct access)
const API_URL = window.location.origin;

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
    
    // Find and activate the corresponding button
    const clickedButton = event && event.target ? event.target : 
        document.querySelector(`[onclick="showTab('${tabName}')"]`);
    if (clickedButton) {
        clickedButton.classList.add('active');
    }
    
    // Load data for the tab
    if (tabName === 'edit') {
        loadPrompt();
    } else if (tabName === 'stats') {
        loadStats();
    } else if (tabName === 'gmail') {
        checkGmailStatus();
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
// Gmail Authorization
// ============================================================================

async function checkGmailStatus() {
    const statusContainer = document.getElementById('gmail-auth-status');
    const loadingDiv = document.getElementById('gmail-status-loading');
    const authorizeBtn = document.getElementById('authorize-button');
    const revokeBtn = document.getElementById('revoke-button');
    
    loadingDiv.style.display = 'block';
    statusContainer.innerHTML = '';
    
    try {
        const response = await fetch(`${API_URL}/api/gmail/status`);
        if (!response.ok) {
            throw new Error('Failed to check Gmail status');
        }
        
        const status = await response.json();
        
        // Display status
        let html = '<div class="gmail-status">';
        
        if (status.authorized && status.token_valid) {
            html += `
                <div class="status status-success">
                    <h3>✅ Gmail Authorized</h3>
                    ${status.email ? `<p><strong>Account:</strong> ${status.email}</p>` : ''}
                    <p>${status.message}</p>
                </div>
            `;
            authorizeBtn.style.display = 'none';
            revokeBtn.style.display = 'inline-block';
        } else if (!status.credentials_exists) {
            html += `
                <div class="status status-error">
                    <h3>❌ Credentials Not Found</h3>
                    <p>${status.message}</p>
                    <p><strong>Action needed:</strong> Please upload credentials.json to your server.</p>
                    <p>See setup instructions below.</p>
                </div>
            `;
            authorizeBtn.style.display = 'none';
            revokeBtn.style.display = 'none';
        } else {
            html += `
                <div class="status status-warning">
                    <h3>⚠️ Not Authorized</h3>
                    <p>${status.message}</p>
                    <p><strong>Action needed:</strong> Click "Authorize Gmail" below.</p>
                </div>
            `;
            authorizeBtn.style.display = 'inline-block';
            revokeBtn.style.display = 'none';
        }
        
        html += '</div>';
        statusContainer.innerHTML = html;
        
    } catch (error) {
        statusContainer.innerHTML = `
            <div class="status status-error">
                Error checking Gmail status: ${error.message}
            </div>
        `;
        authorizeBtn.style.display = 'none';
        revokeBtn.style.display = 'none';
    } finally {
        loadingDiv.style.display = 'none';
    }
}

async function authorizeGmail() {
    const actionStatus = document.getElementById('gmail-action-status');
    
    actionStatus.innerHTML = `
        <div class="status status-info">
            Starting authorization flow...
        </div>
    `;
    
    try {
        const response = await fetch(`${API_URL}/api/oauth/start`);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start OAuth flow');
        }
        
        const data = await response.json();
        
        // Redirect to Google OAuth page
        actionStatus.innerHTML = `
            <div class="status status-success">
                Redirecting to Google for authorization...
            </div>
        `;
        
        // Small delay so user sees the message
        setTimeout(() => {
            window.location.href = data.auth_url;
        }, 500);
        
    } catch (error) {
        actionStatus.innerHTML = `
            <div class="status status-error">
                Error starting authorization: ${error.message}
                <br><br>
                Make sure credentials.json exists and is properly configured.
            </div>
        `;
    }
}

async function revokeGmail() {
    if (!confirm('Are you sure you want to revoke Gmail authorization?')) {
        return;
    }
    
    const actionStatus = document.getElementById('gmail-action-status');
    
    try {
        const response = await fetch(`${API_URL}/api/gmail/revoke`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            actionStatus.innerHTML = `
                <div class="status status-success">
                    ${data.message}
                </div>
            `;
            // Refresh status
            setTimeout(checkGmailStatus, 1000);
        } else {
            actionStatus.innerHTML = `
                <div class="status status-error">
                    ${data.message}
                </div>
            `;
        }
        
    } catch (error) {
        actionStatus.innerHTML = `
            <div class="status status-error">
                Error revoking authorization: ${error.message}
            </div>
        `;
    }
}

// ============================================================================
// Initialization
// ============================================================================

// Load prompt on page load
document.addEventListener('DOMContentLoaded', () => {
    loadPrompt();
    
    // Check for OAuth callback result
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('oauth_success')) {
        // Show success message and switch to Gmail tab
        showTab('gmail');
        document.getElementById('gmail-action-status').innerHTML = `
            <div class="status status-success">
                ✅ Gmail authorization successful! You can now test emails.
            </div>
        `;
        checkGmailStatus();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.has('oauth_error')) {
        // Show error message
        const error = urlParams.get('oauth_error');
        showTab('gmail');
        document.getElementById('gmail-action-status').innerHTML = `
            <div class="status status-error">
                ❌ Gmail authorization failed: ${error}
                <br>Please try again or check your credentials.json file.
            </div>
        `;
        checkGmailStatus();
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

