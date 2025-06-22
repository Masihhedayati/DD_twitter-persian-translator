# Twitter Monitor - Production Deployment Guide

## 🚀 **PRODUCTION DEPLOYMENT SETUP**

This comprehensive guide will walk you through deploying the Twitter Monitoring & Notification System in production.

## 📋 **PREREQUISITES**

### System Requirements
- **Python**: 3.9+ (tested with 3.13.3)
- **Memory**: Minimum 512MB RAM, Recommended 2GB+
- **Storage**: 1GB+ for database and media files
- **Network**: Stable internet connection for API calls

### Required API Credentials
You will need the following credentials before deployment:

#### 1. **Twitter API (TwitterAPI.io)**
- **API Key**: Your TwitterAPI.io API key
- **Required for**: Monitoring user tweets and fetching tweet data
- **Cost**: Check TwitterAPI.io pricing plans
- **Obtain from**: https://twitterapi.io/

#### 2. **OpenAI API**
- **API Key**: Your OpenAI API key  
- **Required for**: AI analysis of tweet content
- **Cost**: Pay-per-token usage (typically $0.01-0.05 per analysis)
- **Obtain from**: https://platform.openai.com/api-keys

#### 3. **Telegram Bot API**
- **Bot Token**: Your Telegram bot token
- **Chat ID**: Target chat/channel ID for notifications
- **Required for**: Sending tweet notifications
- **Cost**: Free
- **Obtain from**: @BotFather on Telegram

## 🔧 **INSTALLATION STEPS**

### Step 1: Clone and Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd dd_v3

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration
Create a `.env` file in the project root:

```bash
# Copy the example environment file
cp env.example .env
```

Edit `.env` with your actual credentials:

```env
# Twitter API Configuration
TWITTER_API_KEY=your_twitterapi_io_key_here

# OpenAI Configuration  
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=150

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Monitoring Configuration
MONITORED_USERS=elonmusk,naval,paulg
CHECK_INTERVAL=60
NOTIFICATION_ENABLED=true
NOTIFY_AI_PROCESSED_ONLY=true

# System Configuration
DATABASE_PATH=./tweets.db
MEDIA_STORAGE_PATH=./media
LOG_LEVEL=INFO
PORT=5001

# Performance Configuration
AI_BATCH_SIZE=5
AI_PROCESSING_INTERVAL=120
NOTIFICATION_DELAY=10
```

### Step 3: Database Initialization
```bash
# Initialize the database
python -c "from core.database import Database; db = Database('./tweets.db'); print('Database initialized successfully')"
```

### Step 4: Test Configuration
```bash
# Test your configuration
python -c "
from core.config_manager import ConfigManager
config = ConfigManager()
print('✅ Configuration loaded successfully')
print(f'Monitoring users: {config.get_config_value(\"app\", \"monitored_users\", \"none\")}')
"
```

## 🐳 **DOCKER DEPLOYMENT (Recommended)**

### Using Docker Compose
```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application  
docker-compose down
```

### Manual Docker Build
```bash
# Build the image
docker build -t twitter-monitor .

# Run the container
docker run -d \
  --name twitter-monitor \
  -p 5001:5001 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  twitter-monitor
```

## 🖥️ **DIRECT DEPLOYMENT**

### Start the Application
```bash
# Activate virtual environment
source venv/bin/activate

# Start the Flask application
python app.py
```

The application will be available at `http://localhost:5001`

### Production WSGI Server
For production, use a proper WSGI server:

```bash
# Install gunicorn
pip install gunicorn

# Start with gunicorn
gunicorn --bind 0.0.0.0:5001 --workers 2 app:app
```

## 🔍 **VERIFICATION STEPS**

### 1. Health Check
```bash
curl http://localhost:5001/health
```
Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-12-22T10:00:00.000Z",
  "version": "1.0.0"
}
```

### 2. Dashboard Access
- Open `http://localhost:5001` in your browser
- You should see the Twitter Monitor Dashboard
- Check the statistics cards for system status

### 3. API Endpoints Test
```bash
# Test tweets API
curl http://localhost:5001/api/tweets

# Test statistics API  
curl http://localhost:5001/api/statistics

# Test system status
curl http://localhost:5001/api/status
```

### 4. Monitor Logs
```bash
# View application logs
tail -f logs/app.log

# Check for any errors
grep -i error logs/app.log
```

## 📊 **MONITORING AND MAINTENANCE**

### Log Files Location
- **Application Logs**: `logs/app.log`
- **Error Logs**: `logs/error.log` 
- **Performance Logs**: `logs/performance.log`

### Database Management
```bash
# Check database size
ls -lh tweets.db

# Backup database
cp tweets.db tweets_backup_$(date +%Y%m%d).db

# View database contents
sqlite3 tweets.db "SELECT COUNT(*) FROM tweets;"
```

### Media Files Management
```bash
# Check media storage size
du -sh media/

# Clean old media files (optional)
find media/ -type f -mtime +30 -delete
```

## ⚡ **PERFORMANCE OPTIMIZATION**

### Recommended Settings for High Volume
```env
# Increase batch sizes for high volume
AI_BATCH_SIZE=10
CHECK_INTERVAL=30
NOTIFICATION_DELAY=5

# Enable caching
ENABLE_CACHING=true
CACHE_TTL=300

# Database optimization
DATABASE_POOL_SIZE=10
```

### System Resource Monitoring
```bash
# Monitor CPU and memory usage
htop

# Monitor network usage
netstat -i

# Monitor disk space
df -h
```

## 🚨 **TROUBLESHOOTING**

### Common Issues

#### 1. **Database Connection Issues**
```bash
# Check database file permissions
ls -la tweets.db

# Re-initialize database
rm tweets.db
python -c "from core.database import Database; Database('./tweets.db')"
```

#### 2. **API Rate Limiting**
- Check your TwitterAPI.io quota and limits
- Increase `CHECK_INTERVAL` to reduce API calls
- Monitor rate limiting in logs

#### 3. **Telegram Notifications Not Working**
```bash
# Test bot token
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"

# Test chat ID
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${TELEGRAM_CHAT_ID}&text=Test"
```

#### 4. **High Memory Usage**
- Reduce `AI_BATCH_SIZE`
- Enable periodic cleanup
- Monitor for memory leaks in logs

### Log Analysis
```bash
# Check for errors
grep -i "error\|exception\|failed" logs/app.log

# Monitor API calls
grep -i "api" logs/app.log | tail -20

# Check performance
grep -i "processing time\|elapsed" logs/app.log
```

## 🔒 **SECURITY CONSIDERATIONS**

### Environment Variables
- Never commit `.env` files to version control
- Use secure environment variable management in production
- Rotate API keys regularly

### Network Security
- Use HTTPS in production
- Configure firewall rules to restrict access
- Consider using VPN for admin access

### Data Privacy
- Configure data retention policies
- Implement log rotation
- Secure database backups

## 📈 **SCALING CONSIDERATIONS**

### Horizontal Scaling
- Use Docker Swarm or Kubernetes for multiple instances
- Implement shared database backend
- Use Redis for shared caching

### Vertical Scaling
- Increase server resources (CPU, RAM)
- Optimize database indexes
- Use SSD storage for better I/O performance

## 🆘 **SUPPORT AND MAINTENANCE**

### Regular Maintenance Tasks
1. **Daily**: Check logs for errors
2. **Weekly**: Monitor API usage and costs
3. **Monthly**: Backup database and clean old media
4. **Quarterly**: Update dependencies and security patches

### Performance Monitoring
- Set up alerts for API failures
- Monitor response times
- Track notification delivery success rates

### Updates and Upgrades
```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Restart application
docker-compose restart
# OR
pkill -f "python app.py" && python app.py &
```

---

## 🎯 **QUICK START CHECKLIST**

- [ ] All API credentials obtained and configured
- [ ] `.env` file created with your credentials
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Database initialized successfully
- [ ] Application starts without errors
- [ ] Dashboard accessible at `http://localhost:5001`
- [ ] Health check returns "healthy" status
- [ ] First tweets appear in dashboard
- [ ] Telegram notifications working
- [ ] Logs show successful operations

**Once all items are checked, your Twitter Monitor is ready for production!** 🎉 