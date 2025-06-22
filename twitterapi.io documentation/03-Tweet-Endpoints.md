# Tweet Endpoints

## Overview
Tweet endpoints provide access to Twitter posts (tweets), their metadata, interactions, and related content.

## Endpoints

### 1. Get Tweets by IDs
**Endpoint**: `GET /twitter/tweets`

**Description**: Get tweet by tweet IDs.

**Note**: Detailed parameters and response format not fully documented in available sources.

---

### 2. Get Tweet Replies
**Endpoint**: `GET /twitter/tweet/replies`

**Description**: Get tweet replies by tweet ID.

**Key Features**:
- Returns up to 20 replies per page
- Filters out ads and non-tweet content
- Replies are ordered by time (descending)
- Supports pagination using cursor

**Parameters**:
- Tweet ID (method not fully detailed)
- Cursor for pagination

---

### 3. Get Tweet Quotations
**Endpoint**: `GET /twitter/tweet/quotes`

**Description**: Get quote tweets for a specific tweet.

**Key Features**:
- Each page returns exactly 20 quotes
- Order by quote time descending
- Supports pagination using cursor

**Parameters**:
- Tweet ID (method not fully detailed)
- Cursor for pagination

---

### 4. Get Tweet Retweeters
**Endpoint**: `GET /twitter/tweet/retweeters`

**Description**: Get tweet retweeters by tweet ID.

**Key Features**:
- Each page returns about 100 retweeters
- Order by retweet time descending
- Supports pagination via cursor

**Parameters**:
- Tweet ID (method not fully detailed)
- Cursor for pagination

---

### 5. Get Tweet Thread Context
**Endpoint**: `GET /twitter/tweet/thread_context`

**Description**: Get the thread context of a tweet. Retrieves the conversation thread that a tweet belongs to.

**Parameters**:
- `tweetId` (required, string): The tweet ID to retrieve thread context for
- `cursor` (optional, string): Pagination cursor, first page is empty string

**Authentication**: Requires `X-API-Key` in request header

**Response Structure**:
```json
{
  "replies": [...],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "message": "string"
}
```

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/tweet/thread_context \
  --header 'X-API-Key: <api-key>'
```

**Note**: Pagination size cannot be set, and data returned per page is not fixed due to Twitter's limitations.

---

### 6. Get Article
**Endpoint**: `GET /twitter/article`

**Description**: Retrieve detailed article information from a specific tweet.

**Cost**: 100 credits per article

**Parameters**:
- `tweet_id` (required, string): The ID of the tweet containing the article
  - Example: "1905545699552375179"

**Authentication**: Requires `X-API-Key` in request header

**Response Format**:
```json
{
  "article": {
    "author": {UserInfo object},
    "replyCount": 123,
    "likeCount": 123,
    "quoteCount": 123,
    "viewCount": 123,
    "createdAt": "<timestamp>",
    "title": "<string>",
    "preview_text": "<string>",
    "cover_media_img_url": "<URL>",
    "contents": [{"text": "<string>"}]
  },
  "status": "success",
  "message": "<optional message>"
}
```

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/article \
  --header 'X-API-Key: <api-key>'
```

---

### 7. Advanced Search
**Endpoint**: `GET /twitter/tweet/advanced_search`

**Description**: Advanced search for tweets with filtering capabilities.

**Key Features**:
- Returns up to 20 results per page
- Supports pagination using cursor
- Filters available for dates and keywords
- Sometimes returns fewer than 20 results (filters out ads and non-tweets)

**Parameters**: Not fully detailed in available documentation
- Search query/keywords
- Date filters
- Cursor for pagination

## Common Response Elements

Tweet objects typically include:
- Tweet ID and URL
- Tweet text content
- Creation timestamp
- Author information
- Engagement metrics (likes, retweets, replies, views)
- Entities (hashtags, mentions, URLs)
- Media attachments (if any)
- Reply/quote/retweet relationships

## Authentication
All tweet endpoints require the `X-API-Key` header for authentication.

## Pagination
Most endpoints support cursor-based pagination:
- Use empty string `""` for the first page
- Use the `next_cursor` value from the response for subsequent pages
- Check `has_next_page` to determine if more results are available