# User Endpoints

## Overview
User endpoints provide access to Twitter user profiles, their relationships, and user-related data.

## Endpoints

### 1. Batch Get User Info By UserIds
**Endpoint**: `GET /twitter/user/batch_info_by_ids`

**Description**: Retrieve user information for multiple user IDs in a single request.

**Pricing**:
- Single user request: 18 credits per user
- Bulk request (100+ users): 10 credits per user

**Parameters**:
- User IDs (method of passing not specified in available docs)

**Use Case**: Recommended for cost optimization when fetching multiple user profiles.

---

### 2. Get User Info
**Endpoint**: `GET /twitter/user/info`

**Description**: Get user info by screen name.

**Parameters**:
- Screen name (method not fully detailed)

**Pricing**: Part of $0.18/1k user profiles pricing structure

---

### 3. Get User Last Tweets
**Endpoint**: `GET /twitter/user/last_tweets`

**Description**: Retrieve tweets by user name, sorted by created_at.

**Parameters**:
- `userId` (optional, string): User ID (recommended for stability)
- `userName` (optional, string): Screen name of the user
- `cursor` (optional, string): Pagination cursor, first page is ""
- `includeReplies` (optional, boolean): Default is false

**Response Structure**:
```json
{
  "tweets": [...],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "message": "string"
}
```

**Key Features**:
- Up to 20 tweets per page
- Paginated results
- Does not return replied tweets by default
- Prefer `userId` over `userName` for stability

---

### 4. Get User Followers
**Endpoint**: `GET /twitter/user/followers`

**Description**: Get a user's followers list.

**Parameters**:
- `userName` (required, string): Screen name of the user
- `cursor` (optional, string): Pagination cursor (first page is "")
- `pageSize` (optional, integer): Default: 200, Min: 20, Max: 200

**Response**: Array of 200 followers per page, sorted by most recent followers first.

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/user/followers \
  --header 'X-API-Key: <api-key>'
```

---

### 5. Get User Followings
**Endpoint**: `GET /twitter/user/followings`

**Description**: Get a user's following list.

**Parameters**:
- `userName` (required, string): Screen name of the user
- `cursor` (optional, string): Pagination cursor, first page is ""
- `pageSize` (optional, integer): Default: 200, Min: 20, Max: 200

**Response Structure**:
```json
{
  "followings": [...],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "message": "string"
}
```

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/user/followings \
  --header 'X-API-Key: <api-key>'
```

---

### 6. Get User Mentions
**Endpoint**: `GET /twitter/user/mentions`

**Description**: Get tweet mentions by user screen name.

**Key Features**:
- Page Size: Exactly 20 mentions per page
- Pagination: Supported via cursor
- Sorting: Order by mention time descending

---

### 7. Check Follow Relationship
**Endpoint**: `GET /twitter/user/check_follow_relationship`

**Description**: Check the follow relationship between two Twitter users.

**Parameters**:
- `source_user_name` (required, string): Screen name of the source user
- `target_user_name` (required, string): Screen name of the target user

**Pricing**: 100 credits per call

**Response**:
```json
{
  "data": {
    "following": true,    // Whether source user follows target user
    "followed_by": true   // Whether source user is followed by target user
  },
  "status": "success",
  "message": "<string>"
}
```

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/user/check_follow_relationship \
  --header 'X-API-Key: <api-key>'
```

---

### 8. Search User by Keyword
**Endpoint**: `GET /twitter/user/search`

**Description**: Search for users by keyword.

**Parameters**:
- `query` (required, string): The keyword to search

**Response Structure**:
```json
{
  "users": [...],
  "has_next_page": boolean,
  "next_cursor": "string",
  "status": "success|error",
  "msg": "string"
}
```

**User Information Includes**:
- Username, user ID, display name
- Profile details (picture, bio, location)
- Follower/following counts
- Verification status
- Account creation date

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/user/search \
  --header 'X-API-Key: <api-key>'
```

## Common Response Fields

All user endpoints return comprehensive user profile data including:
- Username and display name
- User ID
- Profile picture
- Bio/description
- Location
- Follower/following counts
- Account creation date
- Verification status
- And additional profile metadata

## Authentication
All user endpoints require the `X-API-Key` header for authentication.