# Twitter Monitoring & Notification System

A comprehensive Python application that monitors specified Twitter accounts, downloads media content, processes tweets with AI, and sends intelligent notifications via Telegram.

## 🚀 Features

- **Real-time Twitter Monitoring**: Track multiple Twitter accounts automatically
- **Media Download**: Automatically download images, videos, and audio from tweets
- **AI Processing**: Analyze tweets using OpenAI for intelligent insights
- **Telegram Integration**: Send notifications with rich media to Telegram
- **Web Dashboard**: User-friendly interface to view and manage collected data
- **Robust Architecture**: Built with Flask, SQLite, and proven Python libraries

## 📋 Requirements

- Python 3.11+
- Twitter API access (TwitterAPI.io)
- OpenAI API key
- Telegram Bot token
- ~500MB disk space for initial setup

## 🔧 Installation

### 1. Clone and Setup Environment

```bash
git clone <your-repo-url>
cd twitter-monitor
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp env.example .env
# Edit .env file with your API keys and settings
```

Required API Keys:
- **TwitterAPI.io**: Get from [twitterapi.io/dashboard](https://twitterapi.io/dashboard)
- **OpenAI**: Get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Telegram Bot**: Create via [@BotFather](https://t.me/BotFather) on Telegram

### 3. Initialize Database

```bash
python -c "from core.database import init_db; init_db()"
```

### 4. Run Application

```bash
python app.py
```

Visit `http://localhost:5000` to access the dashboard.

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONITORED_USERS` | Comma-separated Twitter usernames | `elonmusk,naval,paulg` |
| `CHECK_INTERVAL` | Tweet check frequency (seconds) | `60` |
| `OPENAI_MODEL` | AI model to use | `gpt-3.5-turbo` |
| `MEDIA_RETENTION_DAYS` | Days to keep downloaded media | `90` |

### Monitored Users

Add Twitter usernames (without @) to `MONITORED_USERS`:
```env
MONITORED_USERS=elonmusk,karpathy,sama,paulg,naval
```

### AI Prompts

Customize AI analysis in the dashboard settings or via:
```env
DEFAULT_AI_PROMPT="Analyze this tweet and provide key insights about its content and sentiment."
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Twitter API   │    │   Flask Web App   │    │   Telegram Bot  │
│   (TwitterAPI.io)│<-->│                  │<-->│                 │
└─────────────────┘    │  ┌─────────────┐ │    └─────────────────┘
                       │  │  Scheduler  │ │
┌─────────────────┐    │  └─────────────┘ │    ┌─────────────────┐
│    OpenAI API   │<-->│                  │    │   SQLite DB     │
└─────────────────┘    │  ┌─────────────┐ │    │                 │
                       │  │Media Download│ │<-->│  Tweet Storage  │
┌─────────────────┐    │  └─────────────┘ │    └─────────────────┘
│  File Storage   │<-->└──────────────────┘
│  (Images/Videos)│
└─────────────────┘
```

## 📊 Dashboard Features

### Tweet Timeline
- Chronological feed of monitored tweets
- Real-time updates without page refresh
- Rich media display (images, videos, audio)

### Filtering & Search
- Filter by username or date range
- Full-text search in tweet content
- Filter by media type or AI results

### Analytics
- Tweet volume statistics
- Media download metrics
- AI processing performance
- Storage usage tracking

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/tweets` | GET | Get tweets JSON |
| `/api/stats` | GET | System statistics |
| `/health` | GET | Health check |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov-report=html

# Run specific test file
pytest tests/test_twitter_client.py
```

## 📝 Logging

Logs are stored in `logs/` directory:
- `app.log`: Application logs
- `twitter.log`: Twitter API interactions
- `ai.log`: OpenAI processing logs
- `telegram.log`: Telegram bot logs

Log level can be configured via `LOG_LEVEL` environment variable.

## 🚀 Deployment

### Production Setup

1. **Environment Configuration**:
   ```bash
   export FLASK_ENV=production
   export FLASK_DEBUG=False
   ```

2. **Process Management**:
   ```bash
   # Using systemd
   sudo cp twitter-monitor.service /etc/systemd/system/
   sudo systemctl enable twitter-monitor
   sudo systemctl start twitter-monitor
   ```

3. **Reverse Proxy** (nginx example):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### Docker Deployment

```bash
# Build image
docker build -t twitter-monitor .

# Run container
docker run -d \
  --name twitter-monitor \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  twitter-monitor
```

## 🛠️ Development

### Project Structure

```
twitter-monitor/
├── app.py              # Main Flask application
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── core/              # Core business logic
│   ├── twitter_client.py
│   ├── media_downloader.py
│   ├── ai_processor.py
│   ├── telegram_bot.py
│   └── database.py
├── templates/         # HTML templates
├── static/           # CSS, JS, images
├── tests/            # Unit tests
└── logs/             # Application logs
```

### Adding New Features

1. Create feature branch: `git checkout -b feature/new-feature`
2. Add tests in `tests/`
3. Implement feature in appropriate `core/` module
4. Update documentation
5. Submit pull request

## 📋 Troubleshooting

### Common Issues

**Problem**: Twitter API rate limits
**Solution**: Increase `CHECK_INTERVAL` or reduce monitored users

**Problem**: Media download failures
**Solution**: Check network connectivity and storage space

**Problem**: Telegram notifications not working
**Solution**: Verify bot token and chat ID in settings

**Problem**: High CPU usage
**Solution**: Increase check interval or optimize AI processing frequency

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python app.py
```

## 💰 Cost Estimation

**Monthly costs for monitoring 10 active accounts:**
- TwitterAPI.io: ~$15-30 (based on tweet volume)
- OpenAI API: ~$5-20 (gpt-3.5-turbo)
- Server hosting: ~$10-50 (VPS or cloud)
- **Total**: $30-100/month

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- Create an issue for bugs or feature requests
- Check the troubleshooting section
- Review logs in the `logs/` directory

---

**⚡ Quick Start**: Copy `env.example` to `.env`, add your API keys, run `pip install -r requirements.txt && python app.py` 