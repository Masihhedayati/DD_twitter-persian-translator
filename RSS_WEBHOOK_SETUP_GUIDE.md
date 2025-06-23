# RSS.app + TwitterAPI.io Integration - Complete Setup Guide

## 🎯 Overview

This guide shows you how to set up RSS.app webhooks to trigger your TwitterAPI.io system when new tweets are posted. This works around X/Twitter Free API limitations by using RSS.app as a notification layer.

## ✅ System Status: FULLY IMPLEMENTED & TESTED

**What's Working:**
- ✅ RSS webhook handler processing webhooks correctly
- ✅ Username extraction from RSS feeds and webhook data  
- ✅ TwitterAPI.io integration fetching tweets on webhook triggers
- ✅ Database storage of new tweets
- ✅ AI processing queue integration
- ✅ Rate limiting (5-minute intervals per user)
- ✅ Telegram notifications
- ✅ Permanent ngrok tunnel for webhooks

**Current Webhook URL:** `https://761a-2a00-23c7-e53c-4801-e805-be6d-3581-608.ngrok-free.app/webhook/rss`

## 📋 Step-by-Step Setup

### Phase 1: RSS.app Account & Feed Setup

#### 1. Create RSS.app Account
1. Go to [https://rss.app/](https://rss.app/)
2. Sign up for an account
3. Choose a plan that supports webhooks (check their pricing page)

#### 2. Create Twitter RSS Feeds
For each user you want to monitor (currently: `elonmusk`, `naval`, `paulg`):

1. **Add New Feed:**
   - Click \"Create Feed\" or \"Add Feed\"
   - Choose \"Twitter\" as source
   - Enter the Twitter username (e.g., `elonmusk`)
   - Or use Twitter URL: `https://twitter.com/elonmusk`

2. **Configure Feed Settings:**
   - Set update frequency (RSS.app typically checks every 15-30 minutes)
   - Enable the feed
   - Note the RSS feed URL for reference

3. **Repeat for all monitored users:**
   - `@elonmusk` → RSS feed
   - `@naval` → RSS feed  
   - `@paulg` → RSS feed

### Phase 2: Webhook Configuration

#### 3. Configure RSS.app Webhooks
1. **Find Webhook Settings:**
   - In RSS.app dashboard, look for \"Webhooks\", \"Integrations\", or \"Notifications\"
   - This might be under \"Settings\" or \"Advanced\" section

2. **Add Webhook URL:**
   ```
   https://761a-2a00-23c7-e53c-4801-e805-be6d-3581-608.ngrok-free.app/webhook/rss
   ```

3. **Configure Webhook Triggers:**
   - Set to trigger on \"New Items\" or \"New Posts\"
   - Apply to all your Twitter feeds
   - Choose HTTP POST method
   - Set Content-Type to `application/json`

4. **Test Webhook (if available):**
   - Many services provide a \"Test Webhook\" button
   - Use this to verify connectivity

### Phase 3: System Startup & Testing

#### 4. Start Your System
1. **Start the permanent tunnel:**
   ```bash
   ./scripts/start-permanent-tunnel.sh
   ```

2. **Start your development environment:**
   ```bash
   # In a new terminal
   python -c \"
   import os
   with open('.env.development', 'r') as f:
       for line in f:
           line = line.strip()
           if line and not line.startswith('#') and '=' in line:
               key, value = line.split('=', 1)
               os.environ[key] = value.strip('\\\"')
   os.environ['PORT'] = '5001'
   import subprocess, sys
   subprocess.run([sys.executable, 'app.py'])
   \"
   ```

#### 5. Test the Complete System
1. **Test RSS webhook endpoint:**
   ```bash
   curl -X POST https://761a-2a00-23c7-e53c-4801-e805-be6d-3581-608.ngrok-free.app/webhook/rss/test \\
        -H \"Content-Type: application/json\"
   ```

2. **Check webhook stats:**
   ```bash
   curl https://761a-2a00-23c7-e53c-4801-e805-be6d-3581-608.ngrok-free.app/api/rss/stats
   ```

3. **Monitor ngrok dashboard:**
   - Open http://localhost:4040
   - Watch for incoming webhook requests

### Phase 4: Production Deployment

#### 6. For Production Use
1. **Get a permanent domain:**
   - Upgrade to ngrok paid plan for static domains
   - Or deploy to a VPS with permanent URL
   - Or use services like Railway, Heroku, etc.

2. **Update RSS.app webhook URL** to your permanent domain

3. **Monitor logs:**
   ```bash
   tail -f logs/app.log
   ```

## 🔧 System Architecture

```
Twitter → RSS.app → RSS Webhook → Your System → TwitterAPI.io → AI Processing → Telegram
```

**Flow:**
1. User posts on Twitter
2. RSS.app detects new post (15-30 min delay)
3. RSS.app sends webhook to your system
4. Your system extracts username from webhook
5. System calls TwitterAPI.io to fetch latest tweets
6. New tweets are stored in database
7. AI processing happens in background
8. Telegram notifications sent

## 📊 Monitoring & Troubleshooting

### Check System Status
```bash
# Check RSS webhook stats
curl https://YOUR-NGROK-URL/api/rss/stats

# Check system health
curl https://YOUR-NGROK-URL/api/health

# Check recent tweets
curl https://YOUR-NGROK-URL/api/tweets/recent
```

### Common Issues

**1. Webhook not triggering:**
- Check RSS.app webhook configuration
- Verify ngrok tunnel is running
- Check ngrok dashboard for incoming requests

**2. No tweets fetched:**
- Verify TwitterAPI.io credentials
- Check if user is in monitored list
- Review rate limiting (5-minute minimum intervals)

**3. AI processing not working:**
- Check OpenAI API key
- Monitor AI processing queue
- Review logs for errors

### Log Files
- Application logs: Check terminal output or log files
- ngrok logs: Check ngrok dashboard at http://localhost:4040
- RSS.app logs: Check RSS.app dashboard

## 🎉 Success Indicators

You'll know it's working when:
- ✅ RSS.app shows active feeds updating
- ✅ Webhook requests appear in ngrok dashboard
- ✅ New tweets appear in your database
- ✅ Telegram notifications are sent
- ✅ AI processing happens in background

## 🔄 Daily Workflow

1. **Morning:** Check if ngrok tunnel is still running
2. **Ongoing:** Monitor Telegram for new tweet notifications
3. **Evening:** Review any errors in logs
4. **Weekly:** Check RSS.app feed health

## 📈 Advantages of This Setup

- ✅ **Works with X Free API** (no premium webhook access needed)
- ✅ **Near real-time** notifications (15-30 minute RSS delays)
- ✅ **Reduces API calls** (only polls when RSS detects new content)
- ✅ **Reliable** (RSS.app handles the Twitter monitoring)
- ✅ **Scalable** (can add more users/keywords easily)
- ✅ **Cost-effective** (uses existing free/low-cost services)

## 🚀 Next Steps

After successful setup:
1. **Add more Twitter users** to monitor
2. **Configure keyword-based RSS feeds** for topics
3. **Set up monitoring alerts** for system health
4. **Optimize AI processing** prompts
5. **Add more notification channels** (Discord, Slack, etc.)

---

**Need Help?** 
- Check the ngrok dashboard: http://localhost:4040
- Review RSS.app documentation
- Monitor system logs for detailed error messages 