# Backend API Specifications for Labor Law Chatbot

**Version:** 1.0.0  
**Last Updated:** October 31, 2025  
**Frontend Repository:** LEO-Frontend

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Core API Endpoints](#core-api-endpoints)
4. [Data Models](#data-models)
5. [Error Handling](#error-handling)
6. [Rate Limiting & Performance](#rate-limiting--performance)
7. [Multilingual Support](#multilingual-support)
8. [Security Considerations](#security-considerations)

---

## Overview

This document specifies the backend API requirements for the Labor Law Chatbot frontend application. The API must support:

- **Real-time chat messaging** with LLM-powered legal responses
- **Conversation management** (create, read, update, delete, archive)
- **Feedback and rating system** for AI responses
- **Citation validation and enrichment**
- **Multilingual support** (English, Filipino/Tagalog, Cebuano)
- **User analytics and feedback collection**

### Technology Requirements

- RESTful API architecture (recommended) or GraphQL
- JSON request/response format
- HTTPS only (SSL/TLS required)
- CORS support for frontend domain
- WebSocket support (optional, for real-time streaming)

---

## Authentication & Authorization

### Authentication Method

**Recommended:** JWT (JSON Web Tokens) or OAuth 2.0

```http
Authorization: Bearer <token>
```

### Endpoints

#### 1. User Registration (Future)
```http
POST /api/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "preferredLanguage": "fil"
}
```

**Response:** `201 Created`
```json
{
  "userId": "uuid-v4",
  "email": "user@example.com",
  "token": "jwt-token",
  "expiresIn": 3600
}
```

#### 2. Anonymous Session Creation (Current Priority)
```http
POST /api/auth/session
```

**Request Body:**
```json
{
  "preferredLanguage": "en",
  "deviceInfo": {
    "userAgent": "Mozilla/5.0...",
    "timezone": "Asia/Manila"
  }
}
```

**Response:** `201 Created`
```json
{
  "sessionId": "anonymous-session-uuid",
  "token": "temporary-jwt-token",
  "expiresIn": 86400
}
```

---

## Core API Endpoints

### 1. Chat Message API

#### Send Message and Get AI Response

```http
POST /api/chat/message
```

**Request Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
Accept-Language: en | fil | ceb
```

**Request Body:**
```json
{
  "conversationId": "conv-uuid-v4",
  "message": "What are my rights if I'm terminated?",
  "language": "en",
  "context": {
    "previousMessageIds": ["msg-uuid-1", "msg-uuid-2"],
    "userMetadata": {
      "employmentType": "regular",
      "industry": "IT"
    }
  }
}
```

**Response:** `200 OK`
```json
{
  "messageId": "msg-uuid-v4",
  "role": "assistant",
  "content": "Under Article 279 of the Labor Code of the Philippines...",
  "timestamp": "2025-10-31T10:30:00Z",
  "citations": [
    {
      "id": "cite-uuid-1",
      "text": "Regular employees are entitled to security of tenure.",
      "source": "Labor Code of the Philippines",
      "article": "Article 279",
      "url": "https://www.dole.gov.ph/labor-code-of-the-philippines/",
      "confidence": 0.95
    }
  ],
  "suggestions": [
    {
      "id": "action-1",
      "type": "contact",
      "label": "Contact DOLE",
      "data": {
        "name": "Department of Labor and Employment",
        "hotline": "1349",
        "email": "dolero4a@gmail.com",
        "website": "https://www.dole.gov.ph"
      }
    },
    {
      "id": "action-2",
      "type": "form",
      "label": "File SEnA Request",
      "data": {
        "formName": "Single Entry Approach (SEnA)",
        "instructions": [
          "Go to nearest DOLE office",
          "Fill out SEnA Request Form",
          "Submit with supporting documents"
        ],
        "downloadUrl": "https://www.dole.gov.ph/sena-request-form/"
      }
    },
    {
      "id": "action-3",
      "type": "link",
      "label": "Find a Lawyer",
      "data": {
        "url": "https://www.pao.gov.ph",
        "external": true
      }
    }
  ],
  "metadata": {
    "processingTime": 1.5,
    "model": "gpt-4",
    "confidence": 0.92,
    "disclaimerRequired": true
  }
}
```

**Error Response:** `400 Bad Request`
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Message content is required",
    "field": "message",
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

**Error Response:** `429 Too Many Requests`
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait before sending another message.",
    "retryAfter": 60,
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

---

### 2. Conversation Management API

#### Create New Conversation

```http
POST /api/conversations
```

**Request Body:**
```json
{
  "title": "Question about overtime pay",
  "language": "en",
  "metadata": {
    "source": "web_app",
    "tags": ["overtime", "compensation"]
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "conv-uuid-v4",
  "title": "Question about overtime pay",
  "language": "en",
  "createdAt": "2025-10-31T10:30:00Z",
  "updatedAt": "2025-10-31T10:30:00Z",
  "messageCount": 0,
  "archived": false
}
```

#### Get All Conversations

```http
GET /api/conversations?limit=20&offset=0&archived=false
```

**Query Parameters:**
- `limit` (optional): Number of conversations to return (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)
- `archived` (optional): Include archived conversations (default: false)
- `search` (optional): Search query for title/content
- `language` (optional): Filter by language (en, fil, ceb)

**Response:** `200 OK`
```json
{
  "conversations": [
    {
      "id": "conv-uuid-1",
      "title": "Overtime pay questions",
      "language": "en",
      "lastMessage": "Thank you for your question about overtime...",
      "messageCount": 5,
      "createdAt": "2025-10-31T09:00:00Z",
      "updatedAt": "2025-10-31T10:30:00Z",
      "archived": false
    }
  ],
  "pagination": {
    "total": 45,
    "limit": 20,
    "offset": 0,
    "hasMore": true
  }
}
```

#### Get Conversation by ID

```http
GET /api/conversations/:conversationId
```

**Response:** `200 OK`
```json
{
  "id": "conv-uuid-1",
  "title": "Overtime pay questions",
  "language": "en",
  "createdAt": "2025-10-31T09:00:00Z",
  "updatedAt": "2025-10-31T10:30:00Z",
  "messageCount": 5,
  "archived": false,
  "messages": [
    {
      "id": "msg-uuid-1",
      "role": "user",
      "content": "What are my overtime rights?",
      "timestamp": "2025-10-31T09:00:00Z"
    },
    {
      "id": "msg-uuid-2",
      "role": "assistant",
      "content": "Under Article 87...",
      "timestamp": "2025-10-31T09:00:15Z",
      "citations": [...],
      "suggestions": [...],
      "feedback": {
        "rating": 5,
        "flagged": false,
        "timestamp": "2025-10-31T09:05:00Z"
      }
    }
  ]
}
```

#### Update Conversation

```http
PATCH /api/conversations/:conversationId
```

**Request Body:**
```json
{
  "title": "Updated conversation title",
  "archived": true
}
```

**Response:** `200 OK`
```json
{
  "id": "conv-uuid-1",
  "title": "Updated conversation title",
  "archived": true,
  "updatedAt": "2025-10-31T10:35:00Z"
}
```

#### Delete Conversation

```http
DELETE /api/conversations/:conversationId
```

**Response:** `204 No Content`

#### Export Conversation

```http
GET /api/conversations/:conversationId/export?format=txt
```

**Query Parameters:**
- `format`: Export format (txt, pdf, json)

**Response:** `200 OK`
```
Content-Type: text/plain
Content-Disposition: attachment; filename="conversation_2025-10-31.txt"

Labor Law Chatbot - Conversation Export
Date: October 31, 2025
Title: Overtime pay questions
Language: English

---

[User - 09:00 AM]
What are my overtime rights?

[LEO - 09:00 AM]
Under Article 87 of the Labor Code of the Philippines...

Citations:
1. Labor Code of the Philippines, Article 87
   "Work performed beyond eight hours a day..."
   Source: https://www.dole.gov.ph/labor-code/

---
```

---

### 3. Feedback & Rating API

#### Submit Message Rating

```http
POST /api/feedback/rating
```

**Request Body:**
```json
{
  "messageId": "msg-uuid-2",
  "conversationId": "conv-uuid-1",
  "rating": 5,
  "language": "en",
  "metadata": {
    "userAgent": "Mozilla/5.0...",
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

**Response:** `201 Created`
```json
{
  "feedbackId": "feedback-uuid-1",
  "messageId": "msg-uuid-2",
  "rating": 5,
  "timestamp": "2025-10-31T10:30:00Z"
}
```

#### Flag Message as Incorrect

```http
POST /api/feedback/flag
```

**Request Body:**
```json
{
  "messageId": "msg-uuid-2",
  "conversationId": "conv-uuid-1",
  "flagged": true,
  "flagReason": "Incorrect Law Citation - The cited article doesn't match the explanation",
  "language": "en",
  "metadata": {
    "userAgent": "Mozilla/5.0...",
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

**Response:** `201 Created`
```json
{
  "feedbackId": "feedback-uuid-2",
  "messageId": "msg-uuid-2",
  "flagged": true,
  "flagReason": "Incorrect Law Citation - The cited article doesn't match the explanation",
  "timestamp": "2025-10-31T10:30:00Z",
  "status": "pending_review"
}
```

#### Get Feedback Statistics

```http
GET /api/feedback/stats?conversationId=conv-uuid-1
```

**Response:** `200 OK`
```json
{
  "conversationId": "conv-uuid-1",
  "totalRatings": 5,
  "averageRating": 4.6,
  "totalFlagged": 1,
  "ratingDistribution": {
    "1": 0,
    "2": 0,
    "3": 1,
    "4": 1,
    "5": 3
  },
  "commonFlagReasons": [
    {
      "reason": "Incorrect Law Citation",
      "count": 1
    }
  ]
}
```

---

### 4. Search API

#### Search Conversations

```http
GET /api/search/conversations?q=overtime&language=en&limit=10
```

**Query Parameters:**
- `q`: Search query (required)
- `language`: Filter by language (optional)
- `limit`: Max results (default: 10, max: 50)
- `offset`: Pagination offset (default: 0)

**Response:** `200 OK`
```json
{
  "results": [
    {
      "id": "conv-uuid-1",
      "title": "Overtime pay questions",
      "snippet": "...What are my <mark>overtime</mark> rights?...",
      "language": "en",
      "relevanceScore": 0.95,
      "timestamp": "2025-10-31T09:00:00Z"
    }
  ],
  "pagination": {
    "total": 3,
    "limit": 10,
    "offset": 0
  }
}
```

---

## Data Models

### Message Model

```typescript
interface Message {
  id: string;                    // UUID v4
  conversationId: string;        // UUID v4
  role: 'user' | 'assistant';
  content: string;               // Message text content
  timestamp: string;             // ISO 8601 timestamp
  citations?: Citation[];        // Legal citations (assistant only)
  suggestions?: SuggestedAction[]; // Suggested actions (assistant only)
  feedback?: MessageFeedback;    // User feedback
  metadata?: {
    processingTime?: number;     // Seconds (assistant only)
    model?: string;              // LLM model used
    confidence?: number;         // 0-1 confidence score
    tokensUsed?: number;
  };
}
```

### Citation Model

```typescript
interface Citation {
  id: string;                    // UUID v4
  text: string;                  // Exact legal text quoted
  source: string;                // e.g., "Labor Code of the Philippines"
  article?: string;              // e.g., "Article 87"
  url?: string;                  // Link to official source
  confidence?: number;           // 0-1 confidence in citation accuracy
  section?: string;              // Section/paragraph reference
  effectiveDate?: string;        // When this law took effect
  amendedBy?: string;            // Reference to amendments
}
```

### Suggested Action Model

```typescript
type ActionType = 'query' | 'link' | 'info' | 'contact' | 'form';

interface SuggestedAction {
  id: string;                    // UUID v4
  type: ActionType;
  label: string;                 // Display text
  data: ActionData;              // Type-specific data
}

type ActionData = 
  | QueryActionData 
  | LinkActionData 
  | InfoActionData 
  | ContactActionData 
  | FormActionData;

interface ContactActionData {
  name: string;
  hotline?: string;
  email?: string;
  website?: string;
  address?: string;
}

interface FormActionData {
  formName: string;
  instructions: string[];
  downloadUrl?: string;
  requiredDocuments?: string[];
}

interface LinkActionData {
  url: string;
  external?: boolean;
  description?: string;
}

interface QueryActionData {
  query: string;                 // Follow-up question
  context?: string;
}

interface InfoActionData {
  title: string;
  content: string;
  icon?: string;
}
```

### Conversation Model

```typescript
interface Conversation {
  id: string;                    // UUID v4
  title: string;                 // Max 100 chars
  language: 'en' | 'fil' | 'ceb';
  lastMessage: string;           // First 100 chars of last message
  messageCount: number;
  createdAt: string;             // ISO 8601
  updatedAt: string;             // ISO 8601
  archived: boolean;
  metadata?: {
    tags?: string[];
    source?: string;             // 'web_app', 'mobile', etc.
    userContext?: Record<string, any>;
  };
}
```

### Feedback Model

```typescript
interface MessageFeedback {
  rating?: 1 | 2 | 3 | 4 | 5;
  flagged?: boolean;
  flagReason?: string;
  timestamp: string;             // ISO 8601
}

interface FeedbackData {
  id: string;                    // UUID v4
  messageId: string;             // UUID v4
  conversationId: string;        // UUID v4
  rating?: 1 | 2 | 3 | 4 | 5;
  flagged?: boolean;
  flagReason?: string;
  language: 'en' | 'fil' | 'ceb';
  timestamp: string;             // ISO 8601
  metadata?: {
    userAgent?: string;
    resolved?: boolean;
    resolvedBy?: string;
    resolvedAt?: string;
  };
}
```

---

## Error Handling

### Error Response Format

All errors should follow this structure:

```typescript
interface ErrorResponse {
  error: {
    code: string;                // Error code (see codes below)
    message: string;             // Human-readable error message
    field?: string;              // Field name for validation errors
    details?: any;               // Additional error context
    timestamp: string;           // ISO 8601
    requestId?: string;          // For tracking/debugging
  }
}
```

### Error Codes

| HTTP Status | Error Code | Description | Retryable |
|------------|------------|-------------|-----------|
| 400 | `VALIDATION_ERROR` | Invalid request data | No |
| 401 | `UNAUTHORIZED` | Missing/invalid authentication | No |
| 403 | `FORBIDDEN` | Insufficient permissions | No |
| 404 | `NOT_FOUND` | Resource not found | No |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests | Yes |
| 500 | `INTERNAL_SERVER_ERROR` | Server error | Yes |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily down | Yes |
| 504 | `GATEWAY_TIMEOUT` | LLM API timeout | Yes |

### Multilingual Error Messages

Errors should be returned in the user's language (from `Accept-Language` header):

**English:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait before sending another message.",
    "retryAfter": 60,
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

**Filipino:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Masyadong maraming kahilingan. Maghintay bago magpadala ng mensahe.",
    "retryAfter": 60,
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

**Cebuano:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Daghan kaayo nga mga hangyo. Palihug paghulat sa dili pa magpadala og mensahe.",
    "retryAfter": 60,
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

---

## Rate Limiting & Performance

### Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /api/chat/message` | 10 requests | per minute |
| `POST /api/conversations` | 20 requests | per hour |
| `GET /api/conversations` | 100 requests | per minute |
| `POST /api/feedback/*` | 50 requests | per hour |

### Rate Limit Headers

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1698745800
```

### Performance Requirements

| Metric | Target | Critical |
|--------|--------|----------|
| Chat message response time | < 5 seconds | < 10 seconds |
| Conversation list load | < 500ms | < 2 seconds |
| Search results | < 1 second | < 3 seconds |
| API availability | 99.5% uptime | 99% uptime |

---

## Multilingual Support

### Language Detection

The API should support language detection and code-switching:

**Request:**
```json
{
  "message": "Ano ang overtime pay ko if I work beyond 8 hours?",
  "language": "fil",
  "autoDetectLanguage": true
}
```

**Response:**
The API should detect Taglish (Filipino-English code-switching) and respond appropriately in Filipino with natural English technical terms where appropriate.

### Supported Languages

| Code | Language | Native Name |
|------|----------|-------------|
| `en` | English | English |
| `fil` | Filipino (Tagalog) | Filipino |
| `ceb` | Cebuano (Bisaya) | Binisaya |

### Translation Guidelines

1. **Legal Terms**: Keep Philippine legal terms in English even in local language responses (e.g., "Article 87", "Labor Code", "DOLE")
2. **Code-Switching**: Support natural code-switching in both questions and responses
3. **Formality**: Maintain formal but friendly tone across all languages
4. **Cultural Context**: Adapt examples and explanations to Philippine context

---

## Security Considerations

### Data Privacy

1. **Personal Information**: Never log or store personally identifiable information (PII) from conversations
2. **Conversation Data**: Encrypt conversations at rest
3. **Session Data**: Use secure, httpOnly cookies for session management
4. **Data Retention**: Auto-delete anonymous sessions after 90 days of inactivity

### Input Validation

1. **Message Length**: Limit messages to 2000 characters
2. **Content Filtering**: Reject messages with:
   - Excessive special characters
   - Potential injection attacks
   - Inappropriate content
3. **Sanitization**: Strip HTML/script tags from all user input

### CORS Configuration

```javascript
// Allowed origins (production)
Access-Control-Allow-Origin: https://labor-law-chatbot.ph
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization, Accept-Language
Access-Control-Max-Age: 86400
```

### API Security Headers

```http
Content-Security-Policy: default-src 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Implementation Priority

### Phase 1: MVP (Critical)

1. ✅ **Chat Message API** (`POST /api/chat/message`)
   - Basic LLM integration
   - Citation generation
   - Suggested actions

2. ✅ **Conversation Management**
   - Create conversation
   - Get conversations
   - Get conversation by ID

3. ✅ **Feedback API**
   - Message rating
   - Flag incorrect responses

### Phase 2: Enhanced Features

4. **Advanced Conversation Features**
   - Search conversations
   - Export conversations (TXT, PDF)
   - Archive/unarchive

5. **Analytics & Monitoring**
   - Feedback statistics
   - Usage analytics
   - Performance monitoring

### Phase 3: Advanced Features

6. **User Accounts** (Optional)
   - User registration/login
   - Cross-device sync
   - Conversation sharing

7. **Real-time Features** (Optional)
   - WebSocket support for streaming responses
   - Live typing indicators
   - Real-time notifications

---

## Testing Requirements

### API Testing

1. **Unit Tests**: All endpoints must have unit test coverage
2. **Integration Tests**: Test LLM integration with mock responses
3. **Load Tests**: Support 100 concurrent users minimum
4. **Language Tests**: Verify multilingual responses for all languages

### Sample Test Cases

**Chat Message API:**
- ✅ Valid message returns proper response structure
- ✅ Multilingual input is handled correctly
- ✅ Citations are properly formatted and validated
- ✅ Suggested actions match user's language
- ✅ Rate limiting is enforced
- ✅ Long messages (>2000 chars) are rejected

**Feedback API:**
- ✅ Valid ratings (1-5) are accepted
- ✅ Invalid ratings are rejected
- ✅ Duplicate ratings update existing feedback
- ✅ Flag reasons are stored correctly

---

## API Versioning

### Version Strategy

Use URL versioning:
```
https://api.labor-law-chatbot.ph/v1/chat/message
```

### Deprecation Policy

- Minimum 6 months notice before deprecating any endpoint
- Old versions supported for 12 months after new version release
- Clear migration guides provided

---

## Monitoring & Logging

### Required Logs

1. **Request Logs**
   - Endpoint called
   - Response time
   - Status code
   - User language preference

2. **Error Logs**
   - Error type and message
   - Stack trace (sanitized)
   - Request ID for tracking
   - User session (anonymized)

3. **Business Metrics**
   - Messages per day
   - Average response time
   - User satisfaction (ratings)
   - Most common topics/questions
   - Flag rate (% of responses flagged)

### Alerts

- API response time > 10 seconds
- Error rate > 5%
- Flag rate > 10%
- Rate limit violations > 100/hour

---

## Additional Resources

### Related Documents

- [Frontend Copilot Instructions](../.github/copilot-instructions.md)
- [UI/UX Design Requirements](../UI-UX_DESIGN_REQUIREMENTS.md)
- [Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)

### External References

- [DOLE Website](https://www.dole.gov.ph)
- [Labor Code of the Philippines](https://www.dole.gov.ph/labor-code-of-the-philippines/)
- [Philippine Laws and Jurisprudence](https://elibrary.judiciary.gov.ph/)

---

## Changelog

### Version 1.0.0 (October 31, 2025)
- Initial API specification
- Core chat, conversation, and feedback endpoints
- Multilingual support requirements
- Security and performance guidelines

---

**For Questions or Clarifications:**  
Please refer to the frontend source code in `src/` directory or consult the development team.
