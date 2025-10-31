# API Testing Examples for Phase 1.A

## Quick API Test (PowerShell)

### 1. Create Anonymous Session

```powershell
# Basic session creation
$response = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/auth/session" `
  -ContentType "application/json" `
  -Body '{"language": "en"}'

$response | ConvertTo-Json -Depth 10

# Save token for later use
$token = $response.token
Write-Host "Token: $token"
```

### 2. Create Session with Filipino Language

```powershell
$response = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/auth/session" `
  -ContentType "application/json" `
  -Body '{"language": "fil"}'

$response | ConvertTo-Json -Depth 10
```

### 3. Create Session with Metadata

```powershell
$body = @{
    language = "en"
    metadata = @{
        userAgent = "Mozilla/5.0"
        platform = "web"
        version = "1.0.0"
    }
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/auth/session" `
  -ContentType "application/json" `
  -Body $body

$response | ConvertTo-Json -Depth 10
```

### 4. Test Protected Endpoint (Future)

```powershell
# Once chat endpoints are implemented
$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}

$chatBody = @{
    message = "What are my rights as an employee?"
    language = "en"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/chat/message" `
  -Headers $headers `
  -Body $chatBody
```

---

## Using curl (Cross-platform)

### 1. Create Session

```bash
curl -X POST http://localhost:8000/api/v1/auth/session \
  -H "Content-Type: application/json" \
  -d '{"language": "en"}'
```

### 2. With Pretty JSON Output

```bash
curl -X POST http://localhost:8000/api/v1/auth/session \
  -H "Content-Type: application/json" \
  -d '{"language": "fil"}' | jq '.'
```

### 3. Save Token to Variable

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/session \
  -H "Content-Type: application/json" \
  -d '{"language": "en"}' | jq -r '.token')

echo "Token: $TOKEN"
```

### 4. Use Token in Protected Request

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

---

## Using Python Requests

### 1. Create Session

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/auth/session",
    json={"language": "en"}
)

session_data = response.json()
print(f"Session ID: {session_data['sessionId']}")
print(f"Token: {session_data['token'][:50]}...")
```

### 2. Complete Example with Protected Endpoint

```python
import requests

# Create session
session_response = requests.post(
    "http://localhost:8000/api/v1/auth/session",
    json={"language": "en"}
)

token = session_response.json()['token']

# Use session for chat (once implemented)
headers = {
    "Authorization": f"Bearer {token}"
}

chat_response = requests.post(
    "http://localhost:8000/api/v1/chat/message",
    headers=headers,
    json={
        "message": "What are my rights regarding overtime pay?",
        "language": "en"
    }
)

print(chat_response.json())
```

---

## Using JavaScript/Fetch

### 1. Create Session

```javascript
async function createSession() {
  const response = await fetch('http://localhost:8000/api/v1/auth/session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      language: 'en'
    })
  });
  
  const data = await response.json();
  console.log('Session ID:', data.sessionId);
  console.log('Token:', data.token);
  
  return data.token;
}

createSession();
```

### 2. Use Token in Protected Request

```javascript
async function sendChatMessage(token, message) {
  const response = await fetch('http://localhost:8000/api/v1/chat/message', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: message,
      language: 'en'
    })
  });
  
  const data = await response.json();
  console.log('Response:', data);
  
  return data;
}

// Usage
const token = await createSession();
await sendChatMessage(token, 'What are my labor rights?');
```

---

## Postman Collection

### Create Session Request

**Method**: POST  
**URL**: `http://localhost:8000/api/v1/auth/session`  
**Headers**:
- Content-Type: application/json

**Body** (raw JSON):
```json
{
  "language": "en",
  "metadata": {
    "userAgent": "Postman",
    "testMode": true
  }
}
```

**Tests** (optional):
```javascript
// Parse response
const response = pm.response.json();

// Validate response
pm.test("Status is 201", () => {
    pm.response.to.have.status(201);
});

pm.test("Response has sessionId", () => {
    pm.expect(response).to.have.property('sessionId');
});

pm.test("Response has token", () => {
    pm.expect(response).to.have.property('token');
});

// Save token to environment
pm.environment.set("auth_token", response.token);
pm.environment.set("session_id", response.sessionId);
```

---

## Expected Response

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJzZXNzaW9uX2lkIjoiNTUwZTg0MDAtZTI5Yi00MWQ0LWE3MTYtNDQ2NjU1NDQwMDAwIiwibGFuZ3VhZ2UiOiJlbiIsImV4cCI6MTczMDQ2MzYwMCwiaWF0IjoxNzI5ODU4ODAwLCJ0eXBlIjoiYW5vbnltb3VzIiwibWV0YWRhdGEiOnt9fQ.abc123xyz",
  "expiresAt": "2025-11-07T12:00:00.000000Z",
  "expiresIn": 604800,
  "language": "en",
  "createdAt": "2025-10-31T12:00:00.000000Z"
}
```

---

## Error Responses

### Invalid Language Code

**Request**:
```json
{
  "language": "invalid"
}
```

**Response (422)**:
```json
{
  "detail": [
    {
      "type": "string_pattern_mismatch",
      "loc": ["body", "language"],
      "msg": "String should match pattern '^(en|fil|ceb)$'",
      "input": "invalid"
    }
  ]
}
```

### Supabase Anonymous Auth Disabled

**Response (500)**:
```json
{
  "error": {
    "code": "SESSION_CREATION_FAILED",
    "message": "Failed to create session"
  }
}
```

---

## Integration Test

### Complete Flow Test

```python
import requests
import time

def test_complete_auth_flow():
    """Test the complete authentication flow."""
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Create session
    print("1. Creating session...")
    response = requests.post(
        f"{base_url}/auth/session",
        json={"language": "en"}
    )
    assert response.status_code == 201
    
    session = response.json()
    token = session['token']
    print(f"   ✓ Session created: {session['sessionId']}")
    
    # 2. Verify token format
    print("2. Verifying token format...")
    parts = token.split('.')
    assert len(parts) == 3
    print(f"   ✓ Token is valid JWT format")
    
    # 3. Check expiration
    print("3. Checking expiration...")
    from datetime import datetime
    created = datetime.fromisoformat(session['createdAt'].replace('Z', '+00:00'))
    expires = datetime.fromisoformat(session['expiresAt'].replace('Z', '+00:00'))
    duration = (expires - created).total_seconds()
    assert duration == session['expiresIn']
    print(f"   ✓ Token expires in {session['expiresIn']} seconds")
    
    # 4. Use token (once chat endpoints are available)
    print("4. Token ready for use in chat requests")
    print(f"   Authorization: Bearer {token[:50]}...")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_complete_auth_flow()
```

---

## Next Steps

1. **Enable Supabase Anonymous Auth** (required)
2. **Start the server**: `uvicorn app.main:app --reload`
3. **Run any of the above tests**
4. **Verify** the response matches expected format
5. **Save the token** for use in future chat requests

Once Phase 1.B and 1.C are complete, you'll use this token to authenticate all chat and conversation API requests.
