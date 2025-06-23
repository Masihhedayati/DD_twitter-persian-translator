// Twitter Monitor - Frontend JavaScript

// Global variables
let currentFilter = 'all';
let searchQuery = '';
let lastUpdateTime = null;
let selectedUsername = '';
let autoRefreshInterval = null;
let isRealTimeMode = true;
let currentMonitoredUsers = []; // Track current monitored users
let lastUserListHash = ''; // Track changes in user list

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// Initialize the application
function initializeApp() {
    console.log('Twitter Monitor - Frontend Initialized');
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize components
    initializeComponents();
    
    // Load initial data
    loadMonitoredUsers();
    loadTweets();
    loadStats();
    
    // Start auto-refresh
    startAutoRefresh();
}

// Setup event listeners
function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', handleRefresh);
    }
    
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleSearch();
            }
        });
    }
    
    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    }
    
    // Filter buttons
    const filterButtons = document.querySelectorAll('[data-filter]');
    filterButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            handleFilter(this.dataset.filter);
        });
    });
    
    // Load more button
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', handleLoadMore);
    }
    
    // Listen for cross-tab updates when users are added/removed
    window.addEventListener('storage', function(e) {
        if (e.key === 'dashboard_update') {
            try {
                const updateEvent = JSON.parse(e.newValue);
                if (updateEvent.type === 'monitored_users_changed') {
                    console.log('Detected user list change from another tab, updating dashboard...');
                    handleMonitoredUsersChange();
                }
            } catch (error) {
                console.error('Error parsing dashboard update event:', error);
            }
        }
    });
    
    // Listen for same-tab updates when users are added/removed
    window.addEventListener('monitoredUsersChanged', function(e) {
        console.log('Detected user list change in same tab, updating dashboard...');
        handleMonitoredUsersChange();
    });
}

// Initialize components
function initializeComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize modals
    const modalTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="modal"]'));
    modalTriggerList.map(function (modalTriggerEl) {
        return new bootstrap.Modal(modalTriggerEl);
    });
}

// Handle refresh button click
function handleRefresh() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        // Add loading state
        const originalContent = refreshBtn.innerHTML;
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refreshing...';
        refreshBtn.disabled = true;
        
        // Load tweets
        loadTweets().finally(() => {
            // Restore button state
            refreshBtn.innerHTML = originalContent;
            refreshBtn.disabled = false;
        });
    }
}

// Handle search
function handleSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchQuery = searchInput.value.trim();
        loadTweets(true); // Reset feed for new search
        updateActiveFilters(); // Update filter display
    }
}

// Handle real-time search while typing
function handleLiveSearch() {
    clearTimeout(window.searchTimeout);
    window.searchTimeout = setTimeout(() => {
        handleSearch();
    }, 300); // Debounce search for 300ms
}

// Handle filter change
function handleFilter(filter) {
    currentFilter = filter;
    
    // Update active filter button
    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(button => {
        button.classList.remove('active');
    });
    // Add active class to appropriate button
    const activeButtonMap = {
        'all': 0,
        'images': 1,
        'videos': 2,
        'ai': 3
    };
    const activeIndex = activeButtonMap[filter] || 0;
    const activeButton = filterButtons[activeIndex];
    if (activeButton) {
        activeButton.classList.add('active');
    }
    
    // Reload tweets with filter
    loadTweets(true);
    
    // Update active filters display
    updateActiveFilters();
}

// Handle load more tweets
function handleLoadMore() {
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Loading...';
        loadMoreBtn.disabled = true;
        
        // Load more tweets (implement pagination)
        setTimeout(() => {
            loadMoreBtn.innerHTML = '<i class="bi bi-arrow-down-circle"></i> Load More';
            loadMoreBtn.disabled = false;
        }, 1000);
    }
}

// Load tweets from API
async function loadTweets(reset = false) {
    try {
        const params = new URLSearchParams();
        params.append('limit', '50');
        
        if (selectedUsername) {
            params.append('username', selectedUsername);
        }
        
        if (searchQuery) {
            params.append('q', searchQuery);
        }
        
        if (currentFilter !== 'all') {
            params.append('filter', currentFilter);
        }
        
        // For real-time updates, use lastUpdateTime
        if (isRealTimeMode && lastUpdateTime && !reset) {
            params.append('since', lastUpdateTime.toISOString());
        }
        
        const response = await fetch(`/api/tweets?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Filter tweets to only show from currently monitored users
        const filteredTweets = filterTweetsByMonitoredUsers(data.tweets || []);
        const filteredData = {
            ...data,
            tweets: filteredTweets,
            count: filteredTweets.length
        };
        
        // Update lastUpdateTime for real-time updates
        if (filteredTweets.length > 0) {
            lastUpdateTime = new Date();
        }
        
        // Update UI with tweets (reset if this is a new search/filter)
        updateTweetFeed(filteredData, reset);
        
        // Update stats
        updateStats(filteredData);
        
    } catch (error) {
        console.error('Error loading tweets:', error);
        showError('Failed to load tweets. Please try again.');
    }
}

// Update tweet feed display
function updateTweetFeed(data, resetFeed = true) {
    const feedContainer = document.getElementById('tweetFeed');
    if (!feedContainer) return;
    
    if (data.count === 0 && resetFeed) {
        feedContainer.innerHTML = `
            <div class="text-center py-5">
                <i class="bi bi-twitter text-muted" style="font-size: 3rem;"></i>
                <h4 class="mt-3 text-muted">No tweets found</h4>
                <p class="text-muted">
                    ${getNoTweetsMessage()}
                </p>
            </div>
        `;
        return;
    }
    
    // Render tweets
    let tweetsHTML = '';
    data.tweets.forEach(tweet => {
        tweetsHTML += renderTweet(tweet);
    });
    
    if (resetFeed) {
        feedContainer.innerHTML = tweetsHTML;
    } else {
        // For real-time updates, prepend new tweets
        feedContainer.insertAdjacentHTML('afterbegin', tweetsHTML);
        
        // Show notification for new tweets
        if (data.tweets.length > 0) {
            showNewTweetsNotification(data.tweets.length);
        }
    }
    
    // Setup media lightbox
    setupMediaLightbox();
}

// Get appropriate no tweets message based on current filters
function getNoTweetsMessage() {
    if (!currentMonitoredUsers || currentMonitoredUsers.length === 0) {
        return 'No users are currently being monitored. Go to Settings to add Twitter accounts to monitor.';
    } else if (searchQuery) {
        return `No tweets found for "${searchQuery}"`;
    } else if (currentFilter !== 'all') {
        return `No ${currentFilter} tweets found`;
    } else if (selectedUsername) {
        return `No tweets found for @${selectedUsername}`;
    } else {
        return 'Make sure your monitoring is running and check back soon for new tweets.';
    }
}

// Show notification for new tweets
function showNewTweetsNotification(count) {
    const notification = document.createElement('div');
    notification.className = 'alert alert-success alert-dismissible fade show new-tweets-notification';
    notification.innerHTML = `
        <i class="bi bi-check-circle-fill"></i>
        <strong>${count} new tweet${count > 1 ? 's' : ''} loaded!</strong>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at top of page
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertBefore(notification, container.firstChild);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }
}

// Render a single tweet
function renderTweet(tweet) {
    const timeAgo = formatTimeAgo(new Date(tweet.created_at));
    const mediaHTML = renderMedia(tweet.media || []);
    const aiAnalysisHTML = renderAIAnalysis(tweet.ai_result);
    const statusIndicators = renderStatusIndicators(tweet);
    
    return `
        <div class="card mb-3 tweet-card" data-tweet-id="${tweet.id}">
            <div class="card-body">
                <div class="d-flex align-items-start">
                    <img src="${tweet.author_avatar || '/static/images/default-avatar.png'}" 
                         class="rounded-circle me-3 tweet-avatar" width="50" height="50"
                         alt="${tweet.display_name || tweet.username}">
                    <div class="flex-grow-1">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div>
                                <h6 class="mb-0 tweet-display-name">${escapeHtml(tweet.display_name || tweet.username)}</h6>
                                <small class="text-muted tweet-username">@${escapeHtml(tweet.username)}</small>
                            </div>
                            <small class="text-muted tweet-timestamp">${timeAgo}</small>
                        </div>
                        
                        <p class="tweet-content">${formatTweetContent(tweet.content)}</p>
                        
                        ${mediaHTML}
                        ${aiAnalysisHTML}
                        
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="d-flex gap-3">
                                <small class="text-muted">
                                    <i class="bi bi-heart"></i> <span class="tweet-likes">${formatNumber(tweet.likes_count || 0)}</span>
                                </small>
                                <small class="text-muted">
                                    <i class="bi bi-arrow-repeat"></i> <span class="tweet-retweets">${formatNumber(tweet.retweets_count || 0)}</span>
                                </small>
                                <small class="text-muted">
                                    <i class="bi bi-chat"></i> <span class="tweet-replies">${formatNumber(tweet.replies_count || 0)}</span>
                                </small>
                            </div>
                            
                            <div class="tweet-status-indicators">
                                ${statusIndicators}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Render media for a tweet
function renderMedia(mediaItems) {
    if (!mediaItems || mediaItems.length === 0) return '';
    
    const gridClass = getMediaGridClass(mediaItems.length);
    let mediaHTML = `<div class="tweet-media mb-3"><div class="media-grid ${gridClass}">`;
    
    mediaItems.forEach(media => {
        mediaHTML += `
            <div class="media-item" data-media-url="${media.url}" data-media-type="${media.type}">
                ${renderMediaItem(media)}
            </div>
        `;
    });
    
    mediaHTML += '</div></div>';
    return mediaHTML;
}

// Render individual media item
function renderMediaItem(media) {
    switch (media.type) {
        case 'image':
            return `<img src="${media.url}" alt="Tweet image" loading="lazy">`;
        case 'video':
            return `
                <video controls preload="metadata">
                    <source src="${media.url}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <div class="media-overlay">
                    <i class="bi bi-play-fill"></i>
                </div>
            `;
        case 'gif':
            return `
                <img src="${media.url}" alt="GIF" loading="lazy">
                <div class="media-overlay">GIF</div>
            `;
        default:
            return `<div class="d-flex align-items-center justify-content-center h-100">
                <i class="bi bi-file-earmark text-muted"></i>
            </div>`;
    }
}

// Render AI analysis
function renderAIAnalysis(aiResult) {
    if (!aiResult) return '';
    
    // Detect if the text contains Persian/Arabic characters for RTL support
    const isPersian = containsPersianText(aiResult);
    const rtlClass = isPersian ? ' style="direction: rtl; text-align: right;"' : '';
    
    return `
        <div class="tweet-ai-analysis mb-3">
            <div class="alert alert-info">
                <i class="bi bi-robot"></i> <strong>AI Analysis:</strong>
                <p class="mb-0 mt-1"${rtlClass}>${escapeHtml(aiResult)}</p>
            </div>
        </div>
    `;
}

// Helper function to detect Persian/Arabic text
function containsPersianText(text) {
    // Persian/Arabic Unicode ranges
    const persianRegex = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
    return persianRegex.test(text);
}

// Render status indicators
function renderStatusIndicators(tweet) {
    let indicators = [];
    
    if (tweet.media_downloaded) {
        indicators.push('<span class="status-indicator downloaded">Downloaded</span>');
    }
    
    if (tweet.ai_processed) {
        indicators.push('<span class="status-indicator ai-processed">AI</span>');
    }
    
    if (tweet.telegram_sent) {
        indicators.push('<span class="status-indicator telegram-sent">Sent</span>');
    }
    
    return indicators.join(' ');
}

// Filter tweets to only include those from currently monitored users
function filterTweetsByMonitoredUsers(tweets) {
    // If no monitored users are loaded yet, show empty state instead of all tweets
    if (!currentMonitoredUsers || currentMonitoredUsers.length === 0) {
        console.log('No monitored users loaded - filtering out all tweets');
        return []; // Return empty array instead of all tweets
    }
    
    const monitoredUsernames = currentMonitoredUsers.map(u => u.username);
    const filteredTweets = tweets.filter(tweet => monitoredUsernames.includes(tweet.username));
    
    // Log filtering results for debugging
    if (tweets.length !== filteredTweets.length) {
        console.log(`Filtered out ${tweets.length - filteredTweets.length} tweets from non-monitored users`);
        console.log(`Monitored users: ${monitoredUsernames.join(', ')}`);
        console.log(`Remaining tweets: ${filteredTweets.length}`);
    }
    
    return filteredTweets;
}

// Update stats display
function updateStats(data) {
    // Update tweet count from current data
    if (data && data.count !== undefined) {
        updateStatCard('total-tweets', data.count);
    }
    
    // Fetch comprehensive stats from API
    fetchStatistics();
}

// Fetch statistics from API
async function fetchStatistics() {
    try {
        const response = await fetch('/api/statistics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const stats = await response.json();
        
        // Update stat cards with real data
        updateStatCard('total-tweets', stats.total_tweets || 0);
        updateStatCard('media-files', stats.media_files || 0);
        updateStatCard('ai-processed', stats.ai_processed || 0);
        updateStatCard('notifications', stats.notifications || 0);
        
    } catch (error) {
        console.error('Error fetching statistics:', error);
        // Don't show error to user for stats, just log it
    }
}

// Update individual stat card
function updateStatCard(cardId, value) {
    const card = document.querySelector(`[data-stat="${cardId}"]`);
    if (card) {
        card.textContent = formatNumber(value);
    }
}

// Utility functions
function formatTimeAgo(date) {
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    
    const hours = Math.floor(seconds / 3600);
    if (hours < 24) {
        // Show hours and remaining minutes for better granularity within 24 hours
        const remainingMinutes = minutes % 60;
        if (remainingMinutes > 0 && hours < 12) {
            return `${hours}h ${remainingMinutes}m ago`;
        }
        return `${hours}h ago`;
    }
    
    const days = Math.floor(seconds / 86400);
    if (days < 7) return `${days}d ago`;
    
    // For older tweets, show actual date
    return date.toLocaleDateString();
}

function formatNumber(num) {
    if (num < 1000) return num.toString();
    if (num < 1000000) return (num / 1000).toFixed(1) + 'K';
    return (num / 1000000).toFixed(1) + 'M';
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatTweetContent(content) {
    // Basic text formatting for tweets
    return escapeHtml(content)
        .replace(/\n/g, '<br>')
        .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
        .replace(/@(\w+)/g, '<a href="https://twitter.com/$1" target="_blank" rel="noopener">@$1</a>')
        .replace(/#(\w+)/g, '<a href="https://twitter.com/hashtag/$1" target="_blank" rel="noopener">#$1</a>');
}

function getMediaGridClass(count) {
    switch (count) {
        case 1: return 'single';
        case 2: return 'double';
        case 3: return 'triple';
        case 4: return 'quadruple';
        default: return 'single';
    }
}

function setupMediaLightbox() {
    const mediaItems = document.querySelectorAll('.media-item');
    mediaItems.forEach(item => {
        item.addEventListener('click', function() {
            const mediaUrl = this.dataset.mediaUrl;
            const mediaType = this.dataset.mediaType;
            openMediaLightbox(mediaUrl, mediaType);
        });
    });
}

function openMediaLightbox(url, type) {
    // Create and show media lightbox
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Media</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center">
                    ${type === 'image' ? 
                        `<img src="${url}" class="img-fluid" alt="Media">` :
                        `<video controls class="w-100"><source src="${url}" type="video/mp4"></video>`
                    }
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const modalInstance = new bootstrap.Modal(modal);
    modalInstance.show();
    
    // Remove modal from DOM when hidden
    modal.addEventListener('hidden.bs.modal', function() {
        document.body.removeChild(modal);
    });
}

function showError(message) {
    // Show error message using Bootstrap alert
    const alertContainer = document.querySelector('.container-fluid');
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.insertBefore(alert, alertContainer.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.classList.remove('show');
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.parentNode.removeChild(alert);
                }
            }, 150);
        }
    }, 5000);
}

function startAutoRefresh() {
    // Clear existing interval
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    // Start automatic refresh every 30 seconds if real-time is enabled
    if (isRealTimeMode) {
        autoRefreshInterval = setInterval(() => {
            if (document.visibilityState === 'visible') {
                // Check for user changes first
                loadMonitoredUsers();
                
                // Then load tweets (will be filtered by current monitored users)
                loadTweets(false); // Don't reset feed, just add new tweets
                
                // Update stats
                fetchStatistics();
            }
        }, 120000); // Increased to 2 minutes to reduce API calls
    }
}

// Toggle real-time mode
function toggleRealTime() {
    const toggle = document.getElementById('realTimeToggle');
    isRealTimeMode = toggle.checked;
    
    if (isRealTimeMode) {
        startAutoRefresh();
    } else {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }
}

// Handle username filter
function handleUsernameFilter(username) {
    selectedUsername = username;
    loadTweets(true); // Reset feed
    updateActiveFilters();
}

// Update active filters display
function updateActiveFilters() {
    const container = document.getElementById('activeFilters');
    const tagsContainer = document.getElementById('filterTags');
    
    if (!container || !tagsContainer) return;
    
    let tags = [];
    
    if (searchQuery) {
        tags.push({
            text: `Search: "${searchQuery}"`,
            type: 'search',
            onclick: 'clearSearch()'
        });
    }
    
    if (selectedUsername) {
        tags.push({
            text: `User: @${selectedUsername}`,
            type: 'username',
            onclick: 'clearUsernameFilter()'
        });
    }
    
    if (currentFilter !== 'all') {
        const filterLabels = {
            'images': '📷 Images',
            'videos': '🎥 Videos',
            'ai': '🤖 AI Processed'
        };
        tags.push({
            text: filterLabels[currentFilter] || currentFilter,
            type: 'filter',
            onclick: 'clearFilter()'
        });
    }
    
    if (tags.length > 0) {
        tagsContainer.innerHTML = tags.map(tag => 
            `<span class="badge bg-secondary me-1">
                ${tag.text}
                <button type="button" class="btn-close btn-close-white ms-1" style="font-size: 0.6em;" onclick="${tag.onclick}"></button>
            </span>`
        ).join('');
        container.style.display = 'block';
    } else {
        container.style.display = 'none';
    }
}

// Clear functions
function clearSearch() {
    searchQuery = '';
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.value = '';
    loadTweets(true);
    updateActiveFilters();
}

function clearUsernameFilter() {
    selectedUsername = '';
    const usernameFilter = document.getElementById('usernameFilter');
    if (usernameFilter) usernameFilter.value = '';
    loadTweets(true);
    updateActiveFilters();
}

function clearFilter() {
    currentFilter = 'all';
    // Update filter buttons
    document.querySelectorAll('.filter-btn').forEach((btn, index) => {
        btn.classList.toggle('active', index === 0);
    });
    loadTweets(true);
    updateActiveFilters();
}

// Load monitored users and update filter dropdown
async function loadMonitoredUsers() {
    try {
        const response = await fetch('/api/users');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const users = data.users || [];
        
        // Create hash to detect changes
        const userListHash = users.map(u => u.username).sort().join(',');
        
        // Update monitored users if changed
        if (userListHash !== lastUserListHash) {
            console.log('Monitored users changed, updating dashboard...');
            currentMonitoredUsers = users;
            lastUserListHash = userListHash;
            
            // Update filter dropdown
            updateUsernameFilter(users);
            
            // Refresh tweets to exclude removed users
            loadTweets(true); // Force refresh
        }
        
    } catch (error) {
        console.error('Error loading monitored users:', error);
    }
}

// Update username filter dropdown with current monitored users
function updateUsernameFilter(users) {
    const usernameFilter = document.getElementById('usernameFilter');
    if (!usernameFilter) return;
    
    // Store current selection
    const currentSelection = usernameFilter.value;
    
    // Clear existing options except "All Users"
    usernameFilter.innerHTML = '<option value="">All Users</option>';
    
    // Add options for each monitored user
    users.forEach(user => {
        const option = document.createElement('option');
        option.value = user.username;
        option.textContent = `@${user.username}`;
        usernameFilter.appendChild(option);
    });
    
    // Restore selection if user still exists
    if (currentSelection && users.some(u => u.username === currentSelection)) {
        usernameFilter.value = currentSelection;
    } else if (currentSelection && currentSelection !== '') {
        // User was removed, clear filter and refresh
        usernameFilter.value = '';
        selectedUsername = '';
        console.log(`User @${currentSelection} was removed, clearing filter`);
    }
}

// Handle monitored users change event
async function handleMonitoredUsersChange() {
    try {
        console.log('Handling monitored users change...');
        
        // Reload monitored users first
        await loadMonitoredUsers();
        
        // Force refresh tweets to reflect new user list
        await loadTweets(true); // Reset feed
        
        // Update stats
        await fetchStatistics();
        
        console.log('Dashboard updated after monitored users change');
    } catch (error) {
        console.error('Error handling monitored users change:', error);
    }
}

// Export functions for use in other scripts
window.TwitterMonitor = {
    loadTweets,
    formatTimeAgo,
    formatNumber,
    escapeHtml,
    toggleRealTime,
    handleUsernameFilter,
    clearSearch,
    clearUsernameFilter,
    clearFilter,
    handleMonitoredUsersChange
}; 