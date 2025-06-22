# TwitterAPI.io Documentation Overview

## API Overview
TwitterAPI.io is a comprehensive Twitter data API service that provides access to Twitter data at significantly reduced costs compared to official Twitter API services.

### Key Features
- **Stability**: Proven with over 1,000,000 API calls
- **Performance**: Average response time of 700ms
- **High QPS**: Supports up to 200 QPS per client
- **Design**: RESTful API design following standard OpenAPI specifications
- **Cost-effective**: 96% cheaper than official Twitter API

### Pricing
- **Tweets**: $0.15 per 1k tweets
- **User Profiles**: $0.18 per 1k user profiles
- **Followers**: $0.15 per 1k followers
- **Minimum Charge**: $0.00015 per request
- **Special Offers**: Discounted rates for students and research institutions

### Base URL
```
https://api.twitterapi.io
```

## API Categories

### 1. User Endpoints
- Batch Get User Info By UserIds
- Get User Info
- Get User Last Tweets
- Get User Followers
- Get User Followings
- Get User Mentions
- Check Follow Relationship
- Search User by Keyword

### 2. Tweet Endpoints
- Get Tweets by IDs
- Get Tweet Replies
- Get Tweet Quotations
- Get Tweet Retweeters
- Get Tweet Thread Context
- Get Article
- Advanced Search

### 3. Communities Endpoints
- Get Community Info By Id
- Get Community Members
- Get Community Moderators
- Get Community Tweets

### 4. List Endpoints
- Get List Tweets
- Get List Followers
- Get List Members

### 5. Trend Endpoints
- Get Trends

### 6. My Account Endpoints
- Get My Account Info

### 7. Login Endpoints
- Login Step 1: by email or username
- Login Step 2: by 2FA code

### 8. Tweet Action Endpoints
- Upload Image
- Post/Reply/Quote a Tweet
- Like a Tweet
- Retweet a Tweet

### 9. Webhook/Websocket Filter Rules
- Add Webhook/Websocket Tweet Filter Rule
- Get ALL Test Webhook/Websocket Tweet Filter Rules
- Update Webhook/Websocket Tweet Filter Rule
- Delete Webhook/Websocket Tweet Filter Rule

## Authentication
All API requests require authentication using an API key passed in the header as `X-API-Key`.

## Rate Limits
- Supports up to 200 QPS (Queries Per Second) per client
- No specific rate limits mentioned beyond QPS capacity

## Response Format
All responses are in JSON format following RESTful API conventions.