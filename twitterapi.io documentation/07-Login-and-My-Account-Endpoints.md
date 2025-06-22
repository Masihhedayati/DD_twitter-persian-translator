# Login and My Account Endpoints

## Overview
These endpoints provide authentication functionality and access to authenticated user account information.

## Endpoints

### 1. Get My Account Info
**Endpoint**: `GET /oapi/my/info`

**Description**: Get information about the authenticated user's account.

**Parameters**: None specified in available documentation

**Authentication**: Requires `X-API-Key` in header

**Response Format**: Not detailed in available documentation

**Use Case**: Retrieve account information for the authenticated user

---

### 2. Login Step 1: By Email or Username
**Endpoint**: `POST /twitter/login_by_email_or_username`

**Description**: First step of the two-factor authentication login process.

**Pricing**: $0.003 per call (trial operation)

**Recommended Input**: Email preferred over username

**Parameters**: Not explicitly detailed in available documentation (likely email/username)

**Response Format**: Not specified in available documentation

**Process Flow**: 
1. Use this endpoint with email or username
2. Proceed to Login Step 2 with 2FA code

---

### 3. Login Step 2: By 2FA Code
**Endpoint**: `POST /twitter/login_by_2fa`

**Description**: Second step of the authentication process using 2FA code.

**Pricing**: $0.003 per call (trial operation)

**Parameters**: Not explicitly detailed in available documentation (likely 2FA code)

**Response Format**: Not specified in available documentation

**Process Flow**:
1. Complete Login Step 1 first
2. Use the 2FA code received to complete authentication

## Authentication Flow

The login process follows a two-step authentication pattern:

1. **Step 1**: Authenticate with email or username
   - Use `POST /twitter/login_by_email_or_username`
   - Email is preferred over username
   - Costs $0.003 per call

2. **Step 2**: Complete authentication with 2FA code
   - Use `POST /twitter/login_by_2fa`
   - Provide the 2FA code received
   - Costs $0.003 per call

3. **Access Account**: Once authenticated, use `GET /oapi/my/info` to retrieve account information

## Pricing
- Login Step 1: $0.003 per call
- Login Step 2: $0.003 per call
- Get My Account Info: Pricing not specified

## Security Notes
- Two-factor authentication is required for login
- Email is recommended over username for Step 1
- Both login steps are billable operations

## Authentication
All endpoints require the `X-API-Key` header for authentication.

## Note
The available documentation for these endpoints is limited. For complete implementation details including:
- Exact parameter names and formats
- Complete response structures
- Error handling
- Authentication token management

Please consult the full API documentation or contact TwitterAPI.io support.