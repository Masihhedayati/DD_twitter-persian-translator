# Webhook/Websocket Filter Rules

## Overview
Webhook and Websocket filter rules allow you to set up automated monitoring of Twitter content based on specific criteria. These rules can filter tweets and trigger actions when matching content is found.

## Endpoints

### 1. Add Webhook/Websocket Tweet Filter Rule
**Endpoint**: `POST /oapi/tweet_filter/add_rule`

**Description**: Create a new tweet filter rule for webhook or websocket monitoring.

**Parameters**:
- `tag` (required, string): Custom identifier for the rule
  - Maximum length: 255 characters
- `value` (required, string): Rule to filter tweets (e.g., "from:elonmusk OR from:kaitoeasyapi")
  - Maximum length: 255 characters
- `interval_seconds` (required, number): Interval to check tweets
  - Minimum: 100 seconds
  - Maximum: 86,400 seconds (24 hours)

**Authentication**: Requires `X-API-Key` in header

**Response**:
```json
{
  "rule_id": "<string>",
  "status": "success",
  "msg": "<string>"
}
```

**Important Notes**:
- Default rule is not activated upon creation
- You must call `update_rule` to activate the rule

**Example Request**:
```bash
curl --request POST \
  --url https://api.twitterapi.io/oapi/tweet_filter/add_rule \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <api-key>' \
  --data '{
    "tag": "elon_mentions",
    "value": "from:elonmusk OR @elonmusk",
    "interval_seconds": 300
  }'
```

---

### 2. Get ALL Test Webhook/Websocket Tweet Filter Rules
**Endpoint**: `GET /oapi/tweet_filter/get_rules`

**Description**: Retrieve all tweet filter rules. Rules can be used in webhook and websocket.

**Authentication**: Requires `X-API-Key` in header

**Response**:
```json
{
  "rules": [
    {
      "rule_id": "<string>",
      "tag": "<string>",
      "value": "<string>",
      "interval_seconds": 123
    }
  ],
  "status": "success",
  "msg": "<string>"
}
```

**Rule Object Properties**:
- `rule_id`: Unique identifier for the rule
- `tag`: Custom identifier (max 255 characters)
- `value`: Filter rule (max 255 characters)
- `interval_seconds`: Check interval (min 100, max 86400)

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/oapi/tweet_filter/get_rules \
  --header 'X-API-Key: <api-key>'
```

---

### 3. Update Webhook/Websocket Tweet Filter Rule
**Endpoint**: `POST /oapi/tweet_filter/update_rule`

**Description**: Update an existing tweet filter rule. All parameters must be provided.

**Parameters** (all required):
- `rule_id` (string): ID of the rule to update
- `tag` (string): Custom tag to identify the rule (max 255 characters)
- `value` (string): Rule to filter tweets (max 255 characters)
- `interval_seconds` (number): Interval to check tweets (min 0.1, max 86400)
- `is_effect` (integer): Rule effectiveness
  - 0 = inactive
  - 1 = active

**Authentication**: Requires `X-API-Key` in header

**Request Body**:
```json
{
  "rule_id": "<string>",
  "tag": "<string>",
  "value": "<string>",
  "interval_seconds": 123,
  "is_effect": 1
}
```

**Response**:
```json
{
  "status": "success",
  "msg": "<string>"
}
```

**Example Request**:
```bash
curl --request POST \
  --url https://api.twitterapi.io/oapi/tweet_filter/update_rule \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <api-key>' \
  --data '{
    "rule_id": "12345",
    "tag": "updated_rule",
    "value": "from:elonmusk OR tesla",
    "interval_seconds": 600,
    "is_effect": 1
  }'
```

---

### 4. Delete Webhook/Websocket Tweet Filter Rule
**Endpoint**: `DELETE /oapi/tweet_filter/delete_rule`

**Description**: Delete a tweet filter rule.

**Parameters**:
- `rule_id` (required, string): ID of the rule to delete

**Authentication**: Requires `X-API-Key` in header

**Request Body**:
```json
{
  "rule_id": "<string>"
}
```

**Response**:
```json
{
  "status": "success",
  "msg": "<string>"
}
```

**Example Request**:
```bash
curl --request DELETE \
  --url https://api.twitterapi.io/oapi/tweet_filter/delete_rule \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <api-key>' \
  --data '{
    "rule_id": "12345"
  }'
```

## Rule Configuration

### Filter Rule Syntax
The `value` parameter supports Twitter search operators for filtering tweets:
- `from:username`: Tweets from specific users
- `@username`: Mentions of specific users
- `#hashtag`: Tweets containing hashtags
- `keyword`: Tweets containing keywords
- `OR`: Logical OR operator
- `AND`: Logical AND operator
- `"exact phrase"`: Exact phrase matching

### Example Filter Rules
```
"from:elonmusk OR from:tesla"
"#cryptocurrency AND bitcoin"
"@openai OR ChatGPT"
"breaking news" AND "technology"
```

### Interval Configuration
- **Minimum**: 100 seconds (1.67 minutes)
- **Maximum**: 86,400 seconds (24 hours)
- **Recommended**: 300-3600 seconds for most use cases

## Workflow

### Setting Up a Filter Rule
1. **Create Rule**: Use `add_rule` to create a new filter rule (inactive by default)
2. **Activate Rule**: Use `update_rule` with `is_effect: 1` to activate the rule
3. **Monitor**: The rule will now check for matching tweets at the specified interval
4. **Manage**: Update or delete rules as needed

### Rule Lifecycle
```
Create Rule (inactive) → Update Rule (activate) → Monitor Tweets → Update/Delete as needed
```

## Use Cases
- **Brand Monitoring**: Track mentions of your brand or competitors
- **Social Listening**: Monitor conversations around specific topics
- **Trend Analysis**: Track hashtags and keywords over time
- **Customer Service**: Monitor support-related mentions
- **Content Curation**: Collect tweets matching specific criteria

## Best Practices
- Use specific, targeted filter rules to reduce noise
- Set appropriate intervals based on your monitoring needs
- Regularly review and update rules to maintain relevance
- Consider combining multiple operators for precise filtering
- Test rules before deploying to production

## Authentication
All webhook/websocket filter rule endpoints require the `X-API-Key` header for authentication.

## Rate Limits
Follow the API's rate limiting guidelines when creating, updating, or deleting rules frequently.