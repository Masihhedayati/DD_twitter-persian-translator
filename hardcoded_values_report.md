# Hardcoded Values Report for dd_v3 Project

## Summary
This report documents all hardcoded values found in Python files within the `/Users/stevmq/dd_v3` directory, focusing on the main application files and core modules.

## 1. URLs and API Endpoints

### app.py
- Line 204: `https://pbs.twimg.com/profile_images/1683325380441128960/yRsRRjGO_normal.jpg` (test profile image URL)

### core/twitter_client.py
- Line 23: `self.base_url = "https://api.twitterapi.io"` (Twitter API base URL)
- Line 61: `url = f"{self.base_url}/twitter/user/last_tweets"` (API endpoint)

### config.py
- Line 19: `TWITTER_API_BASE_URL = 'https://api.twitterapi.io'` (Twitter API base URL)

## 2. Port Numbers

### app.py
- Line 928: `port=app.config.get('PORT', 5001)` (default port 5001)

### config.py
- Line 11: `PORT = int(os.environ.get('PORT', 5001))` (default port 5001)

## 3. File Paths

### app.py
- Line 29: `logging.FileHandler('logs/app.log')` (log file path)
- Line 50: `database = Database(app.config.get('DATABASE_PATH', './tweets.db'))` (default DB path)
- Line 59: Default monitored users list hardcoded as `['elonmusk', 'naval', 'paulg']`
- Line 61: `MEDIA_STORAGE_PATH` default: `'./media'`
- Line 62: `DATABASE_PATH` default: `'./tweets.db'`
- Line 101: `'logs/twitter-monitor.log'` (production log file)
- Line 726: `MEDIA_STORAGE_PATH` default: `'./media'`
- Line 914: `os.makedirs('logs', exist_ok=True)`
- Line 915: `os.makedirs('media', exist_ok=True)`

### config.py
- Line 15: `DATABASE_PATH = os.environ.get('DATABASE_PATH', './tweets.db')` (default DB path)
- Line 48: `MEDIA_STORAGE_PATH = os.environ.get('MEDIA_STORAGE_PATH', './media')` (default media path)
- Line 101: `'logs/twitter-monitor.log'` (production log file path)

### core/database.py
- Line 13: `def __init__(self, db_path: str = "./tweets.db"):` (default DB path)
- Line 617: Default monitored users: `['elonmusk', 'naval', 'paulg']`
- Line 621: Default monitored users: `['elonmusk', 'naval', 'paulg']`
- Line 781: `def init_db(db_path: str = "./tweets.db"):` (default DB path)

### core/media_extractor.py
- Line 47: Base directories: `['images', 'videos', 'audio', 'thumbnails']`

## 4. Database Configuration

### core/database.py
- SQLite database schema hardcoded in lines 24-93 (CREATE TABLE statements)
- Database file: `tweets.db` (SQLite)

## 5. Timeout Values and Numeric Constants

### app.py
- Line 60: `CHECK_INTERVAL` default: 60 seconds
- Line 63: `AI_BATCH_SIZE` default: 5
- Line 64: `AI_PROCESSING_INTERVAL` default: 120 seconds
- Line 68: `NOTIFICATION_DELAY` default: 10 seconds
- Line 71: `HISTORICAL_HOURS` default: 2 hours
- Line 142: Version: `'1.0.0'`
- Line 259: Default limit: 50 tweets
- Line 470: Default notification limit: 5
- Line 532: Default batch size: 10
- Line 549: Default check interval: 60 seconds
- Line 562-566: AI settings defaults
- Line 715: Database size calculation divisor: 1024 * 1024 (MB conversion)

### config.py
- Line 9: `SECRET_KEY` default: `'dev-secret-key-change-in-production'`
- Line 10: `HOST` default: `'0.0.0.0'`
- Line 11: `PORT` default: 5001
- Line 25: `HISTORICAL_HOURS` default: 2
- Line 30: `OPENAI_MODEL` default: `'gpt-3.5-turbo'`
- Line 31: `OPENAI_MAX_TOKENS` default: 150
- Line 41: `NOTIFICATION_DELAY` default: 10
- Line 44: Default monitored users: `'elonmusk,naval,paulg'`
- Line 45: `CHECK_INTERVAL` default: 60 seconds
- Line 49: `MAX_MEDIA_SIZE` default: 104857600 (100MB)
- Line 50: `MEDIA_RETENTION_DAYS` default: 90
- Line 53: `MAX_CONCURRENT_DOWNLOADS` default: 5
- Line 54: `DOWNLOAD_TIMEOUT` default: 30 seconds
- Line 55: `MAX_RETRY_ATTEMPTS` default: 3
- Line 61: `DEFAULT_AI_MAX_TOKENS` default: 150
- Line 102: Log file max size: 10240000 (10MB)
- Line 103: Log backup count: 10

### core/twitter_client.py
- Line 28: `rate_limit_remaining = 100`
- Line 31: `min_request_interval = 1.0` seconds
- Line 64: Max tweet count: 100
- Line 73: Request timeout: 30 seconds
- Line 121: Sleep between users: 0.5 seconds
- Line 148: Tweet count for historical fetch: 50
- Line 166: Sleep between users: 0.5 seconds
- Line 380: File size tolerance: 1% or 100 bytes
- Line 443: `min_request_interval = 1.0` seconds

### core/media_extractor.py
- Line 33: `max_retries = 3`
- Line 34: `retry_delay = 1.0` seconds
- Line 35: `timeout = 30` seconds
- Line 36: `max_file_size = 100 * 1024 * 1024` (100MB)
- Line 37: `concurrent_downloads = 5`
- Line 169: HTTP timeout: 30 seconds
- Line 229: Exponential backoff multiplier: 2
- Line 380: Size tolerance: 1% or 100 bytes
- Line 447: `days_to_keep` default: 90 days
- Line 642: Request timeout: 30 seconds
- Line 705: `days_old` default: 30 days
- Line 707: Time calculation: `days_old * 24 * 60 * 60`

### core/openai_client.py
- Line 19: `model` default: `"gpt-3.5-turbo"`
- Line 19: `max_tokens` default: 1000
- Line 26: `max_retries = 3`
- Line 27: `request_timeout = 30`
- Line 31: `rate_limit_rpm = 3000` (requests per minute)
- Line 32: `rate_limit_tpm = 90000` (tokens per minute)
- Line 48: `cache_ttl = 3600` (1 hour)
- Lines 40-44: Model costs hardcoded:
  - GPT-4: input=$0.03, output=$0.06
  - GPT-4-turbo: input=$0.01, output=$0.03
  - GPT-3.5-turbo: input=$0.001, output=$0.002

## 6. Hardcoded Credentials/Keys

### config.py
- Line 9: Default secret key: `'dev-secret-key-change-in-production'` (should be changed in production)

## 7. Email Addresses and Domains

No hardcoded email addresses were found in the main application files.

## 8. Default Values and Constants

### app.py
- Line 59: Default monitored users: `'elonmusk', 'naval', 'paulg'`
- Line 199: Test tweet text: `"This is a test tweet for webhook functionality! #test #webhook"`
- Line 201: Test username: `"elonmusk"`

### config.py
- Line 44: Default monitored users: `'elonmusk,naval,paulg'`
- Line 58-59: Default AI prompt (multiline string)
- Line 60: Default AI model: `'gpt-3.5-turbo'`

### core/database.py
- Line 617, 621: Default monitored users: `['elonmusk', 'naval', 'paulg']`

### core/media_extractor.py
- Line 40: Valid media types: `{'image', 'video', 'audio', 'gif'}`
- Line 47: Base directories: `['images', 'videos', 'audio', 'thumbnails']`
- Line 568: Image extensions: `['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']`
- Line 573: Video extensions: `['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']`
- Line 639: User-Agent: `'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'`

### core/webhook_handler.py
- Line 25: Default monitored users: `'elonmusk,naval,paulg'`

### core/openai_client.py
- Lines 51-58: Hardcoded prompt templates for different analysis types

## 9. API Response Formats

### app.py
- Lines 197-217: Test tweet JSON structure hardcoded
- Line 142: API version: `'1.0.0'`

### core/twitter_client.py
- Lines 189-193: Twitter time format strings hardcoded
- Line 306: Regex pattern for t.co links: `r'https://t\.co/\w+$'`

## Recommendations

1. **Configuration Management**: Move all hardcoded values to environment variables or a configuration file
2. **Secrets Management**: The default secret key should never be used in production
3. **Path Configuration**: Use absolute paths or configurable base paths instead of relative paths
4. **Rate Limits**: Consider making rate limits configurable
5. **Timeouts**: Make timeout values configurable based on deployment environment
6. **Default Users**: Consider removing hardcoded default users or making them configurable
7. **API Costs**: Consider moving cost tracking configuration to a separate config file
8. **User Agents**: Move user agent strings to configuration
9. **File Extensions**: Consider making supported file types configurable