# Complete TwitterAPI.io API Reference

## Base Information
- **Base URL**: `https://api.twitterapi.io`
- **Authentication**: API Key via `X-API-Key` header
- **Response Format**: JSON
- **Design**: RESTful API following OpenAPI specifications

## Quick Reference

### User Endpoints
| Endpoint | Method | Description | Page Size |
|----------|--------|-------------|-----------|
| `/twitter/user/batch_info_by_ids` | GET | Batch get user info by IDs | Variable |
| `/twitter/user/info` | GET | Get user info by screen name | Single user |
| `/twitter/user/last_tweets` | GET | Get user's recent tweets | 20 tweets |
| `/twitter/user/followers` | GET | Get user's followers | 200 users |
| `/twitter/user/followings` | GET | Get user's following list | 200 users |
| `/twitter/user/mentions` | GET | Get user mentions | 20 mentions |
| `/twitter/user/check_follow_relationship` | GET | Check follow relationship between users | Single check |
| `/twitter/user/search` | GET | Search users by keyword | Variable |

### Tweet Endpoints
| Endpoint | Method | Description | Page Size |
|----------|--------|-------------|-----------|
| `/twitter/tweets` | GET | Get tweets by IDs | Variable |
| `/twitter/tweet/replies` | GET | Get tweet replies | 20 replies |
| `/twitter/tweet/quotes` | GET | Get tweet quotations | 20 quotes |
| `/twitter/tweet/retweeters` | GET | Get tweet retweeters | ~100 users |
| `/twitter/tweet/thread_context` | GET | Get tweet thread context | Variable |
| `/twitter/article` | GET | Get article from tweet | Single article |
| `/twitter/tweet/advanced_search` | GET | Advanced tweet search | 20 tweets |

### Communities Endpoints
| Endpoint | Method | Description | Page Size |
|----------|--------|-------------|-----------|
| `/twitter/community/info` | GET | Get community info by ID | Single community |
| `/twitter/community/members` | GET | Get community members | 20 members |
| `/twitter/community/moderators` | GET | Get community moderators | 20 moderators |
| `/twitter/community/tweets` | GET | Get community tweets | 20 tweets |

### List Endpoints
| Endpoint | Method | Description | Page Size |
|----------|--------|-------------|-----------|
| `/twitter/list/tweets` | GET | Get list tweets | 20 tweets |
| `/twitter/list/followers` | GET | Get list followers | 20 followers |
| `/twitter/list/members` | GET | Get list members | 20 members |

### Trend Endpoints
| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/twitter/trends` | GET | Get trends by location | Up to 50 trends |

### Account & Authentication
| Endpoint | Method | Description | Cost |
|----------|--------|-------------|------|
| `/oapi/my/info` | GET | Get account info | Not specified |
| `/twitter/login_by_email_or_username` | POST | Login step 1 | $0.003 per call |
| `/twitter/login_by_2fa` | POST | Login step 2 | $0.003 per call |

### Tweet Actions (Requires Login)
| Endpoint | Method | Description | Cost |
|----------|--------|-------------|------|
| `/twitter/upload_image` | POST | Upload image | Not specified |
| `/twitter/create_tweet` | POST | Post/reply/quote tweet | $0.001 per call |
| `/twitter/like_tweet` | POST | Like a tweet | $0.001 per call |
| `/twitter/retweet_tweet` | POST | Retweet a tweet | $0.001 per call |

### Filter Rules (Webhook/Websocket)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/oapi/tweet_filter/add_rule` | POST | Add filter rule |
| `/oapi/tweet_filter/get_rules` | GET | Get all filter rules |
| `/oapi/tweet_filter/update_rule` | POST | Update filter rule |
| `/oapi/tweet_filter/delete_rule` | DELETE | Delete filter rule |

## Pricing Overview

### Standard Endpoints
- **Tweets**: $0.15 per 1k tweets
- **User Profiles**: $0.18 per 1k user profiles
- **Followers**: $0.15 per 1k followers
- **Minimum Charge**: $0.00015 per request

### Bulk Operations
- **Single User Request**: 18 credits per user
- **Bulk Request (100+ users)**: 10 credits per user

### Premium Endpoints
- **Get Article**: 100 credits per article
- **Get Community Info**: 20 credits per call
- **Check Follow Relationship**: 100 credits per call

### Action Endpoints
- **Login Steps**: $0.003 per call each
- **Tweet Actions**: $0.001 per call each

## Common Parameters

### Pagination
Most endpoints support cursor-based pagination:
- `cursor`: Pagination cursor (empty string for first page)
- `next_cursor`: Next page cursor in response
- `has_next_page`: Boolean indicating more results

### User Identification
- `userId`: Recommended for stability
- `userName`: Screen name (alternative to userId)

### Standard Query Parameters
- `pageSize`: Results per page (where applicable)
- `count`: Number of items to return
- `includeReplies`: Include reply tweets (boolean)

## Response Formats

### Standard Success Response
```json
{
  "data": [...],
  "status": "success",
  "message": "string",
  "has_next_page": boolean,
  "next_cursor": "string"
}
```

### Error Response
```json
{
  "status": "error",
  "message": "Error description",
  "error_code": "ERROR_CODE"
}
```

## Rate Limits
- **QPS Limit**: Up to 200 queries per second per client
- **Performance**: Average response time of 700ms

## Authentication Requirements

### API Key Authentication
All endpoints require:
```
X-API-Key: YOUR_API_KEY
```

### Session Authentication (Action Endpoints)
Tweet action endpoints additionally require:
- `auth_session`: Token from login process
- `proxy`: Proxy configuration

## Best Practices

### Performance Optimization
1. Use `userId` instead of `userName` for better stability
2. Implement proper pagination for large datasets
3. Use bulk endpoints for multiple user operations
4. Cache responses when appropriate

### Cost Optimization
1. Use bulk user endpoints for 100+ users
2. Implement efficient pagination strategies
3. Filter results on the client side when possible
4. Monitor API usage and costs

### Error Handling
1. Check `status` field in all responses
2. Implement retry logic for transient errors
3. Handle rate limiting gracefully
4. Validate input parameters before API calls

## Special Notes

### Filter Rules
- Rules are created inactive by default
- Must call `update_rule` to activate
- Interval minimum: 100 seconds, maximum: 86,400 seconds

### Tweet Actions
- Require two-step authentication
- Need proxy configuration
- Session tokens have expiration times

### Community Endpoints
- Some endpoints may be slower (optimization ongoing)
- Community features may have limited availability

## Support and Resources
- **API Support**: Contact through provided channels
- **Documentation**: Available at docs.twitterapi.io
- **Student Discounts**: Available for educational institutions
- **Special Offers**: Discounted rates for students and research institutions