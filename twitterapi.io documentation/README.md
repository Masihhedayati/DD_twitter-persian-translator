# TwitterAPI.io Documentation

Complete documentation for the TwitterAPI.io API service - a cost-effective Twitter data access solution.

## 📁 Documentation Structure

| File | Description |
|------|-------------|
| [00-Overview.md](./00-Overview.md) | API overview, features, pricing, and categories |
| [01-Authentication.md](./01-Authentication.md) | Authentication setup and examples |
| [02-User-Endpoints.md](./02-User-Endpoints.md) | User profile and relationship endpoints |
| [03-Tweet-Endpoints.md](./03-Tweet-Endpoints.md) | Tweet data and interaction endpoints |
| [04-Communities-Endpoints.md](./04-Communities-Endpoints.md) | Twitter Communities API endpoints |
| [05-List-Endpoints.md](./05-List-Endpoints.md) | Twitter Lists API endpoints |
| [06-Trend-Endpoints.md](./06-Trend-Endpoints.md) | Trending topics endpoints |
| [07-Login-and-My-Account-Endpoints.md](./07-Login-and-My-Account-Endpoints.md) | Authentication and account endpoints |
| [08-Tweet-Action-Endpoints.md](./08-Tweet-Action-Endpoints.md) | Tweet creation and interaction endpoints |
| [09-Webhook-Websocket-Filter-Rules.md](./09-Webhook-Websocket-Filter-Rules.md) | Real-time filtering and monitoring |
| [10-Complete-API-Reference.md](./10-Complete-API-Reference.md) | Complete API reference and quick lookup |

## 🚀 Quick Start

### 1. Authentication
```bash
# Get your API key from https://twitterapi.io/dashboard
curl --location 'https://api.twitterapi.io/twitter/user/info?userName=example' \
--header 'x-api-key: YOUR_API_KEY'
```

### 2. Basic User Info
```python
import requests

url = 'https://api.twitterapi.io/twitter/user/info?userName=elonmusk'
headers = {'x-api-key': 'YOUR_API_KEY'}
response = requests.get(url, headers=headers)
print(response.json())
```

### 3. Search Tweets
```javascript
const headers = { 'x-api-key': 'YOUR_API_KEY' };

fetch('https://api.twitterapi.io/twitter/tweet/advanced_search?query=openai', {
    headers: headers
})
.then(response => response.json())
.then(data => console.log(data));
```

## 📊 Key Features

- **Cost-Effective**: 96% cheaper than official Twitter API
- **High Performance**: 700ms average response time
- **Scalable**: Up to 200 QPS per client
- **Comprehensive**: 40+ endpoints covering all Twitter data types
- **Real-time**: Webhook/websocket filtering for live monitoring

## 💰 Pricing Summary

| Category | Price |
|----------|-------|
| Tweets | $0.15/1k tweets |
| User Profiles | $0.18/1k profiles |
| Followers | $0.15/1k followers |
| Tweet Actions | $0.001 per action |
| Login | $0.003 per step |
| Minimum Charge | $0.00015 per request |

## 🔗 API Categories

### User Data
- User profiles and information
- Followers and following lists
- User search and relationships
- User mentions and activity

### Tweet Data
- Tweet content and metadata
- Replies, quotes, and retweets
- Thread context and conversations
- Advanced search capabilities

### Interactive Features
- Communities data
- Twitter Lists
- Trending topics
- Real-time filtering

### Actions (Requires Login)
- Post tweets and replies
- Like and retweet content
- Upload images
- Account management

## 🛠️ Implementation Examples

### Get User Followers
```python
def get_user_followers(username, api_key, page_size=200):
    url = f'https://api.twitterapi.io/twitter/user/followers'
    headers = {'x-api-key': api_key}
    params = {'userName': username, 'pageSize': page_size}
    
    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

### Tweet Filtering Rule
```python
def create_filter_rule(tag, filter_value, interval, api_key):
    url = 'https://api.twitterapi.io/oapi/tweet_filter/add_rule'
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }
    data = {
        'tag': tag,
        'value': filter_value,
        'interval_seconds': interval
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()
```

### Pagination Example
```python
def get_all_tweets_from_user(username, api_key):
    url = 'https://api.twitterapi.io/twitter/user/last_tweets'
    headers = {'x-api-key': api_key}
    params = {'userName': username, 'cursor': ''}
    
    all_tweets = []
    
    while True:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        all_tweets.extend(data['tweets'])
        
        if not data['has_next_page']:
            break
            
        params['cursor'] = data['next_cursor']
    
    return all_tweets
```

## 🔒 Security Best Practices

1. **API Key Security**
   - Never expose API keys in client-side code
   - Use environment variables for API keys
   - Rotate API keys regularly

2. **Rate Limiting**
   - Implement exponential backoff for retries
   - Monitor QPS usage (max 200 per client)
   - Cache responses when appropriate

3. **Error Handling**
   - Always check response status
   - Implement proper error recovery
   - Log errors for debugging

## 📈 Optimization Tips

### Cost Optimization
- Use bulk endpoints for multiple users (100+ users)
- Implement efficient pagination
- Cache frequently accessed data
- Filter results client-side when possible

### Performance Optimization
- Use `userId` instead of `userName` for stability
- Implement concurrent requests where appropriate
- Use appropriate page sizes for your use case
- Monitor response times and adjust accordingly

## 🆘 Support Resources

- **Documentation**: [docs.twitterapi.io](https://docs.twitterapi.io)
- **Dashboard**: [twitterapi.io/dashboard](https://twitterapi.io/dashboard)
- **Student Discounts**: Available for educational institutions
- **API Status**: Monitor performance and availability

## 📋 Common Use Cases

### Social Media Monitoring
- Track brand mentions across Twitter
- Monitor competitor activity
- Analyze sentiment and engagement

### Research and Analytics
- Collect tweet data for analysis
- Study user behavior patterns
- Track trending topics and hashtags

### Content Creation
- Find popular content in your niche
- Identify influencers and thought leaders
- Monitor engagement on your posts

### Customer Service
- Track support mentions
- Monitor customer feedback
- Automate response workflows

## 🔄 Migration Guide

If migrating from official Twitter API:
1. Replace authentication headers with `x-api-key`
2. Update base URLs to `api.twitterapi.io`
3. Adjust pagination parameters as needed
4. Review pricing model differences
5. Test thoroughly in development environment

## ⚖️ Terms and Compliance

- Follow Twitter's terms of service
- Respect rate limits and usage guidelines
- Implement proper attribution where required
- Consider user privacy and data protection laws

---

*Last Updated: December 2024*
*API Version: Latest*
*Documentation scraped from: docs.twitterapi.io*