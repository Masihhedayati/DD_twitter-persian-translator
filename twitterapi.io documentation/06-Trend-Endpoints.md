# Trend Endpoints

## Overview
Trend endpoints provide access to Twitter trending topics for specific locations.

## Endpoints

### 1. Get Trends
**Endpoint**: `GET /twitter/trends`

**Description**: Get trending topics for a specific location.

**Parameters**:
- `woeid` (required, integer): Location identifier (Where On Earth ID)
  - Example: 2418046
  - Complete list available at: https://gist.github.com/tedyblood/5bb5a9f78314cc1f478b3dd7cde790b9
- `count` (optional, integer): Number of trends to return
  - Default: 30
  - Minimum: 30

**Authentication**: Requires `X-API-Key` in header

**Response Format**:
```json
{
  "trends": [
    {
      "name": "<string>",
      "target": {
        "query": "<string>"
      },
      "rank": 123,
      "meta_description": "<string>"
    }
  ],
  "status": "success",
  "msg": "<string>"
}
```

**Response Fields**:
- `trends`: Array of trending topics
  - `name`: The trending topic name
  - `target.query`: Search query for the trend
  - `rank`: Numerical ranking of the trend
  - `meta_description`: Additional description of the trend
- `status`: Response status ("success" or "error")
- `msg`: Optional message

**Example Request**:
```bash
curl --request GET \
  --url https://api.twitterapi.io/twitter/trends \
  --header 'X-API-Key: <api-key>'
```

**Example with Parameters**:
```bash
curl --request GET \
  --url 'https://api.twitterapi.io/twitter/trends?woeid=2418046&count=50' \
  --header 'X-API-Key: <api-key>'
```

## WOEID (Where On Earth ID)
WOEID is a unique identifier for geographic locations used by Twitter for trending topics. Common WOEIDs include:
- Global: 1
- United States: 23424977
- New York: 2459115
- London: 44418
- Tokyo: 1118370

For a complete list of WOEIDs, visit: https://gist.github.com/tedyblood/5bb5a9f78314cc1f478b3dd7cde790b9

## Use Cases
- **Social Media Monitoring**: Track trending topics in specific regions
- **Content Strategy**: Identify popular topics for content creation
- **Market Research**: Understand what's trending in target markets
- **Real-time Analysis**: Monitor emerging trends and topics

## Authentication
The trends endpoint requires the `X-API-Key` header for authentication.