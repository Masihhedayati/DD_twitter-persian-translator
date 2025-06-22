# Tweet Action Endpoints

## Overview
Tweet Action endpoints allow you to perform actions on Twitter such as uploading images, posting tweets, liking tweets, and retweeting. These endpoints require prior authentication and use session tokens.

## Prerequisites
All tweet action endpoints require:
1. Prior login using the two-step authentication process
2. An `auth_session` token from the login process
3. Proxy configuration

## Endpoints

### 1. Upload Image
**Endpoint**: `POST /twitter/upload_image` (estimated based on navigation)

**Description**: Upload images to Twitter for use in tweets.

**Note**: Detailed documentation not available in current sources. This endpoint likely follows similar patterns to other action endpoints requiring auth_session and proxy parameters.

---

### 2. Post/Reply/Quote a Tweet
**Endpoint**: `POST /twitter/create_tweet`

**Description**: Create a new tweet, reply to an existing tweet, or quote tweet.

**Pricing**: $0.001 per call (trial operation)

**Prerequisites**: Must login first using the two-step authentication process

**Parameters**: Not fully detailed in available documentation

**Authentication**: Requires `X-API-Key` in header

**Note**: Complete parameter structure not available in current documentation

---

### 3. Like a Tweet
**Endpoint**: `POST /twitter/like_tweet`

**Description**: Like a specific tweet.

**Pricing**: $0.001 per call (trial operation)

**Prerequisites**: Must login first

**Parameters**:
- `auth_session` (required, string): Login session returned by `/twitter/login_by_2fa`
- `tweet_id` (required, string): ID of the tweet to like
- `proxy` (required, string): Proxy server details

**Authentication**: Requires `X-API-Key` in header

**Request Body**:
```json
{
  "auth_session": "<string>",
  "tweet_id": "<string>",
  "proxy": "<string>"
}
```

**Response**:
```json
{
  "status": "<string>",
  "msg": "<string>"
}
```

**Example Request**:
```bash
curl --request POST \
  --url https://api.twitterapi.io/twitter/like_tweet \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <api-key>' \
  --data '{
    "auth_session": "<session_token>",
    "tweet_id": "1234567890",
    "proxy": "<proxy_details>"
  }'
```

---

### 4. Retweet a Tweet
**Endpoint**: `POST /twitter/retweet_tweet`

**Description**: Retweet a specific tweet.

**Pricing**: $0.001 per call (trial operation)

**Prerequisites**: Must login first

**Parameters**:
- `auth_session` (required, string): Login session string
- `tweet_id` (required, string): ID of tweet to retweet
- `proxy` (required, string): Proxy server details (format: "http://username:password@ip:port")

**Authentication**: Requires `X-API-Key` in header

**Request Body**:
```json
{
  "auth_session": "<string>",
  "tweet_id": "<string>",
  "proxy": "<string>"
}
```

**Response**:
```json
{
  "status": "<string>",
  "msg": "<string>"
}
```

**Example Request**:
```bash
curl --request POST \
  --url https://api.twitterapi.io/twitter/retweet_tweet \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: <api-key>' \
  --data '{
    "auth_session": "<session_token>",
    "tweet_id": "1234567890",
    "proxy": "http://username:password@ip:port"
  }'
```

## Common Requirements

### Authentication Session
All action endpoints require an `auth_session` token obtained through the login process:
1. Use `POST /twitter/login_by_email_or_username` with email/username
2. Use `POST /twitter/login_by_2fa` with the 2FA code
3. Extract the `auth_session` from the login response

### Proxy Configuration
All action endpoints require proxy configuration. The proxy should be provided in the format:
```
http://username:password@ip:port
```

### Request Headers
All requests must include:
- `Content-Type: application/json`
- `X-API-Key: <your-api-key>`

## Response Format
All action endpoints return a response with:
- `status`: "success" or "error"
- `msg`: Additional message or error details

## Pricing
All tweet action endpoints are priced at $0.001 per call during trial operations.

## Error Handling
- Ensure valid `auth_session` token
- Verify proxy configuration is correct
- Check that tweet IDs exist and are accessible
- Handle rate limiting appropriately

## Use Cases
- **Upload Image**: Prepare media for tweets
- **Post Tweet**: Create new content, replies, or quote tweets
- **Like Tweet**: Engage with content programmatically
- **Retweet**: Share content with your followers

## Security Notes
- Keep `auth_session` tokens secure and refresh them regularly
- Use secure proxy connections
- Never expose authentication tokens in client-side code
- Follow Twitter's terms of service for automated actions