# List Endpoints

## Overview
List endpoints provide access to Twitter Lists, including tweets from lists, list followers, and list members.

## Endpoints

### 1. Get List Tweets
**Endpoint**: `GET /twitter/list/tweets`

**Description**: Get tweets from a specific Twitter list.

**Key Features**:
- Each page returns exactly 20 tweets
- Tweets are ordered by tweet time descending
- Supports pagination using cursor

**Parameters**:
- List ID (parameter method not fully detailed in available docs)
- Cursor for pagination

**Note**: Specific parameter names and response format not detailed in available documentation.

---

### 2. Get List Followers
**Endpoint**: `GET /twitter/list/followers`

**Description**: Get followers of a list.

**Parameters**:
- `list_id` (required, string): ID of the list
- `cursor` (optional, string): Cursor for pagination

**Authentication**: Requires `X-API-Key` in header

**Response Structure**:
```json
{
  "followers": [UserInfo objects],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "msg": "string"
}
```

**Key Features**:
- Page size: 20 followers per request
- Supports pagination via cursor
- Returns comprehensive user information

**UserInfo Object Includes**:
- Username, user ID, display name
- Profile picture and cover picture URLs
- Follower/following counts
- Account creation date
- Verification status

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/list/followers \
  --header 'X-API-Key: <api-key>'
```

---

### 3. Get List Members
**Endpoint**: `GET /twitter/list/members`

**Description**: Get members of a list.

**Parameters**:
- `list_id` (required, string): ID of the list
- `cursor` (optional, string): Cursor for pagination

**Authentication**: Requires `X-API-Key` in header

**Response Format**:
```json
{
  "members": [UserInfo objects],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "msg": "string"
}
```

**Key Features**:
- Page size: 20 members per request
- Supports pagination via cursor
- Returns detailed user information for each member

**UserInfo Object Includes**:
- Username, user ID, display name
- Profile picture and cover picture URLs
- Bio/description
- Location
- Follower/following counts
- Account creation date
- Verification status
- Additional profile metadata

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/list/members \
  --header 'X-API-Key: <api-key>'
```

## Common Response Elements

### UserInfo Object
List followers and members endpoints return UserInfo objects containing:
- Basic user details (username, ID, name)
- Profile information (pictures, bio, location)
- Account statistics (followers, following counts)
- Account metadata (creation date, verification status)
- Additional profile details

### Pagination
List endpoints support cursor-based pagination:
- Use the `cursor` parameter for pagination
- Check `has_next_page` to determine if more results are available
- Use `next_cursor` value for subsequent requests
- First page: omit cursor or use empty string

## Authentication
All list endpoints require the `X-API-Key` header for authentication.

## Use Cases
- **Get List Tweets**: Retrieve tweets from curated Twitter lists
- **Get List Followers**: Analyze who follows specific lists
- **Get List Members**: Get members of curated Twitter lists for analysis or engagement