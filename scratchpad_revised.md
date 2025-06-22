# Twitter Monitoring & Notification System - Complete Engineering Plan

## Executive Summary
A practical, reliable system for monitoring Twitter accounts, downloading media, processing tweets with AI, and sending notifications. Focus on proven tools, simple architecture, and excellent user experience.

## Core Requirements (Unchanged)
- Monitor list of Twitter accounts for new tweets
- Download all media content (images, videos)
- Store data in structured database
- Process tweets through OpenAI API
- Send results to Telegram
- Simple web interface for viewing data

## Revised Technical Architecture

### Backend Stack
- **Language**: Python 3.11+ (mature ecosystem, excellent library support)
- **Web Framework**: Flask (simpler than FastAPI for this use case)
- **Task Queue**: Simple background threads with `schedule` library (no Redis/Celery overhead)
- **Database**: SQLite for simplicity (can migrate to PostgreSQL later if needed)
- **Media Storage**: Local filesystem with structured folders

### Key Libraries (All Well-Maintained)
- **Twitter API**: `tweepy` - Official Twitter API wrapper, handles rate limits automatically
- **Media Download**: `requests` with retry logic
- **Telegram**: `python-telegram-bot` - Official Telegram bot library
- **OpenAI**: `openai` - Official OpenAI Python library
- **Scheduling**: `schedule` - Dead simple Python job scheduling
- **Web UI**: `Flask` + `Jinja2` templates + `Bootstrap 5` (CDN)

## Detailed Project Phases

### Phase 0: Project Setup & Infrastructure (Days 1-2)

#### Task 0.1: Initialize Project Structure
**Deliverable**: Complete project skeleton with all directories
```bash
twitter-monitor/
├── app.py              # Main Flask application
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── .env.example       # Example environment variables
├── .gitignore         # Git ignore file
├── README.md          # Project documentation
├── /core/             # Core business logic
├── /templates/        # HTML templates
├── /static/           # CSS, JS, images
├── /media/            # Downloaded media storage
├── /logs/             # Application logs
└── /tests/            # Unit tests
```
**Success Criteria**: 
- All directories created
- Git repository initialized
- Virtual environment setup complete

#### Task 0.2: Setup Development Environment
**Deliverable**: Working development environment
**Steps**:
1. Create virtual environment
2. Install all dependencies
3. Setup pre-commit hooks for code quality
4. Configure IDE settings
**Success Criteria**: 
- `pip install -r requirements.txt` works
- Can run `python app.py` without errors

#### Task 0.3: Configure Environment Variables
**Deliverable**: Complete `.env` file with all required keys
```env
# Twitter API
TWITTER_API_KEY=xxx
TWITTER_API_SECRET=xxx
TWITTER_ACCESS_TOKEN=xxx
TWITTER_ACCESS_SECRET=xxx

# OpenAI
OPENAI_API_KEY=xxx
OPENAI_MODEL=gpt-3.5-turbo

# Telegram
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# App Settings
MONITORED_USERS=elonmusk,naval,paulg
CHECK_INTERVAL=60
MEDIA_STORAGE_PATH=./media
DATABASE_PATH=./tweets.db
```
**Success Criteria**: All API keys validated and working

### Phase 1: Database & Models (Days 3-4)

#### Task 1.1: Design Database Schema
**Deliverable**: SQLite database with optimized schema
```sql
-- Main tweets table
CREATE TABLE tweets (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    content TEXT NOT NULL,
    tweet_type TEXT, -- 'tweet', 'reply', 'retweet', 'quote'
    created_at TIMESTAMP NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    ai_processed BOOLEAN DEFAULT 0,
    telegram_sent BOOLEAN DEFAULT 0,
    INDEX idx_username (username),
    INDEX idx_created_at (created_at)
);

-- Media storage table
CREATE TABLE media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL,
    media_type TEXT NOT NULL, -- 'image', 'video', 'gif'
    original_url TEXT NOT NULL,
    local_path TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    download_status TEXT DEFAULT 'pending',
    downloaded_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

-- AI processing results
CREATE TABLE ai_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL,
    prompt_used TEXT NOT NULL,
    result TEXT,
    model_used TEXT,
    processing_time REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tweet_id) REFERENCES tweets(id)
);

-- User settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**Success Criteria**: Database created with all tables and indexes

#### Task 1.2: Create Database Models & ORM
**Deliverable**: Python models using SQLAlchemy
```python
# models.py
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Tweet(Base):
    __tablename__ = 'tweets'
    id = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    content = Column(String, nullable=False)
    # ... other fields
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'content': self.content,
            # ... other fields
        }
```
**Success Criteria**: All CRUD operations working

#### Task 1.3: Create Database Migration System
**Deliverable**: Simple migration system for schema updates
**Success Criteria**: Can upgrade/downgrade database schema

### Phase 2: Twitter Integration (Days 5-7)

#### Task 2.1: Implement Twitter API Client
**Deliverable**: Robust Twitter client with rate limit handling
```python
# twitter_client.py
import tweepy
from typing import List, Dict
import logging

class TwitterMonitor:
    def __init__(self, api_keys: Dict):
        self.api = self._setup_api(api_keys)
        self.logger = logging.getLogger(__name__)
    
    def get_user_tweets(self, username: str, since_id: str = None) -> List[Dict]:
        """Fetch latest tweets from user with automatic pagination"""
        try:
            tweets = []
            for tweet in tweepy.Cursor(
                self.api.user_timeline,
                screen_name=username,
                since_id=since_id,
                tweet_mode='extended',
                exclude_replies=False,
                include_rts=True
            ).items(50):
                tweets.append(self._parse_tweet(tweet))
            return tweets
        except tweepy.RateLimitError:
            self.logger.warning(f"Rate limit hit for {username}")
            return []
```
**Success Criteria**: 
- Can fetch tweets from multiple users
- Handles rate limits gracefully
- Parses all tweet types correctly

#### Task 2.2: Build Media Extractor
**Deliverable**: Extract all media URLs from tweets
```python
def extract_media_urls(tweet_data: Dict) -> List[Dict]:
    """Extract all media URLs with metadata"""
    media_items = []
    
    # Handle different media types
    if 'extended_entities' in tweet_data:
        for media in tweet_data['extended_entities'].get('media', []):
            if media['type'] == 'photo':
                media_items.append({
                    'type': 'image',
                    'url': media['media_url_https'],
                    'width': media['sizes']['large']['w'],
                    'height': media['sizes']['large']['h']
                })
            elif media['type'] in ['video', 'animated_gif']:
                # Get highest quality video
                variants = media['video_info']['variants']
                best_video = max(
                    [v for v in variants if v['content_type'] == 'video/mp4'],
                    key=lambda x: x.get('bitrate', 0)
                )
                media_items.append({
                    'type': 'video',
                    'url': best_video['url'],
                    'thumbnail': media['media_url_https']
                })
    
    return media_items
```
**Success Criteria**: Correctly identifies all media types

#### Task 2.3: Implement Polling Scheduler
**Deliverable**: Reliable polling system with error recovery
```python
# scheduler.py
import schedule
import time
from concurrent.futures import ThreadPoolExecutor

class TweetPoller:
    def __init__(self, twitter_client, db, config):
        self.twitter = twitter_client
        self.db = db
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def check_all_users(self):
        """Check all monitored users for new tweets"""
        for username in self.config.MONITORED_USERS:
            self.executor.submit(self.check_user, username)
    
    def start(self):
        """Start the polling schedule"""
        schedule.every(self.config.CHECK_INTERVAL).seconds.do(self.check_all_users)
        
        while True:
            schedule.run_pending()
            time.sleep(1)
```
**Success Criteria**: 
- Polls all users every 60 seconds
- Continues running despite errors
- Logs all activities

### Phase 3: Media Download System (Days 8-9)

#### Task 3.1: Build Async Media Downloader
**Deliverable**: Fast, reliable media downloader
```python
# media_downloader.py
import aiohttp
import asyncio
from pathlib import Path
import hashlib

class MediaDownloader:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.session = None
    
    async def download_media(self, tweet_id: str, media_url: str, media_type: str):
        """Download media with retry logic"""
        file_hash = hashlib.md5(media_url.encode()).hexdigest()
        ext = '.jpg' if media_type == 'image' else '.mp4'
        
        # Organize by date and tweet
        date_path = datetime.now().strftime('%Y/%m/%d')
        file_path = self.storage_path / date_path / tweet_id / f"{file_hash}{ext}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with retry
        for attempt in range(3):
            try:
                async with self.session.get(media_url) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        return str(file_path)
            except Exception as e:
                if attempt == 2:
                    raise e
                await asyncio.sleep(2 ** attempt)
```
**Success Criteria**:
- Downloads images and videos reliably
- Handles large files (>100MB)
- Organized file structure
- Deduplicates downloads

#### Task 3.2: Create Media Processing Pipeline
**Deliverable**: Complete pipeline from tweet to stored media
**Success Criteria**:
- Processes media in background
- Updates database with file paths
- Generates thumbnails for videos

### Phase 4: AI Integration (Days 10-11)

#### Task 4.1: Implement OpenAI Client
**Deliverable**: Robust OpenAI integration with error handling
```python
# ai_processor.py
import openai
from typing import Dict, Optional
import json

class AIProcessor:
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        openai.api_key = api_key
        self.model = model
    
    async def process_tweet(self, tweet: Dict, custom_prompt: str) -> Dict:
        """Process tweet through OpenAI with custom prompt"""
        
        # Build context-aware prompt
        prompt = f"""
        {custom_prompt}
        
        Tweet from @{tweet['username']}:
        "{tweet['content']}"
        
        Tweet metadata:
        - Type: {tweet['type']}
        - Has media: {len(tweet['media']) > 0}
        - Created: {tweet['created_at']}
        """
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are analyzing tweets."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                'success': True,
                'result': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens,
                'model': self.model
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
```
**Success Criteria**:
- Processes tweets with custom prompts
- Handles API errors gracefully
- Tracks token usage

#### Task 4.2: Build Prompt Management System
**Deliverable**: System for managing different AI prompts
**Success Criteria**:
- Store multiple prompt templates
- Select prompts based on tweet type
- Track prompt performance

### Phase 5: Telegram Integration (Days 12-13)

#### Task 5.1: Create Telegram Bot Client
**Deliverable**: Telegram bot that sends formatted messages
```python
# telegram_bot.py
from telegram import Bot, ParseMode
from telegram.error import TelegramError
import asyncio

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
    
    async def send_tweet_notification(self, tweet: Dict, ai_result: str, media_paths: List[str]):
        """Send formatted tweet with AI analysis to Telegram"""
        
        # Format message with Markdown
        message = f"""
🐦 *New Tweet from @{tweet['username']}*

{tweet['content']}

🤖 *AI Analysis:*
{ai_result}

📅 _{tweet['created_at']}_
        """
        
        try:
            # Send text message
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            # Send media if available
            if media_paths:
                media_group = []
                for path in media_paths[:10]:  # Telegram limit
                    if path.endswith(('.jpg', '.png')):
                        media_group.append(InputMediaPhoto(open(path, 'rb')))
                    elif path.endswith('.mp4'):
                        await self.bot.send_video(
                            chat_id=self.chat_id,
                            video=open(path, 'rb'),
                            caption=f"Video from @{tweet['username']}"
                        )
                
                if media_group:
                    await self.bot.send_media_group(
                        chat_id=self.chat_id,
                        media=media_group
                    )
                    
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False
```
**Success Criteria**:
- Sends formatted messages with media
- Handles different media types
- Rate limit aware

#### Task 5.2: Implement Notification Queue
**Deliverable**: Queue system to prevent Telegram rate limits
**Success Criteria**:
- Queues messages when rate limited
- Retries failed messages
- Respects Telegram's 30 messages/second limit

### Phase 6: UI/UX Design & Implementation (Days 14-18)

#### Task 6.1: Design UI/UX Mockups
**Deliverable**: Complete UI design system
```
Pages to Design:
1. Dashboard (main feed)
2. Tweet Detail View
3. Settings Page
4. Analytics Dashboard
5. Search & Filter Interface
```

**Dashboard Layout**:
```
+----------------------------------+
|        Twitter Monitor           |
|  [🔍 Search] [Filter▼] [Settings]|
+----------------------------------+
| Summary Stats                    |
| 📊 1,234 Tweets | 567 Media     |
| 🤖 890 Processed | ✈️ 456 Sent   |
+----------------------------------+
| Tweet Feed                       |
| +------------------------------+ |
| | @username · 2 hours ago      | |
| | Tweet content here...         | |
| | [Image thumbnails]           | |
| | 🤖 AI: Analysis result...    | |
| | Status: ✅ Sent to Telegram  | |
| +------------------------------+ |
| | @another_user · 3 hours ago  | |
| | Another tweet...             | |
| +------------------------------+ |
| [Load More]                      |
+----------------------------------+
```

**Color Scheme**:
- Primary: #1DA1F2 (Twitter Blue)
- Secondary: #14171A (Dark)
- Success: #17BF63 (Green)
- Background: #F7F9FA (Light Gray)
- Text: #14171A (Dark)

**Typography**:
- Headers: Inter or System Font
- Body: -apple-system, Roboto
- Monospace: Consolas, Monaco

#### Task 6.2: Create HTML/CSS Templates
**Deliverable**: Responsive templates using Bootstrap 5
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Twitter Monitor</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">🐦 Twitter Monitor</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/settings">⚙️ Settings</a>
                <a class="nav-link" href="/analytics">📊 Analytics</a>
            </div>
        </div>
    </nav>
    
    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
```
**Success Criteria**:
- Mobile responsive
- Fast loading (< 2s)
- Accessible (WCAG 2.1 AA)

#### Task 6.3: Implement Interactive Features
**Deliverable**: JavaScript for dynamic updates
```javascript
// static/js/app.js
class TwitterMonitor {
    constructor() {
        this.lastUpdate = new Date();
        this.autoRefresh = true;
        this.init();
    }
    
    init() {
        // Auto-refresh every 30 seconds
        setInterval(() => {
            if (this.autoRefresh) {
                this.checkNewTweets();
            }
        }, 30000);
        
        // Initialize tooltips
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(t => new bootstrap.Tooltip(t));
        
        // Search functionality
        document.getElementById('search').addEventListener('input', (e) => {
            this.filterTweets(e.target.value);
        });
    }
    
    async checkNewTweets() {
        const response = await fetch(`/api/tweets/new?since=${this.lastUpdate.toISOString()}`);
        const data = await response.json();
        
        if (data.count > 0) {
            this.showNotification(`${data.count} new tweets`);
            this.prependTweets(data.tweets);
        }
    }
    
    filterTweets(query) {
        const tweets = document.querySelectorAll('.tweet-card');
        tweets.forEach(tweet => {
            const text = tweet.textContent.toLowerCase();
            tweet.style.display = text.includes(query.toLowerCase()) ? 'block' : 'none';
        });
    }
}
```
**Success Criteria**:
- Real-time updates without page refresh
- Smooth animations
- Search works instantly

#### Task 6.4: Create Tweet Card Component
**Deliverable**: Reusable tweet display component
```html
<!-- templates/components/tweet_card.html -->
<div class="tweet-card card mb-3" data-tweet-id="{{ tweet.id }}">
    <div class="card-body">
        <div class="d-flex align-items-start">
            <img src="{{ tweet.profile_image }}" class="rounded-circle me-3" width="48">
            <div class="flex-grow-1">
                <h6 class="mb-1">
                    {{ tweet.display_name }}
                    <span class="text-muted">@{{ tweet.username }} · {{ tweet.created_at|timeago }}</span>
                </h6>
                <p class="tweet-content">{{ tweet.content|linkify }}</p>
                
                {% if tweet.media %}
                <div class="media-grid row g-2 mt-2">
                    {% for media in tweet.media[:4] %}
                    <div class="col-6">
                        {% if media.type == 'image' %}
                        <img src="{{ media.local_url }}" class="img-fluid rounded" 
                             data-bs-toggle="modal" data-bs-target="#mediaModal"
                             data-media-url="{{ media.local_url }}">
                        {% elif media.type == 'video' %}
                        <video controls class="w-100 rounded">
                            <source src="{{ media.local_url }}" type="video/mp4">
                        </video>
                        {% endif %}
                    </div>
                    {% endfor %}
                    {% if tweet.media|length > 4 %}
                    <div class="col-6 d-flex align-items-center justify-content-center bg-light rounded">
                        <span class="text-muted">+{{ tweet.media|length - 4 }} more</span>
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                {% if tweet.ai_result %}
                <div class="ai-analysis mt-3 p-3 bg-light rounded">
                    <small class="text-muted d-block mb-1">🤖 AI Analysis:</small>
                    <p class="mb-0 small">{{ tweet.ai_result }}</p>
                </div>
                {% endif %}
                
                <div class="tweet-actions mt-3 d-flex gap-3 small">
                    <span class="text-muted">
                        {% if tweet.telegram_sent %}
                        <span class="text-success">✅ Sent to Telegram</span>
                        {% else %}
                        <span class="text-warning">⏳ Pending</span>
                        {% endif %}
                    </span>
                    <a href="/tweet/{{ tweet.id }}" class="text-decoration-none">View Details</a>
                    <a href="#" class="text-decoration-none" onclick="retryTweet('{{ tweet.id }}')">Retry</a>
                </div>
            </div>
        </div>
    </div>
</div>
```
**Success Criteria**:
- Displays all tweet data clearly
- Media preview works
- Interactive elements functional

#### Task 6.5: Build Settings Interface
**Deliverable**: User-friendly settings page
```html
<!-- templates/settings.html -->
<div class="settings-page">
    <h2>Settings</h2>
    
    <div class="card mt-4">
        <div class="card-header">
            <h5>Monitored Accounts</h5>
        </div>
        <div class="card-body">
            <div class="mb-3">
                <label class="form-label">Twitter Usernames (comma-separated)</label>
                <textarea class="form-control" id="monitored-users" rows="3">{{ settings.monitored_users }}</textarea>
                <small class="form-text text-muted">Example: elonmusk, naval, paulg</small>
            </div>
            <button class="btn btn-primary" onclick="saveSettings()">Save Changes</button>
        </div>
    </div>
    
    <div class="card mt-4">
        <div class="card-header">
            <h5>AI Processing</h5>
        </div>
        <div class="card-body">
            <div class="mb-3">
                <label class="form-label">OpenAI Prompt</label>
                <textarea class="form-control" id="ai-prompt" rows="5">{{ settings.ai_prompt }}</textarea>
                <small class="form-text text-muted">This prompt will be used to analyze each tweet</small>
            </div>
            <div class="mb-3">
                <label class="form-label">Model</label>
                <select class="form-select" id="ai-model">
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo (Fastest)</option>
                    <option value="gpt-4">GPT-4 (Most Accurate)</option>
                </select>
            </div>
        </div>
    </div>
</div>
```
**Success Criteria**:
- All settings editable
- Changes persist
- Validation on inputs

### Phase 7: Integration & Testing (Days 19-21)

#### Task 7.1: Create End-to-End Pipeline
**Deliverable**: Complete flow from Twitter to Telegram
```python
# main_pipeline.py
class TweetPipeline:
    def __init__(self):
        self.twitter = TwitterMonitor(config)
        self.downloader = MediaDownloader(config.MEDIA_PATH)
        self.ai = AIProcessor(config.OPENAI_KEY)
        self.telegram = TelegramNotifier(config.TELEGRAM_TOKEN)
        self.db = Database()
    
    async def process_tweet(self, tweet_data):
        """Complete pipeline for a single tweet"""
        
        # 1. Save tweet to database
        tweet = self.db.save_tweet(tweet_data)
        
        # 2. Download media
        for media in tweet_data['media']:
            local_path = await self.downloader.download_media(
                tweet.id, media['url'], media['type']
            )
            self.db.save_media(tweet.id, media, local_path)
        
        # 3. Process with AI
        ai_result = await self.ai.process_tweet(
            tweet_data, 
            self.db.get_setting('ai_prompt')
        )
        self.db.save_ai_result(tweet.id, ai_result)
        
        # 4. Send to Telegram
        media_paths = self.db.get_media_paths(tweet.id)
        sent = await self.telegram.send_tweet_notification(
            tweet_data, 
            ai_result['result'],
            media_paths
        )
        self.db.update_tweet_status(tweet.id, telegram_sent=sent)
        
        return tweet.id
```
**Success Criteria**:
- Full pipeline works end-to-end
- Error recovery at each step
- Performance < 5s per tweet

#### Task 7.2: Write Comprehensive Tests
**Deliverable**: Test suite with >80% coverage
```python
# tests/test_pipeline.py
import pytest
from unittest.mock import Mock, patch

class TestTweetPipeline:
    @pytest.fixture
    def pipeline(self):
        return TweetPipeline()
    
    @pytest.mark.asyncio
    async def test_process_tweet_success(self, pipeline):
        # Mock tweet data
        tweet_data = {
            'id': '123456',
            'username': 'testuser',
            'content': 'Test tweet',
            'media': []
        }
        
        # Process tweet
        result = await pipeline.process_tweet(tweet_data)
        
        # Verify all steps completed
        assert result == '123456'
        assert pipeline.db.get_tweet('123456') is not None
    
    @pytest.mark.asyncio
    async def test_media_download_retry(self, pipeline):
        # Test retry logic on failure
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = [Exception(), Exception(), Mock(status=200)]
            
            result = await pipeline.downloader.download_media(
                '123', 'http://example.com/image.jpg', 'image'
            )
            
            assert mock_get.call_count == 3
            assert result is not None
```
**Success Criteria**:
- Unit tests for all components
- Integration tests for pipeline
- Error scenario tests

#### Task 7.3: Performance Optimization
**Deliverable**: Optimized system handling 100+ tweets/minute
**Success Criteria**:
- Media downloads in parallel
- Database queries optimized
- Memory usage stable

### Phase 8: Deployment & Documentation (Days 22-24)

#### Task 8.1: Create Deployment Scripts
**Deliverable**: One-command deployment
```bash
#!/bin/bash
# deploy.sh

# Check Python version
python3 --version

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# Create systemd service
sudo cp twitter-monitor.service /etc/systemd/system/
sudo systemctl enable twitter-monitor
sudo systemctl start twitter-monitor

echo "Deployment complete! Check status with: sudo systemctl status twitter-monitor"
```
**Success Criteria**:
- Works on Ubuntu/Debian
- Handles all edge cases
- Includes rollback option

#### Task 8.2: Write User Documentation
**Deliverable**: Complete README and user guide
**Success Criteria**:
- Installation guide
- Configuration reference
- Troubleshooting section

#### Task 8.3: Setup Monitoring & Alerts
**Deliverable**: Basic monitoring dashboard
```python
# monitoring.py
class SystemMonitor:
    def check_health(self):
        return {
            'twitter_api': self.check_twitter_connection(),
            'database': self.check_database(),
            'storage_space': self.check_storage(),
            'telegram_bot': self.check_telegram(),
            'last_tweet': self.get_last_tweet_time()
        }
```
**Success Criteria**:
- Health check endpoint
- Email alerts on failures
- Basic metrics dashboard

## Success Metrics

### Technical Metrics
- **Reliability**: 99% uptime
- **Performance**: Process tweet in <5 seconds
- **Storage**: <100MB per 1000 tweets with media
- **API Usage**: Stay within rate limits

### Business Metrics
- **Coverage**: Miss <1% of tweets from monitored users
- **Accuracy**: AI processing success rate >95%
- **Delivery**: Telegram notifications within 2 minutes

## Risk Mitigation

### Technical Risks
1. **Twitter API Changes**: Use official Tweepy library for stability
2. **Rate Limits**: Implement exponential backoff
3. **Storage Full**: Auto-cleanup old media after 90 days
4. **Database Corruption**: Daily backups to separate location

### Operational Risks
1. **API Key Exposure**: Use environment variables, never commit keys
2. **Cost Overrun**: Monitor OpenAI usage, set spending limits
3. **Telegram Spam**: Rate limit notifications per user

## Timeline Summary

**Week 1** (Days 1-7): Setup, Database, Twitter Integration
**Week 2** (Days 8-14): Media Download, AI, Telegram
**Week 3** (Days 15-21): UI/UX Implementation, Testing
**Week 4** (Days 22-24): Deployment, Documentation, Launch

Total: 24 working days for MVP

## Next Steps

1. Review and approve this plan
2. Set up development environment
3. Begin Phase 0: Project Setup
4. Daily progress updates via dashboard

This revised plan focuses on:
- Using proven, well-maintained tools
- Step-by-step task breakdown with clear deliverables
- Dedicated UI/UX phase for good user experience
- Realistic timeline with buffer
- Clear success criteria for each task