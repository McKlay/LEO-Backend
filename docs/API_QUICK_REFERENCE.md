# Backend API - Quick Reference Guide

**For Backend Developers** | **Last Updated:** October 31, 2025

> **Full Specification:** See [BACKEND_API_SPECIFICATIONS.md](./BACKEND_API_SPECIFICATIONS.md) for complete details.

---

## Core Requirements Summary

The frontend expects a RESTful API that supports:

1. **AI-powered chat messaging** with legal citations
2. **Conversation persistence** and management
3. **User feedback** collection (ratings + flags)
4. **Multilingual support** (English, Filipino, Cebuano)
5. **Anonymous sessions** (authentication optional for MVP)

---

## Priority Endpoints (MVP)

### 1. Send Chat Message
```http
POST /api/chat/message
Authorization: Bearer <token>
Content-Type: application/json
```

**What it needs:**
```json
{
  "conversationId": "uuid",
  "message": "What are my overtime rights?",
  "language": "en"
}
```

**What frontend expects back:**
```json
{
  "messageId": "uuid",
  "content": "Under Article 87 of the Labor Code...",
  "citations": [
    {
      "id": "uuid",
      "text": "Quote from law",
      "source": "Labor Code of the Philippines",
      "article": "Article 87",
      "url": "https://www.dole.gov.ph/..."
    }
  ],
  "suggestions": [
    {
      "id": "uuid",
      "type": "contact",
      "label": "Contact DOLE",
      "data": {
        "name": "DOLE",
        "hotline": "1349",
        "website": "https://www.dole.gov.ph"
      }
    }
  ]
}
```

**Performance:** Must respond in < 5 seconds

---

### 2. Create Conversation
```http
POST /api/conversations
```

```json
{
  "title": "Question about overtime",
  "language": "en"
}
```

**Returns:**
```json
{
  "id": "uuid",
  "title": "Question about overtime",
  "createdAt": "2025-10-31T10:30:00Z"
}
```

---

### 3. Get All Conversations
```http
GET /api/conversations?limit=20&offset=0&archived=false
```

**Returns:**
```json
{
  "conversations": [
    {
      "id": "uuid",
      "title": "Overtime questions",
      "lastMessage": "Thank you for...",
      "messageCount": 5,
      "createdAt": "2025-10-31T09:00:00Z",
      "updatedAt": "2025-10-31T10:30:00Z",
      "language": "en",
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

---

### 4. Get Conversation with Messages
```http
GET /api/conversations/:conversationId
```

**Returns:**
```json
{
  "id": "uuid",
  "title": "Overtime questions",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "What are my rights?",
      "timestamp": "2025-10-31T09:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Under Article 87...",
      "timestamp": "2025-10-31T09:00:15Z",
      "citations": [...],
      "suggestions": [...],
      "feedback": {
        "rating": 5,
        "flagged": false
      }
    }
  ]
}
```

---

### 5. Update Conversation
```http
PATCH /api/conversations/:conversationId
```

**Supports:**
```json
{
  "title": "New title",
  "archived": true
}
```

---

### 6. Delete Conversation
```http
DELETE /api/conversations/:conversationId
```

Returns: `204 No Content`

---

### 7. Submit Rating
```http
POST /api/feedback/rating
```

```json
{
  "messageId": "uuid",
  "conversationId": "uuid",
  "rating": 5,
  "language": "en"
}
```

---

### 8. Flag Message
```http
POST /api/feedback/flag
```

```json
{
  "messageId": "uuid",
  "conversationId": "uuid",
  "flagged": true,
  "flagReason": "Incorrect Law Citation - Details here",
  "language": "en"
}
```

---

## Multilingual Support

### Language Codes
- `en` - English
- `fil` - Filipino (Tagalog)
- `ceb` - Cebuano (Bisaya)

### Implementation Notes
1. Detect language from `Accept-Language` header OR `language` field in request body
2. Return responses in the same language as the request
3. Keep legal terms in English even in local languages (e.g., "Article 87", "DOLE")
4. Support code-switching (e.g., Taglish: "Ano ang overtime pay ko?")

---

## Security Requirements

### Authentication (Phase 1: Optional)
```http
Authorization: Bearer <jwt-token>
```

For MVP, support **anonymous sessions**:
```http
POST /api/auth/session
{
  "preferredLanguage": "en"
}

Response:
{
  "sessionId": "uuid",
  "token": "temporary-jwt"
}
```

### Input Validation
- Max message length: 2000 characters
- Sanitize all user input (remove HTML/scripts)
- Validate language codes

### CORS
Allow: `https://labor-law-chatbot.ph` (production domain)

---

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Chat response time | < 5s | < 10s |
| Conversation list | < 500ms | < 2s |
| API availability | 99.5% | 99% |

### Rate Limits
- Chat messages: **10 per minute**
- Conversation creation: **20 per hour**
- Feedback: **50 per hour**

**Rate limit headers:**
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1698745800
```

---

## Error Handling

All errors must follow this format:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please wait.",
    "retryAfter": 60,
    "timestamp": "2025-10-31T10:30:00Z"
  }
}
```

### Error Codes
| Code | HTTP Status | Description |
|------|------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `UNAUTHORIZED` | 401 | Missing/invalid token |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_SERVER_ERROR` | 500 | Server error |

**Error messages must be multilingual** based on user's language preference.

---

## Critical Data Structures

### Citation Object (Required)
```typescript
{
  id: string;           // UUID
  text: string;         // Exact legal quote
  source: string;       // "Labor Code of the Philippines"
  article?: string;     // "Article 87"
  url?: string;         // Link to official source
  confidence?: number;  // 0-1 (how confident is the citation)
}
```

### Suggested Action Object (Required)
```typescript
{
  id: string;
  type: "contact" | "form" | "link" | "query" | "info";
  label: string;        // "Contact DOLE"
  data: {
    // For type="contact":
    name: string;
    hotline?: string;
    email?: string;
    website?: string;
    
    // For type="form":
    formName: string;
    instructions: string[];
    downloadUrl?: string;
    
    // For type="link":
    url: string;
    external?: boolean;
  }
}
```

---

## UI Implementation Details

### Citations Display
- Frontend shows citations in **collapsible section** within bot messages
- Each citation has:
  - Source name + Article reference
  - Quoted text (italicized)
  - "View Source" button (if URL provided)
  - "Related Resources" button (auto-generated by frontend)

### Suggested Actions Display
- Shown as **clickable buttons** below bot response
- Max 3-4 suggested actions per message
- Actions trigger modals or external links:
  - `contact` → Opens contact modal with DOLE info
  - `form` → Opens form modal with step-by-step instructions
  - `link` → Opens URL in new tab
  - `query` → Sends follow-up question automatically

### Feedback UI
- **Star rating (1-5)**: Inline below each bot message
- **Flag button**: "Flag as Incorrect" - opens modal with reason dropdown
- Feedback is **persistent** and saved to localStorage + backend
- Anonymous users can still provide feedback

---

## Frontend Current State

### What's Already Implemented
✅ Full chat UI with message display  
✅ Conversation sidebar with history  
✅ Citation collapsible sections  
✅ Suggested action buttons  
✅ Star rating component  
✅ Flag modal with reason categories  
✅ Multilingual support (en, fil, ceb)  
✅ LocalStorage persistence (fallback)  
✅ Error handling with toasts  
✅ Loading states and typing indicators  
✅ Accessibility features (ARIA, keyboard nav)  

### What Needs Backend
❌ Real chat API integration (currently mocked)  
❌ Conversation sync across devices  
❌ Feedback analytics/reporting  
❌ User authentication (optional for MVP)  
❌ Advanced search functionality  

---

## Implementation Steps

### Step 1: Setup
1. Create REST API with Express/FastAPI/Django
2. Setup database (PostgreSQL recommended)
3. Integrate LLM (OpenAI GPT-4.1)
4. Configure CORS for frontend domain

### Step 2: Core Endpoints (Priority)
1. `POST /api/chat/message` - Get this working first!
2. `POST /api/conversations` - Create conversations
3. `GET /api/conversations` - List conversations
4. `GET /api/conversations/:id` - Get conversation with messages

### Step 3: Feedback
5. `POST /api/feedback/rating` - Star ratings
6. `POST /api/feedback/flag` - Flag incorrect responses

### Step 4: Management
7. `PATCH /api/conversations/:id` - Update/archive
8. `DELETE /api/conversations/:id` - Delete conversations

### Step 5: Polish
9. Add rate limiting
10. Implement proper error handling
11. Add monitoring/logging
12. Performance optimization

---

## Testing Checklist

### Chat Message API
- [ ] Returns response in < 5 seconds
- [ ] Citations are valid and properly formatted
- [ ] Suggestions match user's language
- [ ] Handles code-switching (Taglish, Bislish)
- [ ] Rejects messages > 2000 characters
- [ ] Rate limiting works (10/min)

### Conversation API
- [ ] Creates conversation successfully
- [ ] Lists conversations with pagination
- [ ] Returns full conversation with messages
- [ ] Updates title and archive status
- [ ] Deletes conversation and all messages

### Feedback API
- [ ] Accepts ratings 1-5
- [ ] Rejects invalid ratings
- [ ] Stores flag reasons correctly
- [ ] Prevents duplicate feedback spam

---

## Important Contacts & Resources

### DOLE Information
- **Hotline:** 1349
- **Website:** https://www.dole.gov.ph
- **Email:** dolero4a@gmail.com

### Legal Resources
- **Labor Code:** https://www.dole.gov.ph/labor-code-of-the-philippines/
- **Supreme Court:** https://elibrary.judiciary.gov.ph/
- **SEnA Form:** https://www.dole.gov.ph/sena-request-form/

---

## Need Help?

**Full API Specification:** [BACKEND_API_SPECIFICATIONS.md](./BACKEND_API_SPECIFICATIONS.md)  
**Frontend Source Code:** `src/` directory  
**UI Requirements:** [UI-UX_DESIGN_REQUIREMENTS.md](../UI-UX_DESIGN_REQUIREMENTS.md)  
**Project Instructions:** [.github/copilot-instructions.md](../.github/copilot-instructions.md)

---

**Key Takeaway:** The frontend is **fully functional** with mock data. Backend needs to implement these 8 endpoints with proper citation generation and multilingual support to go live!
