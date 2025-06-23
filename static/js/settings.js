/**
 * Settings Page JavaScript
 * Handles all settings UI interactions and API calls
 */

// Global settings state
let currentSettings = {};
let systemStatus = {};
let isAdvancedMode = false;

// Loading state management
const loadingStates = new Map();

// Set button loading state
function setButtonLoading(button, isLoading, text = null) {
    if (!button) {
        console.warn('setButtonLoading: button is null or undefined');
        return;
    }
    
    // Create a unique identifier for the button
    const buttonId = button.id || button.getAttribute('data-button-id') || 
                    (button.onclick ? button.onclick.toString() : '') || 
                    button.outerHTML;
    
    if (isLoading) {
        // Store original state
        loadingStates.set(buttonId, {
            html: button.innerHTML,
            disabled: button.disabled
        });
        
        // Set loading state
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${text || 'Loading...'}`;
        console.log('Button set to loading state:', buttonId);
    } else {
        // Restore original state
        const originalState = loadingStates.get(buttonId);
        if (originalState) {
            button.innerHTML = originalState.html;
            button.disabled = originalState.disabled;
            loadingStates.delete(buttonId);
            console.log('Button restored from loading state:', buttonId);
        } else {
            console.warn('No original state found for button:', buttonId);
            // Fallback: just enable the button
            button.disabled = false;
        }
    }
}

// Initialize settings page
document.addEventListener('DOMContentLoaded', function() {
    console.log('Settings page loaded');
    
    // Load initial data
    loadSettings();
    loadSystemStatus();
    loadMonitoredUsers();
    
    // Setup auto-refresh for system status
    setInterval(loadSystemStatus, 30000); // Refresh every 30 seconds
    
    // Setup form change handlers
    setupFormHandlers();
});

// Load current settings from API
async function loadSettings() {
    try {
        showStatus('Loading settings...', 'info');
        
        const response = await fetch('/api/settings');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const settings = await response.json();
        currentSettings = settings;
        
        // Populate form fields
        populateSettingsForm(settings);
        
        hideStatus();
        
    } catch (error) {
        console.error('Error loading settings:', error);
        showStatus('Failed to load settings: ' + error.message, 'error');
    }
}

// Load system status from API
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/system/status/detailed');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const status = await response.json();
        systemStatus = status;
        
        // Update status display
        updateSystemStatusDisplay(status);
        
    } catch (error) {
        console.error('Error loading system status:', error);
        updateSystemStatusDisplay({
            system_health: 'error',
            components: {},
            storage: {},
            performance: {}
        });
    }
}

// Populate settings form with current values
function populateSettingsForm(settings) {
    // Twitter settings
    if (settings.monitored_users) {
        const monitoredUsersElement = document.getElementById('monitoredUsers');
        if (monitoredUsersElement) {
            monitoredUsersElement.value = settings.monitored_users.join(', ');
        }
    }
    
    if (settings.check_interval) {
        const checkIntervalElement = document.getElementById('checkInterval');
        if (checkIntervalElement) {
            checkIntervalElement.value = settings.check_interval;
        }
    }
    
    if (settings.historical_hours) {
        const historicalHoursElement = document.getElementById('historicalHours');
        if (historicalHoursElement) {
            historicalHoursElement.value = settings.historical_hours;
        }
    }
    
    // Set monitoring mode radio button
    if (settings.monitoring_mode) {
        const modeRadio = document.querySelector(`input[name="monitoringMode"][value="${settings.monitoring_mode}"]`);
        if (modeRadio) {
            modeRadio.checked = true;
        }
    }
    
    // Notification settings
    const notificationSettings = settings.notification_settings || {};
    const notificationsEnabledElement = document.getElementById('notificationsEnabled');
    if (notificationsEnabledElement) {
        notificationsEnabledElement.checked = notificationSettings.enabled || false;
    }
    
    if (notificationSettings.notify_all_tweets) {
        const notifyAllElement = document.getElementById('notifyAll');
        if (notifyAllElement) {
            notifyAllElement.checked = true;
        }
    } else {
        const notifyAiOnlyElement = document.getElementById('notifyAiOnly');
        if (notifyAiOnlyElement) {
            notifyAiOnlyElement.checked = true;
        }
    }
    
    if (notificationSettings.notification_delay !== undefined) {
        const notificationDelayElement = document.getElementById('notificationDelay');
        if (notificationDelayElement) {
            notificationDelayElement.value = notificationSettings.notification_delay;
        }
    }
    
    // AI settings
    const aiSettings = settings.ai_settings || {};
    const aiEnabledElement = document.getElementById('aiEnabled');
    if (aiEnabledElement) {
        aiEnabledElement.checked = aiSettings.enabled || false;
    }
    
    const autoProcessEnabledElement = document.getElementById('autoProcessEnabled');
    if (autoProcessEnabledElement) {
        autoProcessEnabledElement.checked = aiSettings.auto_process || false;
    }
    
    const aiBatchSizeElement = document.getElementById('aiBatchSize');
    if (aiBatchSizeElement) {
        aiBatchSizeElement.value = aiSettings.batch_size || 10;
    }
    
    // AI Prompt and Model settings
    const aiPromptElement = document.getElementById('aiPrompt');
    if (aiPromptElement) {
        aiPromptElement.value = aiSettings.prompt || 'Analyze this tweet and provide a brief summary of its key points and sentiment.';
    }
    
    const aiModelElement = document.getElementById('aiModel');
    if (aiModelElement) {
        aiModelElement.value = aiSettings.model || 'gpt-3.5-turbo';
    }
    
    const aiMaxTokensElement = document.getElementById('aiMaxTokens');
    if (aiMaxTokensElement) {
        aiMaxTokensElement.value = aiSettings.max_tokens || 150;
    }
}

// Update system status display
function updateSystemStatusDisplay(status) {
    // System health
    const systemHealthElement = document.getElementById('systemStatus');
    const systemUptimeElement = document.getElementById('systemUptime');
    
    if (systemHealthElement) {
        systemHealthElement.className = `status-indicator status-${status.system_health}`;
    }
    
    if (systemUptimeElement && status.uptime !== undefined) {
        const hours = Math.floor(status.uptime / 3600);
        const minutes = Math.floor((status.uptime % 3600) / 60);
        systemUptimeElement.textContent = `Uptime: ${hours}h ${minutes}m`;
    }
    
    // Scheduler status
    const schedulerStatusElement = document.getElementById('schedulerStatus');
    const schedulerInfoElement = document.getElementById('schedulerInfo');
    
    if (status.components && status.components.scheduler) {
        const scheduler = status.components.scheduler;
        if (schedulerStatusElement) {
            schedulerStatusElement.className = `status-indicator status-${scheduler.status === 'running' ? 'healthy' : 'warning'}`;
        }
        if (schedulerInfoElement) {
            schedulerInfoElement.textContent = `${scheduler.status} - ${scheduler.monitored_users ? scheduler.monitored_users.length : 0} users`;
        }
    }
    
    // API status
    const apiStatusElement = document.getElementById('apiStatus');
    const apiInfoElement = document.getElementById('apiInfo');
    
    if (status.components) {
        const apiCount = [
            status.components.twitter_api?.status === 'configured',
            status.components.openai_api?.status === 'configured',
            status.components.telegram?.status === 'configured'
        ].filter(Boolean).length;
        
        if (apiStatusElement) {
            apiStatusElement.className = `status-indicator status-${apiCount === 3 ? 'healthy' : apiCount > 0 ? 'warning' : 'error'}`;
        }
        if (apiInfoElement) {
            apiInfoElement.textContent = `${apiCount}/3 configured`;
        }
    }
    
    // Storage status
    const storageStatusElement = document.getElementById('storageStatus');
    const storageInfoElement = document.getElementById('storageInfo');
    
    if (status.storage) {
        if (storageStatusElement) {
            storageStatusElement.className = 'status-indicator status-healthy';
        }
        if (storageInfoElement) {
            storageInfoElement.textContent = `${status.storage.database_size || 0} MB DB`;
        }
    }
    
    // Update database stats
    updateElement('databaseSize', `${status.storage?.database_size || 0} MB`);
    updateElement('mediaFilesCount', status.storage?.media_files_count || 0);
    
    // Update performance stats
    updateElement('avgProcessingTime', `${status.performance?.avg_processing_time || 0}s`);
    updateElement('successRate', `${status.performance?.success_rate || 0}%`);
    
    // Update API status in modal
    if (status.components) {
        updateElement('twitterApiStatus', status.components.twitter_api?.status || 'unknown', 'badge');
        updateElement('openaiApiStatus', status.components.openai_api?.status || 'unknown', 'badge');
        updateElement('telegramApiStatus', status.components.telegram?.status || 'unknown', 'badge');
    }
}

// Setup form change handlers
function setupFormHandlers() {
    // Auto-save on significant changes
    const significantFields = ['notificationsEnabled', 'aiEnabled', 'schedulerEnabled'];
    
    significantFields.forEach(fieldId => {
        const element = document.getElementById(fieldId);
        if (element) {
            element.addEventListener('change', function() {
                saveSettings();
            });
        }
    });
    
    // Real-time validation for numeric fields
    const numericFields = [
        { id: 'checkInterval', name: 'Polling Interval' },
        { id: 'notificationDelay', name: 'Notification Delay' },
        { id: 'aiBatchSize', name: 'Batch Size' },
        { id: 'aiMaxTokens', name: 'Max Tokens' },
        { id: 'historicalHours', name: 'Historical Period' }
    ];
    
    numericFields.forEach(field => {
        const element = document.getElementById(field.id);
        if (element) {
            // Add label if missing
            if (!element.labels || element.labels.length === 0) {
                element.setAttribute('aria-label', field.name);
            }
            
            // Real-time validation on input
            element.addEventListener('input', function() {
                validateNumericField(this, false); // Don't show error message on input
            });
            
            // Full validation on blur
            element.addEventListener('blur', function() {
                validateNumericField(this, true);
            });
        }
    });
    
    // Real-time validation for URL input
    const urlInput = document.getElementById('newUserInput');
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            validateUrlInput(this);
        });
    }
    
    // Real-time validation for AI prompt
    const promptTextarea = document.getElementById('aiPrompt');
    if (promptTextarea) {
        promptTextarea.addEventListener('input', function() {
            validatePrompt(this);
        });
        
        // Initialize character counter
        validatePrompt(promptTextarea);
    }
    
    // Add validation state to all form controls on load
    document.querySelectorAll('.form-control, .form-select').forEach(element => {
        element.addEventListener('focus', function() {
            this.classList.add('focus');
        });
        
        element.addEventListener('blur', function() {
            this.classList.remove('focus');
        });
    });
}

// Validate numeric field with real-time feedback
function validateNumericField(field, showError = true) {
    const value = parseInt(field.value);
    const min = parseInt(field.min);
    const max = parseInt(field.max);
    const fieldName = field.labels?.[0]?.textContent || field.placeholder || 'Field';
    
    // Remove existing validation feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    if (isNaN(value) || value < min || value > max) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        
        // Add validation feedback
        if (showError) {
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = isNaN(value) 
                ? `Please enter a valid number`
                : `Must be between ${min} and ${max}`;
            field.parentNode.appendChild(feedback);
        }
        
        return false;
    } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        return true;
    }
}

// Validate URL input
function validateUrlInput(field) {
    const value = field.value.trim();
    
    // Remove existing validation feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    if (!value) {
        field.classList.remove('is-invalid', 'is-valid');
        return true; // Empty is okay
    }
    
    // Check if it's a valid Twitter username or URL
    const usernameRegex = /^[A-Za-z0-9_]{1,15}$/;
    const urlRegex = /^https?:\/\/(www\.)?(twitter\.com|x\.com)\/[A-Za-z0-9_]{1,15}\/?$/;
    
    if (usernameRegex.test(value) || urlRegex.test(value)) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        
        const feedback = document.createElement('div');
        feedback.className = 'valid-feedback';
        feedback.textContent = '✓ Valid format';
        field.parentNode.appendChild(feedback);
        
        return true;
    } else {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = 'Enter a username or Twitter/X.com URL';
        field.parentNode.appendChild(feedback);
        
        return false;
    }
}

// Validate prompt textarea
function validatePrompt(field) {
    const value = field.value.trim();
    const minLength = 10;
    const maxLength = 1000;
    
    // Remove existing validation feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    const charCount = document.getElementById('promptCharCount') || createCharCounter(field);
    charCount.textContent = `${value.length}/${maxLength} characters`;
    
    if (value.length < minLength) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        charCount.classList.add('text-danger');
        charCount.classList.remove('text-success', 'text-muted');
        
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = `Prompt must be at least ${minLength} characters`;
        field.parentNode.appendChild(feedback);
        
        return false;
    } else if (value.length > maxLength) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        charCount.classList.add('text-danger');
        charCount.classList.remove('text-success', 'text-muted');
        
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = `Prompt must not exceed ${maxLength} characters`;
        field.parentNode.appendChild(feedback);
        
        return false;
    } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        charCount.classList.add('text-success');
        charCount.classList.remove('text-danger', 'text-muted');
        
        return true;
    }
}

// Create character counter for textarea
function createCharCounter(field) {
    const counter = document.createElement('small');
    counter.id = 'promptCharCount';
    counter.className = 'form-text text-muted';
    field.parentNode.appendChild(counter);
    return counter;
}

// Save all settings
async function saveAllSettings(event) {
    await saveSettings(event);
}

// Save settings to API
async function saveSettings(event) {
    const button = event ? event.target.closest('button') : null;
    if (button) {
        setButtonLoading(button, true, 'Saving...');
    }
    
    try {
        // Collect form data
        const settings = {
            twitter_settings: {
                check_interval: parseInt(document.getElementById('checkInterval').value),
                monitoring_mode: document.querySelector('input[name="monitoringMode"]:checked').value,
                historical_hours: parseInt(document.getElementById('historicalHours').value)
            },
            notification_settings: {
                enabled: document.getElementById('notificationsEnabled').checked,
                notify_all_tweets: document.getElementById('notifyAll').checked,
                notify_ai_processed_only: document.getElementById('notifyAiOnly').checked,
                notification_delay: parseInt(document.getElementById('notificationDelay').value)
            },
            ai_settings: {
                enabled: document.getElementById('aiEnabled').checked,
                auto_process: document.getElementById('autoProcessEnabled').checked,
                batch_size: parseInt(document.getElementById('aiBatchSize').value),
                model: document.getElementById('aiModel').value,
                max_tokens: parseInt(document.getElementById('aiMaxTokens').value),
                prompt: document.getElementById('aiPrompt').value
            }
        };
        
        showStatus('Saving settings...', 'info');
        
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showStatus(`Settings saved: ${result.message}`, 'success');
            // Refresh system status to reflect changes
            setTimeout(loadSystemStatus, 1000);
        } else {
            throw new Error(result.error || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Error saving settings:', error);
        showStatus('Failed to save settings: ' + error.message, 'error', 10000);
    } finally {
        if (button) {
            setButtonLoading(button, false);
        }
    }
}

// Reset settings to defaults
function resetSettings() {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
        // Set default values
        const defaults = {
            check_interval: 60,
            historical_hours: 2,
            monitoring_mode: 'hybrid',
            notification_settings: {
                enabled: false,
                notify_all_tweets: true,
                notify_ai_processed_only: false,
                notification_delay: 5
            },
            ai_settings: {
                enabled: false,
                auto_process: false,
                batch_size: 10,
                model: 'gpt-4o',
                max_tokens: 150,
                prompt: 'Analyze this Persian tweet and provide:\n1. English translation\n2. Key topics and sentiment\n3. Any notable context or references'
            }
        };
        
        // Populate form with defaults
        populateSettingsForm(defaults);
        showStatus('Settings reset to defaults. Click "Save All" to apply.', 'info');
    }
}

// Test notification
async function testNotification(event) {
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Sending...');
    
    try {
        const response = await fetch('/api/test/notification', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('Test notification sent successfully! Check your Telegram.', 'success', 10000);
        } else {
            throw new Error('Failed to send test notification');
        }
        
    } catch (error) {
        console.error('Error sending test notification:', error);
        showStatus('Failed to send test notification: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Pause notifications
async function pauseNotifications(event) {
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Pausing...');
    
    try {
        const response = await fetch('/api/notifications/pause', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('Notifications paused', 'info');
            document.getElementById('notificationsEnabled').checked = false;
            loadSystemStatus();
        } else {
            throw new Error('Failed to pause notifications');
        }
        
    } catch (error) {
        console.error('Error pausing notifications:', error);
        showStatus('Failed to pause notifications: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Resume notifications
async function resumeNotifications(event) {
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Resuming...');
    
    try {
        const response = await fetch('/api/notifications/resume', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('Notifications resumed', 'success');
            document.getElementById('notificationsEnabled').checked = true;
            loadSystemStatus();
        } else {
            throw new Error('Failed to resume notifications');
        }
        
    } catch (error) {
        console.error('Error resuming notifications:', error);
        showStatus('Failed to resume notifications: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Force AI processing
async function forceAiProcessing(event) {
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Processing...');
    
    try {
        showStatus('Starting AI processing...', 'info');
        
        const response = await fetch('/api/ai/force', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('AI processing started', 'success');
        } else {
            throw new Error('Failed to start AI processing');
        }
        
    } catch (error) {
        console.error('Error starting AI processing:', error);
        showStatus('Failed to start AI processing: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// View AI stats
function viewAiStats() {
    // Redirect to main dashboard with AI filter
    window.location.href = '/?filter=ai';
}

// Force poll now
async function forcePoll(event) {
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Checking...');
    
    try {
        showStatus('Starting manual poll...', 'info');
        
        const response = await fetch('/api/poll/force', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('Manual poll started', 'success');
        } else {
            throw new Error('Failed to start manual poll');
        }
        
    } catch (error) {
        console.error('Error starting manual poll:', error);
        showStatus('Failed to start manual poll: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Restart scheduler
async function restartScheduler(event) {
    if (!confirm('Are you sure you want to restart the scheduler?')) {
        return;
    }
    
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Restarting...');
    
    try {
        showStatus('Restarting scheduler...', 'info');
        
        const response = await fetch('/api/system/restart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ component: 'scheduler' })
        });
        
        if (response.ok) {
            const result = await response.json();
            showStatus(result.message, 'success');
            setTimeout(loadSystemStatus, 2000);
        } else {
            throw new Error('Failed to restart scheduler');
        }
        
    } catch (error) {
        console.error('Error restarting scheduler:', error);
        showStatus('Failed to restart scheduler: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Clear cache
async function clearCache(event) {
    if (!confirm('Are you sure you want to clear the cache?')) {
        return;
    }
    
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Clearing...');
    
    try {
        showStatus('Clearing cache...', 'info');
        
        const response = await fetch('/api/cache/clear', {
            method: 'POST'
        });
        
        if (response.ok) {
            showStatus('Cache cleared', 'success');
        } else {
            throw new Error('Failed to clear cache');
        }
        
    } catch (error) {
        console.error('Error clearing cache:', error);
        showStatus('Failed to clear cache: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Refresh API status
function refreshApiStatus() {
    loadSystemStatus();
}

// Utility functions
function updateElement(id, value, className = '') {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
        if (className) {
            element.className = `${className} bg-secondary`;
        }
    }
}

function showStatus(message, type, duration = null) {
    // Remove existing status alerts of the same type
    const existingAlerts = document.querySelectorAll(`.alert.status-alert.alert-${type}`);
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alertClass = {
        'info': 'alert-info',
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning'
    }[type] || 'alert-info';
    
    const iconClass = {
        'info': 'bi-info-circle',
        'success': 'bi-check-circle',
        'error': 'bi-exclamation-triangle',
        'warning': 'bi-exclamation-circle'
    }[type] || 'bi-info-circle';
    
    const alert = document.createElement('div');
    alert.className = `alert ${alertClass} alert-dismissible fade show status-alert alert-${type}`;
    alert.innerHTML = `
        <i class="bi ${iconClass} me-2"></i>
        <span>${message}</span>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at the top of the content
    const content = document.querySelector('.container-fluid');
    if (content) {
        content.insertBefore(alert, content.firstChild);
    }
    
    // Auto-dismiss based on type or duration
    const dismissTime = duration || (type === 'error' ? 15000 : 8000);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }
    }, dismissTime);
}

function hideStatus() {
    const statusAlerts = document.querySelectorAll('.alert.status-alert');
    statusAlerts.forEach(alert => {
        if (alert.classList.contains('alert-info')) {
            alert.remove();
        }
    });
}

// User Management Functions

// Load monitored users
async function loadMonitoredUsers() {
    try {
        const response = await fetch('/api/users');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        displayMonitoredUsers(data.users);
        
    } catch (error) {
        console.error('Error loading monitored users:', error);
        showStatus('Failed to load monitored users: ' + error.message, 'error');
    }
}

// Display monitored users in the UI
function displayMonitoredUsers(users) {
    const container = document.getElementById('monitoredUsersList');
    if (!container) return;
    
    if (users.length === 0) {
        container.innerHTML = `
            <div class="col-12">
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i> No users currently being monitored. Add some users above to get started!
                </div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = users.map(user => `
        <div class="col-md-6 col-lg-4 mb-3">
            <div class="card h-100">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-twitter text-primary"></i> @${user.username}
                        </h6>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeUser('${user.username}', event)" title="Remove user">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                    <div class="small text-muted">
                        <div class="d-flex justify-content-between">
                            <span>Tweets:</span>
                            <span class="badge bg-primary">${user.tweet_count}</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span>AI Processed:</span>
                            <span class="badge bg-success">${user.ai_processed}</span>
                        </div>
                        ${user.last_tweet ? `
                            <div class="mt-1">
                                <small>Last: ${new Date(user.last_tweet).toLocaleDateString()}</small>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// Add new user
async function addNewUser(event) {
    console.log('addNewUser called with event:', event);
    
    const button = event ? event.target.closest('button') : null;
    console.log('Button found:', button);
    
    if (button) {
        setButtonLoading(button, true, 'Adding...');
    }
    
    const input = document.getElementById('newUserInput');
    if (!input) {
        console.error('newUserInput element not found');
        return;
    }
    
    const userInput = input.value.trim();
    console.log('User input:', userInput);
    
    if (!userInput) {
        showStatus('Please enter a Twitter username or URL', 'warning');
        if (button) {
            setButtonLoading(button, false);
        }
        return;
    }
    
    try {
        showStatus('Adding user...', 'info');
        console.log('Making API request to add user:', userInput);
        
        const response = await fetch('/api/users/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: userInput
            })
        });
        
        console.log('API response status:', response.status);
        const result = await response.json();
        console.log('API response result:', result);
        
        if (response.ok && result.success) {
            showStatus(result.message, 'success');
            input.value = ''; // Clear input
            loadMonitoredUsers(); // Refresh list
            
            // Notify dashboard to update if it's open in another tab/window
            notifyDashboardUpdate();
        } else {
            showStatus(result.error || 'Failed to add user', 'error', 10000);
        }
        
    } catch (error) {
        console.error('Error adding user:', error);
        showStatus('Failed to add user: ' + error.message, 'error', 10000);
    } finally {
        console.log('addNewUser finally block - restoring button');
        if (button) {
            setButtonLoading(button, false);
        }
    }
}

// Remove user
async function removeUser(username, event) {
    if (!confirm(`Are you sure you want to stop monitoring @${username}?`)) {
        return;
    }
    
    const button = event ? event.target.closest('button') : null;
    if (button) {
        setButtonLoading(button, true, 'Removing...');
    }
    
    try {
        showStatus('Removing user...', 'info');
        
        const response = await fetch('/api/users/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showStatus(result.message, 'success');
            loadMonitoredUsers(); // Refresh list
            
            // Notify dashboard to update if it's open in another tab/window
            notifyDashboardUpdate();
        } else {
            showStatus(result.error || 'Failed to remove user', 'error', 10000);
        }
        
    } catch (error) {
        console.error('Error removing user:', error);
        showStatus('Failed to remove user: ' + error.message, 'error', 10000);
    } finally {
        if (button) {
            setButtonLoading(button, false);
        }
    }
}

// Scrape historical tweets
async function scrapeHistoricalTweets(event) {
    const hours = document.getElementById('historicalHours')?.value || 2;
    
    if (!confirm(`This will scrape tweets from the last ${hours} hours for all monitored users. Continue?`)) {
        return;
    }
    
    const button = event.target.closest('button');
    setButtonLoading(button, true, 'Scraping...');
    
    try {
        showStatus('Starting historical scrape...', 'info');
        
        const response = await fetch('/api/historical/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                hours: parseInt(hours)
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showStatus(result.message, 'success');
            // Refresh users list to show updated counts
            setTimeout(() => {
                loadMonitoredUsers();
            }, 2000);
        } else {
            showStatus(result.error || 'Failed to start historical scrape', 'error', 10000);
        }
        
    } catch (error) {
        console.error('Error starting historical scrape:', error);
        showStatus('Failed to start historical scrape: ' + error.message, 'error', 10000);
    } finally {
        setButtonLoading(button, false);
    }
}

// Handle Enter key in new user input
document.addEventListener('DOMContentLoaded', function() {
    const newUserInput = document.getElementById('newUserInput');
    if (newUserInput) {
        newUserInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                addNewUser(e);
            }
        });
    }
});

// Notify dashboard to update when users are added/removed
function notifyDashboardUpdate() {
    // Use localStorage to communicate between tabs/windows
    const updateEvent = {
        type: 'monitored_users_changed',
        timestamp: Date.now()
    };
    
    localStorage.setItem('dashboard_update', JSON.stringify(updateEvent));
    
    // Remove the item after a longer delay to ensure all tabs can read it
    setTimeout(() => {
        localStorage.removeItem('dashboard_update');
    }, 500);
    
    // Also dispatch a custom event for same-tab communication
    window.dispatchEvent(new CustomEvent('monitoredUsersChanged', {
        detail: updateEvent
    }));
}

// Toggle between basic and advanced mode
function toggleAdvancedMode() {
    isAdvancedMode = !isAdvancedMode;
    const advancedSettings = document.querySelectorAll('.advanced-setting');
    const modeText = document.getElementById('modeText');
    const toggleBtn = document.getElementById('toggleModeBtn');
    
    if (isAdvancedMode) {
        // Show advanced settings
        advancedSettings.forEach(element => {
            element.style.display = '';
            element.classList.add('fade-in');
        });
        modeText.textContent = 'Hide Advanced';
        toggleBtn.classList.remove('btn-outline-info');
        toggleBtn.classList.add('btn-info');
        
        // Save preference
        localStorage.setItem('settingsAdvancedMode', 'true');
    } else {
        // Hide advanced settings
        advancedSettings.forEach(element => {
            element.style.display = 'none';
            element.classList.remove('fade-in');
        });
        modeText.textContent = 'Show Advanced';
        toggleBtn.classList.remove('btn-info');
        toggleBtn.classList.add('btn-outline-info');
        
        // Save preference
        localStorage.setItem('settingsAdvancedMode', 'false');
    }
}

// Restore advanced mode preference on load
document.addEventListener('DOMContentLoaded', function() {
    const savedMode = localStorage.getItem('settingsAdvancedMode');
    if (savedMode === 'true') {
        toggleAdvancedMode();
    }
});