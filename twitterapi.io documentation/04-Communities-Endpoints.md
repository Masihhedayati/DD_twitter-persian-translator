# Communities Endpoints

## Overview
Communities endpoints provide access to Twitter Communities data, including community information, members, moderators, and tweets.

## Endpoints

### 1. Get Community Info By Id
**Endpoint**: `GET /twitter/community/info`

**Description**: Get community info by community ID.

**Pricing**: 20 credits per call

**Parameters**:
- Community ID (parameter method not fully detailed in available docs)

**Notes**: 
- This API is reported to be slow, with ongoing optimization efforts
- Specific parameter names and response format not detailed in available documentation

---

### 2. Get Community Members
**Endpoint**: `GET /twitter/community/members`

**Description**: Get members of a community.

**Parameters**:
- `community_id` (required, string): ID of the community to retrieve members from

**Authentication**: Requires `X-API-Key` in header

**Response Format**:
```json
{
  "members": [UserInfo objects],
  "status": "success",
  "msg": "<string>"
}
```

**Key Features**:
- Page size: 20 members per request
- Returns comprehensive user information for each member

**UserInfo Object Includes**:
- Basic user details (username, ID, name)
- Profile information (profile picture, cover picture)
- Follower/following counts
- Account metadata (creation date, verification status)

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/community/members \
  --header 'X-API-Key: <api-key>'
```

---

### 3. Get Community Moderators
**Endpoint**: `GET /twitter/community/moderators`

**Description**: Get moderators of a community.

**Parameters**:
- `community_id` (required, string): ID of the community

**Authentication**: Requires `X-API-Key` in header

**Response Format**:
```json
{
  "members": [UserInfo objects],
  "status": "success",
  "msg": "<string>"
}
```

**Key Features**:
- Page size: 20 moderators per request
- Returns comprehensive user information for each moderator

**UserInfo Object Includes**:
- User details (username, profile picture, followers count)
- Verification status
- Profile description
- Account metadata

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/community/moderators \
  --header 'X-API-Key: <api-key>'
```

---

### 4. Get Community Tweets
**Endpoint**: `GET /twitter/community/tweets`

**Description**: Get tweets from a specific community.

**Parameters**:
- `community_id` (required, string): ID of the community
- `cursor` (optional, string): Pagination cursor

**Authentication**: Requires `X-API-Key` in header

**Response Structure**:
```json
{
  "tweets": [Tweet objects],
  "has_next": true/false,
  "next_cursor": "<string>",
  "status": "success",
  "msg": "<optional message>"
}
```

**Key Features**:
- Page size: 20 tweets per request
- Ordered by creation time (descending)
- Supports pagination via cursor

**Tweet Object Includes**:
- Tweet text and metadata
- Author information
- Engagement metrics (likes, retweets, replies)
- Entities (hashtags, URLs, mentions)

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/community/tweets \
  --header 'X-API-Key: <api-key>'
```

## Common Response Elements

### UserInfo Object
All community member and moderator endpoints return UserInfo objects containing:
- Username, user ID, display name
- Profile picture and cover picture URLs
- Bio/description
- Location
- Follower/following counts
- Account creation date
- Verification status
- Additional profile metadata

### Tweet Object
Community tweets endpoint returns Tweet objects containing:
- Tweet ID and text content
- Creation timestamp
- Author information
- Engagement metrics
- Media attachments (if any)
- Entities (hashtags, mentions, URLs)

## Authentication
All communities endpoints require the `X-API-Key` header for authentication.

## Pagination
Community tweets endpoint supports cursor-based pagination:
- Use the `cursor` parameter for pagination
- Check `has_next` to determine if more results are available
- Use `next_cursor` value for subsequent requests