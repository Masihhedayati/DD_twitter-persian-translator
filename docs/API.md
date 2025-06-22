# Twitter Monitor - API Documentation

## 🔗 **API ENDPOINTS REFERENCE**

This document provides comprehensive documentation for all API endpoints in the Twitter Monitoring System.

**Base URL**: `http://localhost:5001` (default)

---

## 📊 **CORE API ENDPOINTS**

### **GET /health**
Health check endpoint for monitoring system status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-12-22T10:00:00.000Z",
  "version": "1.0.0"
}
```

**Status Codes:**
- `200`: System is healthy
- `500`: System error

---

### **GET /api/tweets**
Retrieve tweets with filtering and search capabilities.

**Query Parameters:**
- `limit` (int, optional): Number of tweets to return (default: 50)
- `offset` (int, optional): Number of tweets to skip (default: 0)
- `username` (string, optional): Filter by specific username
- `q` (string, optional): Search query for tweet content
- `filter` (string, optional): Filter type (`all`, `images`, `videos`, `ai`)
- `since` (string, optional): ISO timestamp for real-time updates

**Example Requests:**
```bash
# Get latest 20 tweets
curl "http://localhost:5001/api/tweets?limit=20"

# Filter by username
curl "http://localhost:5001/api/tweets?username=elonmusk"

# Search for specific content
curl "http://localhost:5001/api/tweets?q=AI&filter=ai"

# Get tweets since timestamp
curl "http://localhost:5001/api/tweets?since=2024-12-22T10:00:00Z"
```

**Response:**
```json
{
  "tweets": [
    {
      "id": "1234567890",
      "username": "elonmusk",
      "display_name": "Elon Musk",
      "content": "Tweet content here...",
      "created_at": "2024-12-22T10:00:00Z",
      "detected_at": "2024-12-22T10:01:00Z",
      "likes_count": 1500,
      "retweets_count": 300,
      "replies_count": 50,
      "ai_processed": true,
      "telegram_sent": true,
      "media": [
        {
          "id": 1,
          "media_type": "image",
          "original_url": "https://...",
          "local_path": "./media/2024/12/22/image.jpg",
          "download_status": "completed"
        }
      ],
      "ai_analysis": {
        "id": 1,
        "result": "This tweet discusses space technology...",
        "model_used": "gpt-3.5-turbo",
        "tokens_used": 45,
        "created_at": "2024-12-22T10:02:00Z"
      },
      "has_media": true,
      "has_ai_analysis": true
    }
  ],
  "count": 1,
  "status": "success",
  "filters_applied": {
    "username": null,
    "search_query": null,
    "filter_type": "all",
    "since": null
  }
}
```

---

### **GET /api/statistics**
Get comprehensive system statistics and metrics.

**Response:**
```json
{
  "status": "success",
  "statistics": {
    "database": {
      "total_tweets": 1250,
      "media_files": 340,
      "ai_processed": 1180,
      "notifications_sent": 890,
      "users_monitored": 3
    },
    "scheduler": {
      "status": "running",
      "last_poll": "2024-12-22T10:00:00Z",
      "poll_count": 1440,
      "errors_count": 2,
      "tweets_discovered": 15,
      "uptime_hours": 24.5
    },
    "ai_processing": {
      "status": "active",
      "total_processed": 1180,
      "avg_processing_time": 2.3,
      "tokens_used_today": 45000,
      "cost_estimate_today": 0.68,
      "queue_size": 3
    },
    "notifications": {
      "status": "enabled",
      "sent_today": 25,
      "success_rate": 98.5,
      "last_sent": "2024-12-22T09:58:00Z",
      "queue_size": 1
    },
    "system": {
      "memory_usage_mb": 145,
      "cpu_usage_percent": 12.5,
      "disk_usage_gb": 0.8,
      "api_calls_today": 1200,
      "rate_limit_hits": 0
    }
  },
  "timestamp": "2024-12-22T10:00:00Z"
}
```

---

### **GET /api/status**
Get detailed system status information.

**Response:**
```json
{
  "status": "success",
  "system_status": {
    "scheduler": {
      "running": true,
      "last_poll": "2024-12-22T10:00:00Z",
      "next_poll": "2024-12-22T10:01:00Z",
      "error_count": 0
    },
    "ai_processor": {
      "active": true,
      "queue_size": 3,
      "processing": false
    },
    "telegram_notifier": {
      "enabled": true,
      "queue_size": 1,
      "last_notification": "2024-12-22T09:58:00Z"
    },
    "database": {
      "connected": true,
      "size_mb": 45.2,
      "last_backup": "2024-12-21T00:00:00Z"
    }
  },
  "health": "healthy",
  "uptime": "24h 30m",
  "timestamp": "2024-12-22T10:00:00Z"
}
```

---

## ⚙️ **CONFIGURATION API ENDPOINTS**

### **GET /api/settings**
Retrieve current system configuration.

**Response:**
```json
{
  "status": "success",
  "settings": {
    "monitoring": {
      "users": ["elonmusk", "naval", "paulg"],
      "check_interval": 60,
      "enabled": true
    },
    "ai_processing": {
      "enabled": true,
      "model": "gpt-3.5-turbo",
      "batch_size": 5,
      "processing_interval": 120
    },
    "notifications": {
      "enabled": true,
      "ai_processed_only": true,
      "delay": 10
    },
    "system": {
      "log_level": "INFO",
      "port": 5001,
      "debug": false
    }
  }
}
```

### **POST /api/settings**
Update system configuration.

**Request Body:**
```json
{
  "monitoring": {
    "users": ["elonmusk", "naval", "balajis"],
    "check_interval": 30
  },
  "ai_processing": {
    "batch_size": 10
  },
  "notifications": {
    "delay": 5
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Settings updated successfully",
  "updated_settings": {
    "monitoring.users": "3 users configured",
    "monitoring.check_interval": "30 seconds",
    "ai_processing.batch_size": 10,
    "notifications.delay": 5
  }
}
```

---

## 🎛️ **CONTROL API ENDPOINTS**

### **POST /api/poll/force**
Force immediate polling of Twitter feeds.

**Response:**
```json
{
  "status": "success",
  "message": "Forced polling initiated",
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **POST /api/ai/force**
Force immediate AI processing of queued tweets.

**Response:**
```json
{
  "status": "success",
  "message": "Forced AI processing initiated",
  "queue_size": 5,
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **POST /api/notifications/send**
Force sending of queued notifications.

**Response:**
```json
{
  "status": "success",
  "message": "Notifications sent",
  "sent_count": 3,
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **POST /api/notifications/pause**
Pause notification system.

**Response:**
```json
{
  "status": "success",
  "message": "Notifications paused",
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **POST /api/notifications/resume**
Resume notification system.

**Response:**
```json
{
  "status": "success",
  "message": "Notifications resumed",
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **POST /api/system/restart**
Restart core system components.

**Response:**
```json
{
  "status": "success",
  "message": "System restart initiated",
  "components_restarted": ["scheduler", "ai_processor", "notifier"],
  "timestamp": "2024-12-22T10:00:00Z"
}
```

---

## 📈 **ANALYTICS API ENDPOINTS**

### **GET /api/statistics/detailed**
Get detailed system analytics and performance metrics.

**Response:**
```json
{
  "status": "success",
  "detailed_statistics": {
    "performance": {
      "avg_tweet_processing_time": 2.3,
      "avg_ai_processing_time": 1.8,
      "avg_notification_time": 0.5,
      "api_response_time": 150,
      "database_query_time": 25
    },
    "costs": {
      "openai_tokens_today": 45000,
      "estimated_cost_today": 0.68,
      "estimated_monthly_cost": 20.40,
      "twitter_api_calls": 1200
    },
    "usage_patterns": {
      "peak_hours": ["09:00", "13:00", "18:00"],
      "avg_tweets_per_hour": 52,
      "most_active_user": "elonmusk",
      "busiest_day": "Monday"
    },
    "errors": {
      "twitter_api_errors": 2,
      "openai_api_errors": 1,
      "telegram_errors": 0,
      "database_errors": 0,
      "last_error": "2024-12-22T08:30:00Z"
    }
  },
  "timestamp": "2024-12-22T10:00:00Z"
}
```

### **GET /api/errors**
Get comprehensive error statistics and logs.

**Response:**
```json
{
  "status": "success",
  "error_statistics": {
    "total_errors": 15,
    "error_categories": {
      "api_error": 8,
      "network_error": 4,
      "database_error": 2,
      "processing_error": 1
    },
    "recent_errors": [
      {
        "timestamp": "2024-12-22T09:45:00Z",
        "component": "twitter_client",
        "category": "api_error",
        "severity": "medium",
        "message": "Rate limit temporarily exceeded",
        "resolved": true
      }
    ],
    "component_health": {
      "twitter_client": "healthy",
      "ai_processor": "healthy",
      "telegram_notifier": "healthy",
      "database": "healthy"
    }
  },
  "timestamp": "2024-12-22T10:00:00Z"
}
```

---

## 🔒 **AUTHENTICATION & SECURITY**

### Rate Limiting
All API endpoints are rate-limited to prevent abuse:
- **Default limit**: 100 requests per minute per IP
- **Authentication**: Currently no authentication required for local deployment
- **Production**: Consider implementing API key authentication

### CORS Headers
The API includes appropriate CORS headers for web client access:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## 📝 **ERROR RESPONSES**

### Standard Error Format
```json
{
  "status": "error",
  "error": "Error description",
  "error_code": "ERROR_TYPE",
  "timestamp": "2024-12-22T10:00:00Z",
  "request_id": "req_123456"
}
```

### Common HTTP Status Codes
- **200**: Success
- **400**: Bad Request (invalid parameters)
- **404**: Not Found (endpoint doesn't exist)
- **429**: Too Many Requests (rate limited)
- **500**: Internal Server Error
- **503**: Service Unavailable (system maintenance)

---

## 🚀 **USAGE EXAMPLES**

### JavaScript/Fetch
```javascript
// Get latest tweets
const response = await fetch('http://localhost:5001/api/tweets?limit=10');
const data = await response.json();
console.log(data.tweets);

// Update settings
const updateResponse = await fetch('http://localhost:5001/api/settings', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    monitoring: { check_interval: 30 }
  })
});
```

### Python/Requests
```python
import requests

# Get system statistics
response = requests.get('http://localhost:5001/api/statistics')
stats = response.json()
print(f"Total tweets: {stats['statistics']['database']['total_tweets']}")

# Force AI processing
requests.post('http://localhost:5001/api/ai/force')
```

### cURL Examples
```bash
# Health check
curl http://localhost:5001/health

# Get tweets with filters
curl "http://localhost:5001/api/tweets?username=elonmusk&limit=5"

# Update configuration
curl -X POST http://localhost:5001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"notifications": {"delay": 15}}'

# Force operations
curl -X POST http://localhost:5001/api/poll/force
```

---

## 🔍 **MONITORING & DEBUGGING**

### Real-time Updates
Use the `since` parameter to get real-time updates:
```bash
# Get tweets since last check
curl "http://localhost:5001/api/tweets?since=2024-12-22T10:00:00Z&limit=100"
```

### Performance Monitoring
Monitor API performance with the statistics endpoint:
```bash
# Check processing times
curl http://localhost:5001/api/statistics/detailed | jq '.detailed_statistics.performance'
```

### Health Monitoring
Set up automated health checks:
```bash
#!/bin/bash
# health_check.sh
if curl -f http://localhost:5001/health > /dev/null 2>&1; then
  echo "✅ System healthy"
else
  echo "❌ System down - alerting admin"
  # Send alert notification
fi
```

---

## 📊 **INTEGRATION EXAMPLES**

### Dashboard Integration
```javascript
// Real-time dashboard updates
async function updateDashboard() {
  const [tweets, stats] = await Promise.all([
    fetch('/api/tweets?limit=5'),
    fetch('/api/statistics')
  ]);
  
  const tweetData = await tweets.json();
  const statsData = await stats.json();
  
  updateTweetsTable(tweetData.tweets);
  updateStatsCards(statsData.statistics);
}

setInterval(updateDashboard, 30000); // Update every 30 seconds
```

### Alerting Integration
```python
# Slack/Discord webhook integration
import requests

def check_system_health():
    response = requests.get('http://localhost:5001/api/status')
    status = response.json()
    
    if status['health'] != 'healthy':
        send_alert(f"🚨 Twitter Monitor unhealthy: {status['system_status']}")
    
    # Check error rates
    errors = requests.get('http://localhost:5001/api/errors').json()
    if errors['error_statistics']['total_errors'] > 50:
        send_alert(f"⚠️ High error rate: {errors['error_statistics']['total_errors']} errors")
```

This comprehensive API documentation provides everything needed to integrate with and monitor the Twitter Monitoring System programmatically. 