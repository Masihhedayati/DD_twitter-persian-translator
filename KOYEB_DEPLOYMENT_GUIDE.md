# Koyeb Deployment Guide - Updated 2025

## Overview

This guide provides two deployment methods:

1. **🚀 CLI Deployment** (Recommended - Faster & Automated)
2. **🖥️ Web Interface Deployment** (Manual but Visual)

Both methods will deploy your Twitter monitoring application with PostgreSQL database.

---

## Method 1: CLI Deployment (Recommended)

### Prerequisites

1. **Koyeb CLI Installation**
   ```bash
   # macOS/Linux
   curl -L https://github.com/koyeb/koyeb-cli/releases/latest/download/koyeb-cli_$(uname -s)_$(uname -m) -o koyeb
   chmod +x koyeb
   sudo mv koyeb /usr/local/bin/
   
   # Verify installation
   koyeb version
   ```

2. **Get Your Koyeb API Token**
   - Go to https://app.koyeb.com
   - Navigate to **Settings** → **API Tokens**
   - Click **Create API Token**
   - Name it: `CLI Deployment Token`
   - Copy the token immediately (you won't see it again)

3. **Authenticate CLI**
   ```bash
   koyeb auth login
   # Enter your API token when prompted
   ```

### Step 1: Create PostgreSQL Database

```bash
# Create database service
koyeb database create \
  --name="twitter-monitor-db" \
  --engine="postgresql-16" \
  --region="fra" \
  --instance-type="free"

# Wait for database to be ready (takes 2-3 minutes)
koyeb database get twitter-monitor-db

# Get connection string
koyeb database get twitter-monitor-db --format=json | jq -r '.connection_info.database_url'
```

### Step 2: Create Secrets

```bash
# Twitter API credentials
koyeb secret create TWITTER_API_KEY "your_twitter_api_key_here"
koyeb secret create TWITTER_API_SECRET "your_twitter_api_secret_here"
koyeb secret create TWITTER_BEARER_TOKEN "your_twitter_bearer_token_here"

# Telegram Bot credentials  
koyeb secret create TELEGRAM_BOT_TOKEN "your_telegram_bot_token_here"
koyeb secret create TELEGRAM_CHAT_ID "your_telegram_chat_id_here"

# AI API credentials
koyeb secret create OPENAI_API_KEY "your_openai_api_key_here"

# RSS webhook URL (will be auto-detected by app)
koyeb secret create RSS_WEBHOOK_URL "AUTO_DETECT"

# Database URL (from step 1 - replace with actual connection string)
koyeb secret create DATABASE_URL "postgresql://user:pass@host:5432/dbname"

# Application settings
koyeb secret create OPERATION_MODE "webhook_only"
koyeb secret create ENABLE_MEDIA_DOWNLOAD "false"
koyeb secret create AI_MAX_TOKENS "150"
```

### Step 3: Deploy Application

```bash
# Deploy from GitHub repository
koyeb service create \
  --app="twitter-monitor" \
  --name="twitter-monitor-service" \
  --git="github.com/yourusername/dd_v3" \
  --git-branch="main" \
  --git-build-command="docker" \
  --git-dockerfile="Dockerfile.prod" \
  --instance-type="nano" \
  --region="fra" \
  --port="5000:http" \
  --route="/:5000" \
  --env="PORT=5000" \
  --env="DATABASE_URL={{ secret.DATABASE_URL }}" \
  --env="TWITTER_API_KEY={{ secret.TWITTER_API_KEY }}" \
  --env="TWITTER_API_SECRET={{ secret.TWITTER_API_SECRET }}" \
  --env="TWITTER_BEARER_TOKEN={{ secret.TWITTER_BEARER_TOKEN }}" \
  --env="TELEGRAM_BOT_TOKEN={{ secret.TELEGRAM_BOT_TOKEN }}" \
  --env="TELEGRAM_CHAT_ID={{ secret.TELEGRAM_CHAT_ID }}" \
  --env="OPENAI_API_KEY={{ secret.OPENAI_API_KEY }}" \
  --env="RSS_WEBHOOK_URL={{ secret.RSS_WEBHOOK_URL }}" \
  --env="OPERATION_MODE={{ secret.OPERATION_MODE }}" \
  --env="ENABLE_MEDIA_DOWNLOAD={{ secret.ENABLE_MEDIA_DOWNLOAD }}" \
  --env="AI_MAX_TOKENS={{ secret.AI_MAX_TOKENS }}" \
  --health-check="/health" \
  --scale-min=1 \
  --scale-max=1

# Monitor deployment
koyeb service logs twitter-monitor-service --follow
```

### Step 4: Get Application URL

```bash
# Get app URL
koyeb service get twitter-monitor-service --format=json | jq -r '.public_domain'
```

---

## Method 2: Web Interface Deployment

### Step 1: Create PostgreSQL Database

1. Go to https://app.koyeb.com
2. Click **Databases** → **Create Database Service**
3. Configure:
   - **Name**: `twitter-monitor-db`
   - **Region**: Frankfurt (fra)
   - **Engine**: PostgreSQL 16
   - **Default role**: `koyeb-adm`
   - **Instance type**: Free
4. Click **Create Database Service**
5. Wait 2-3 minutes for deployment
6. Copy the **psql** connection string from the **Connection Details** tab

### Step 2: Create Secrets

1. Go to **Secrets** tab → **Create Secret**
2. Create each secret individually:

   | Secret Name | Value |
   |-------------|--------|
   | `TWITTER_API_KEY` | Your Twitter API key |
   | `TWITTER_API_SECRET` | Your Twitter API secret |
   | `TWITTER_BEARER_TOKEN` | Your Twitter bearer token |
   | `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
   | `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
   | `OPENAI_API_KEY` | Your OpenAI API key |
   | `RSS_WEBHOOK_URL` | `AUTO_DETECT` |
   | `DATABASE_URL` | PostgreSQL connection string from Step 1 |
   | `OPERATION_MODE` | `webhook_only` |
   | `ENABLE_MEDIA_DOWNLOAD` | `false` |
   | `AI_MAX_TOKENS` | `150` |

### Step 3: Deploy Application

1. Click **Create Web Service**
2. **Deployment method**: Select **GitHub**
3. **Repository**: Choose your `dd_v3` repository
4. **Branch**: `main`
5. **Builder**: Select **Dockerfile**
6. **Dockerfile path**: `Dockerfile.prod`
7. **Environment variables**: Click **Bulk Edit** and paste:

```env
PORT=5000
DATABASE_URL={{ secret.DATABASE_URL }}
TWITTER_API_KEY={{ secret.TWITTER_API_KEY }}
TWITTER_API_SECRET={{ secret.TWITTER_API_SECRET }}
TWITTER_BEARER_TOKEN={{ secret.TWITTER_BEARER_TOKEN }}
TELEGRAM_BOT_TOKEN={{ secret.TELEGRAM_BOT_TOKEN }}
TELEGRAM_CHAT_ID={{ secret.TELEGRAM_CHAT_ID }}
OPENAI_API_KEY={{ secret.OPENAI_API_KEY }}
RSS_WEBHOOK_URL={{ secret.RSS_WEBHOOK_URL }}
OPERATION_MODE={{ secret.OPERATION_MODE }}
ENABLE_MEDIA_DOWNLOAD={{ secret.ENABLE_MEDIA_DOWNLOAD }}
AI_MAX_TOKENS={{ secret.AI_MAX_TOKENS }}
```

8. **Instance**: Select **Nano** (256MB RAM, 0.25 vCPU)
9. **Health check path**: `/health`
10. **App name**: `twitter-monitor`
11. **Service name**: `twitter-monitor-service`
12. Click **Deploy**

---

## Post-Deployment Steps

### 1. Verify Deployment

```bash
# Check service status
koyeb service get twitter-monitor-service

# View logs
koyeb service logs twitter-monitor-service --follow

# Check database connection
koyeb database get twitter-monitor-db
```

### 2. Configure RSS Webhooks

1. Your app will display the webhook URL in the startup logs
2. Go to RSS.app and configure webhook for your RSS feed:
   - Webhook URL: `https://your-app-url.koyeb.app/webhook/rss`
   - Method: POST
   - Content-Type: application/json

### 3. Test the Application

1. Visit `https://your-app-url.koyeb.app` to access the dashboard
2. Check `/api/stats` endpoint for data
3. Trigger an RSS webhook to test the pipeline

---

## Environment-Specific Features

### Automatic Webhook Detection
- **Development**: Detects ngrok URLs automatically
- **Production**: Uses Koyeb's `KOYEB_PUBLIC_DOMAIN` environment variable
- **Manual**: Fallback to localhost or custom URL

### Cost Optimization
- **Instance**: Nano (0.25 vCPU, 256MB RAM) = ~$29.76/month
- **Database**: Free tier (5 hours compute/month, 1GB storage)
- **Total estimated cost**: ~$1.61/month (assumes minimal database usage)

### Scaling Configuration
- **Min instances**: 1
- **Max instances**: 1
- **Auto-scaling**: Disabled for cost control
- **Sleep mode**: Enabled after 5 minutes of inactivity

---

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check database status
   koyeb database get twitter-monitor-db
   
   # Verify connection string format
   echo $DATABASE_URL
   ```

2. **Secret Not Found**
   ```bash
   # List all secrets
   koyeb secret list
   
   # Check secret interpolation syntax
   # Correct: {{ secret.SECRET_NAME }}
   # Wrong: ${{ secret.SECRET_NAME }}
   ```

3. **Build Failed**
   ```bash
   # Check build logs
   koyeb service logs twitter-monitor-service --deployment-id=<deployment-id>
   
   # Verify Dockerfile.prod exists in repository
   ```

4. **Health Check Failed**
   ```bash
   # Test health endpoint locally
   curl https://your-app-url.koyeb.app/health
   
   # Check application logs
   koyeb service logs twitter-monitor-service --follow
   ```

### Monitoring

```bash
# Service metrics
koyeb service metrics twitter-monitor-service

# Database metrics  
koyeb database metrics twitter-monitor-db

# Real-time logs
koyeb service logs twitter-monitor-service --follow --since=1h
```

---

## Next Steps

1. **Set up monitoring**: Configure alerts for service health
2. **Custom domain**: Add your own domain name
3. **Backup strategy**: Regular database backups
4. **Performance tuning**: Monitor resource usage and scale if needed

---

## CLI vs Web Interface Summary

| Feature | CLI | Web Interface |
|---------|-----|---------------|
| **Speed** | ⚡ Very Fast | 🐌 Slower |
| **Automation** | ✅ Scriptable | ❌ Manual |
| **Visibility** | 📊 Terminal logs | 👀 Visual feedback |
| **Repeatability** | ✅ Version controlled | ❌ Manual steps |
| **Learning curve** | 📈 Steeper | 📉 Gentler |

**Recommendation**: Use CLI for production deployments and automation. Use web interface for learning and one-off deployments. 