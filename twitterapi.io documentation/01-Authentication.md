# Authentication

## Overview
TwitterAPI.io uses API key authentication for all requests. Every API call must include an API key in the HTTP headers.

## Getting Your API Key
1. Log in to the [TwitterApiIO Dashboard](https://twitterapi.io/dashboard)
2. Find your API key on the dashboard homepage

## Header Requirements
All API requests must include the API key in the headers:

```
x-api-key: YOUR_API_KEY
```

## Code Examples

### cURL
```bash
curl --location 'https://api.twitterapi.io/twitter/user/followings?userName=KaitoEasyAPI' \
--header 'x-api-key: my_test_xxxxx'
```

### Python
```python
import requests

url = 'https://api.twitterapi.io/twitter/user/followings?userName=KaitoEasyAPI'
headers = {'x-api-key': 'my_test_xxxxx'}
response = requests.get(url, headers=headers)
print(response.json())
```

### Java
```java
OkHttpClient client = new OkHttpClient();

Request request = new Request.Builder()
    .url("https://api.twitterapi.io/twitter/user/followings?userName=KaitoEasyAPI")
    .addHeader("x-api-key", "my_test_xxxxx")
    .build();
```

### JavaScript/Node.js
```javascript
const headers = {
    'x-api-key': 'my_test_xxxxx'
};

fetch('https://api.twitterapi.io/twitter/user/followings?userName=KaitoEasyAPI', {
    method: 'GET',
    headers: headers
})
.then(response => response.json())
.then(data => console.log(data));
```

## Important Notes
- The API key header name is case-sensitive: use `x-api-key`
- Always keep your API key secure and never expose it in client-side code
- API keys are unique to each account and should not be shared