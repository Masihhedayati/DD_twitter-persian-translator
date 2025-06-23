# RSS.app + TwitterAPI.io Integration Guide

## Overview

This guide implements a clever workaround for X/Twitter's Free API webhook limitations by using RSS.app as a notification layer to trigger TwitterAPI.io polling.

## How It Works

```
Twitter Accounts → RSS.app → RSS Webhook → Your System → TwitterAPI.io → Process Tweets
```

**Benefits:**
- ✅ Works with X Free API (no premium webhook access needed)
- ✅ Near real-time notifications (RSS.app updates every 15-30 minutes)
- ✅ Reduces unnecessary API calls (only polls when new content detected)
- ✅ Can monitor keywords/topics in addition to users
- ✅ More reliable than constant polling

## Step-by-Step Implementation

### Phase 1: RSS.app Setup

#### 1.1 Create RSS.app Account
1. Visit [https://rss.app/](https://rss.app/)
2. Sign up for an account
3. Choose appropriate plan:
   - **Free**: 5 feeds, basic webhooks
   - **Pro**: 50 feeds, advanced webhooks, faster updates

#### 1.2 Create Twitter RSS Feeds
For each monitored user, create a Twitter RSS feed:

1. **Go to RSS Generator**: https://rss.app/rss-generator
2. **Enter Twitter URL**: `https://twitter.com/username` or `https://x.com/username`
3. **Generate Feed**: RSS.app will create a feed URL like `https://rss.app/feeds/12345.xml`
4. **Repeat for all monitored users**

**Example Users to Set Up:**
- `https://twitter.com/elonmusk` → RSS feed
- `https://twitter.com/naval` → RSS feed  
- `https://twitter.com/paulg` → RSS feed

#### 1.3 Configure RSS.app Webhooks
1. **Go to Feed Settings** for each created feed
2. **Enable Webhooks**:
   - Webhook URL: `https://your-domain.com/webhook/rss` (use ngrok URL for development)
   - Method: POST
   - Content Type: application/json
3. **Set Webhook Secret** (optional but recommended for security)
4. **Test webhook** to ensure connectivity

### Phase 2: Development Environment Setup

#### 2.1 Update Environment Configuration
The RSS webhook secret has been added to your environment:

```bash
# In .env.development
RSS_WEBHOOK_SECRET=your_rss_webhook_secret_here
```

#### 2.2 Start Development Environment
```bash
# Start development with ngrok
./scripts/start-dev.sh

# Your system will be available at:
# - Local: http://localhost:5001
# - ngrok: https://abc123.ngrok.io (use this for RSS.app webhooks)
```

#### 2.3 Configure RSS.app Webhook URLs
Use your ngrok URL for webhook configuration:
```
https://abc123.ngrok.io/webhook/rss
```

### Phase 3: Testing the Integration

#### 3.1 Test RSS Webhook Endpoint
```bash
# Test the RSS webhook endpoint
curl -X POST http://localhost:5001/webhook/rss/test \
  -H "Content-Type: application/json"
```

#### 3.2 Monitor RSS Webhook Activity
```bash
# Check RSS webhook statistics
curl http://localhost:5001/api/rss/stats
```

#### 3.3 Monitor Logs
```bash
# Watch development logs
tail -f logs/app.log | grep -E "(RSS|webhook|polling)"
```

### Phase 4: Production Deployment

#### 4.1 Update Production Environment
Add to your production `.env` file:
```bash
RSS_WEBHOOK_SECRET=your_secure_webhook_secret_here
```

#### 4.2 Update RSS.app Webhook URLs
Change from ngrok URL to production URL:
```
https://your-production-domain.com/webhook/rss
```

#### 4.3 Deploy Updated Code
```bash
# Deploy with RSS webhook support
./deploy.sh
```

## API Endpoints

### RSS Webhook Endpoints

#### `POST /webhook/rss`
Receives RSS.app webhook notifications
- **Headers**: `X-RSS-Signature` or `X-Hub-Signature-256` (for verification)
- **Body**: RSS webhook payload
- **Response**: Processing result

#### `POST /webhook/rss/test`
Test RSS webhook functionality (development only)
- **Body**: Not required (uses sample data)
- **Response**: Test processing result

#### `GET /api/rss/stats`
Get RSS webhook statistics
- **Response**: Webhook activity stats, rate limiting info

## RSS Webhook Payload Examples

### Example 1: RSS.app Standard Format
```json
{
  "item": {
    "title": "New tweet from @elonmusk",
    "link": "https://twitter.com/elonmusk/status/1234567890123456789",
    "description": "Tweet content here...",
    "published": "2023-10-05T00:37:15Z",
    "guid": "https://twitter.com/elonmusk/status/1234567890123456789"
  },
  "feed": {
    "title": "Twitter - @elonmusk",
    "url": "https://rss.app/feeds/12345.xml"
  }
}
```

### Example 2: Alternative Format
```json
{
  "entry": {
    "title": "@naval: New tweet about...",
    "url": "https://x.com/naval/status/9876543210987654321",
    "summary": "Tweet content...",
    "pubDate": "Thu, 05 Oct 2023 00:37:15 GMT"
  }
}
```

## How RSS Webhook Handler Works

1. **Receives Webhook**: RSS.app sends webhook when new RSS item detected
2. **Parses Username**: Extracts Twitter username from URL/title/description
3. **Rate Limiting**: Prevents excessive polling (5-minute minimum interval per user)
4. **Triggers Polling**: Uses TwitterAPI.io to fetch latest tweets for that user
5. **Process Tweets**: Stores new tweets, runs AI analysis, sends notifications

## Rate Limiting & Performance

### Built-in Rate Limiting
- **Minimum Interval**: 5 minutes between polls per user
- **Prevents Spam**: Multiple RSS notifications won't trigger excessive API calls
- **Intelligent Caching**: Tracks last poll time per user

### Performance Optimizations
- Only polls when RSS webhook received (not continuous polling)
- Fetches limited number of tweets (10) per trigger
- Deduplicates tweets already in database
- Processes only new tweets through AI pipeline

## Troubleshooting

### Common Issues

#### 1. RSS Webhook Not Received
**Symptoms**: No webhook calls in logs
**Solutions**:
- Check ngrok tunnel is active: `http://localhost:4040`
- Verify RSS.app webhook URL configuration
- Test webhook endpoint manually
- Check firewall/network restrictions

#### 2. Username Not Extracted
**Symptoms**: "No username found in RSS item" error
**Solutions**:
- Verify RSS feed contains Twitter/X URLs
- Check RSS.app feed configuration
- Test with sample webhook payload
- Add debug logging to `_parse_rss_webhook`

#### 3. Rate Limiting Too Aggressive
**Symptoms**: "Rate limited" responses
**Solutions**:
- Adjust `min_poll_interval` in `RSSWebhookHandler`
- Check if multiple RSS feeds for same user
- Monitor `last_poll_time` in webhook stats

#### 4. No New Tweets Found
**Symptoms**: "No tweets found" or "No new tweets"
**Solutions**:
- Verify TwitterAPI.io API key and limits
- Check if user account exists and is public
- Test TwitterAPI.io directly
- Check database for existing tweets

### Debug Commands

```bash
# Test RSS webhook with sample data
curl -X POST http://localhost:5001/webhook/rss/test

# Check RSS webhook statistics
curl http://localhost:5001/api/rss/stats

# Monitor webhook activity
tail -f logs/app.log | grep "RSS webhook"

# Test TwitterAPI.io connectivity
curl -X POST http://localhost:5001/api/poll/force
```

## Security Considerations

### Webhook Signature Verification
- RSS.app sends signed webhooks with secret
- Handler verifies HMAC-SHA256 signature
- Rejects unsigned/invalid webhooks

### Environment Security
- Store RSS webhook secret in environment variables
- Use different secrets for development/production
- Rotate secrets periodically

### Rate Limiting Protection
- Built-in rate limiting prevents abuse
- Monitors per-user polling frequency
- Logs suspicious activity

## Monitoring & Maintenance

### Key Metrics to Monitor
- RSS webhook success rate
- Polling trigger frequency
- New tweets discovered per webhook
- API call efficiency (webhooks vs continuous polling)

### Maintenance Tasks
- Monitor RSS.app feed health
- Update webhook URLs when domains change
- Review and adjust rate limiting thresholds
- Clean up old webhook statistics

## Comparison with Other Approaches

| Approach | Pros | Cons | Cost |
|----------|------|------|------|
| **RSS.app Webhooks** | ✅ Works with Free API<br>✅ Near real-time<br>✅ Efficient | ⚠️ 15-30min delay<br>⚠️ External dependency | Free-$29/mo |
| **Continuous Polling** | ✅ Full control<br>✅ Real-time | ❌ High API usage<br>❌ Inefficient | API costs |
| **Twitter Webhooks** | ✅ Real-time<br>✅ Efficient | ❌ Requires Premium API | $100+/mo |

## Future Enhancements

### Potential Improvements
1. **Multiple RSS Providers**: Support for other RSS services
2. **Keyword Monitoring**: RSS feeds for specific hashtags/keywords
3. **Batch Processing**: Group multiple webhook triggers
4. **Analytics Dashboard**: RSS webhook performance metrics
5. **Auto-Recovery**: Automatic RSS feed health checks

### Advanced Features
- **Smart Polling**: Adjust frequency based on user activity
- **Webhook Retry Logic**: Handle failed webhook deliveries
- **Feed Health Monitoring**: Alert when RSS feeds break
- **Multi-Account Support**: Different RSS configurations per user

## Conclusion

This RSS.app integration provides an elegant solution for near real-time Twitter monitoring without requiring premium API access. The approach is:

- **Cost-effective**: Works with free X API + affordable RSS.app
- **Reliable**: Reduces API calls while maintaining responsiveness  
- **Scalable**: Easy to add new users and monitoring targets
- **Maintainable**: Clear separation of concerns and robust error handling

The system will automatically trigger data pulling and processing when RSS.app detects new content, providing an efficient hybrid approach between polling and webhooks. 