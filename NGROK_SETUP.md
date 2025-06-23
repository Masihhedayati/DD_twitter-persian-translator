# 🔗 ngrok Setup Guide for Local Development

This guide helps you set up ngrok for local webhook development with the Twitter monitoring system.

## 📋 Prerequisites

- macOS, Linux, or Windows
- Python 3.8+
- Twitter API access with webhook permissions
- Internet connection

## 🚀 One-Time Setup

### 1. Install ngrok

**macOS:**
```bash
brew install ngrok
```

**Linux (Ubuntu/Debian):**
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

**Windows:**
- Download from: https://ngrok.com/download
- Extract and add to PATH

### 2. Create ngrok Account

1. Sign up at: https://dashboard.ngrok.com/signup
2. Get your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure ngrok:
```bash
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

### 3. Create Development Environment

```bash
# Copy environment template
cp env.development.example .env.development

# Edit with your actual API keys
nano .env.development  # or your preferred editor
```

### 4. Test Installation

```bash
# Test ngrok
ngrok http 8080 --log=stdout
# You should see a forwarding URL like: https://abc123.ngrok-free.app
# Press Ctrl+C to stop
```

## 🏃‍♂️ Daily Development Workflow

### Start Development Environment
```bash
./scripts/start-dev.sh
```

This single command:
- ✅ Loads your development environment
- ✅ Starts ngrok tunnel on port 5001
- ✅ Creates development database
- ✅ Starts Flask app with hot reload
- ✅ Shows all important URLs

### Stop Development Environment
```bash
./scripts/stop-dev.sh
```

Or simply press `Ctrl+C` in the terminal.

## 📊 Development URLs

After running `./scripts/start-dev.sh`, you'll see:

- **Local Dashboard:** http://localhost:5001
- **Public Dashboard:** https://your-ngrok-url.ngrok-free.app
- **Webhook URL:** https://your-ngrok-url.ngrok-free.app/webhook/twitter
- **ngrok Inspector:** http://localhost:4040

## 🔧 Twitter Webhook Configuration

### For Development Testing:
1. Use the webhook URL from the script output
2. Configure in Twitter Developer Portal:
   - Webhook URL: `https://your-ngrok-url.ngrok-free.app/webhook/twitter`
   - Environment: Development

### For Production:
- Keep using your Koyeb URL: `https://your-app.koyeb.app/webhook/twitter`

## 🛠 Troubleshooting

### ngrok Not Starting
```bash
# Check if ngrok is installed
ngrok version

# Check authentication
ngrok config check
```

### Port Already in Use
```bash
# Kill processes on port 5001
lsof -ti:5001 | xargs kill -9

# Or change PORT in .env.development
PORT=5002
```

### Webhook Not Receiving Events
1. Check ngrok inspector: http://localhost:4040
2. Verify webhook URL in Twitter Developer Portal
3. Check webhook secret matches in `.env.development`

### Database Issues
```bash
# Remove development database to reset
rm dev_tweets.db

# Restart development environment
./scripts/start-dev.sh
```

## 📝 Tips

- **ngrok URLs change** on restart unless you have a paid plan
- **Development database** (`dev_tweets.db`) is separate from production
- **Hot reload** works - just save your files and Flask restarts
- **ngrok inspector** shows all webhook requests for debugging
- **Production unaffected** - uses separate database and environment

## 🔄 Deployment Workflow

1. **Develop locally** with ngrok
2. **Test thoroughly** using public ngrok URL
3. **Commit changes** when ready
4. **Deploy to production** with `./deploy.sh`

Your production deployment on Koyeb remains completely separate and unaffected by local development. 