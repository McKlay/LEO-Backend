# ADR-001: Architecture & Boundaries

**Status:** Accepted  
**Date:** 2025-10-31  
**Decision Makers:** Development Team  

## Context

We are building **LEO**, a Philippine labor law chatbot backend that must be:
- **Modular**: Easy to swap providers (OpenAI → Anthropic, Supabase → Pinecone)
- **Maintainable**: Clear separation of concerns and boundaries
- **Testable**: Comprehensive unit and integration testing
- **Production-ready**: Deployed to Google Cloud Run with proper monitoring

The system needs to support:
1. Multi-turn conversations with memory
2. RAG-based retrieval from Philippine labor law documents
3. Multilingual support (English, Filipino, Cebuano)
4. Citation-driven responses with legal compliance
5. High scalability and performance

## Decision

### 1. Layered Architecture

We adopt a clean layered architecture with clear boundaries:

```
┌─────────────────────────────────────────────┐
│           API Layer (FastAPI)               │
│  - Routes, request/response validation      │
│  - HTTP-specific concerns                   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│         Application Layer (app/)            │
│  - Application factory                      │
│  - Middleware, error handlers               │
│  - Service composition                      │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│        Services Layer (services/)           │
│  - Business logic & use cases               │
│  - Pipeline orchestration                   │
│  - Domain rules (no I/O)                    │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│        Adapters Layer (adapters/)           │
│  - External service integrations            │
│  - Base interfaces + implementations        │
│  - Swappable providers                      │
└─────────────────────────────────────────────┘
```

### 2. Adapter Pattern for External Services

All external dependencies are accessed through abstract interfaces:

- **BaseLLM**: LLM providers (OpenAI, Anthropic, etc.)
- **BaseEmbeddings**: Embedding models
- **BaseVectorStore**: Vector databases (Supabase, Pinecone)
- **BaseTranslate**: Translation services (Google, DeepL)
- **BaseMaps**: Location services (Google Maps, OSM)
- **BaseModeration**: Content moderation services
- **BaseMemory**: Conversation memory storage

This enables:
- Easy A/B testing between providers
- Quick failover to alternative services
- Simplified unit testing with mocks

### 3. Configuration Management

Using **Pydantic Settings** for type-safe configuration:
- Environment-based configuration (.env files)
- Validation at startup (fail-fast)
- Feature flags for optional services
- Multi-environment support (dev, staging, prod)

### 4. Error Handling Strategy

Centralized exception hierarchy:
- All exceptions inherit from `AppError`
- HTTP status codes mapped to exception types
- Consistent error response format
- Structured logging for debugging

### 5. Dependency Injection

Minimal DI through FastAPI's `Depends()`:
- Service instances provided through dependency functions
- Easy to override for testing
- Clear dependency graph

## Consequences

### Positive

✅ **Modularity**: Each layer has clear responsibilities  
✅ **Testability**: Easy to mock external services  
✅ **Maintainability**: Changes localized to specific layers  
✅ **Swappability**: Can replace providers without breaking changes  
✅ **Type Safety**: Pydantic models catch errors early  
✅ **Developer Experience**: Clear structure, easy onboarding  

### Negative

⚠️ **Boilerplate**: More files and interfaces required  
⚠️ **Learning Curve**: Team must understand architecture  
⚠️ **Initial Overhead**: Takes time to set up properly  

### Mitigations

- Comprehensive documentation and examples
- Code generation tools for adapters
- Architecture decision records (like this one)
- Team training sessions

## Alternatives Considered

### 1. Monolithic Service Layer

**Rejected**: Would make testing difficult and couple business logic to specific providers.

### 2. Microservices Architecture

**Rejected**: Overkill for Phase 0-1; can migrate later if needed.

### 3. Plugin-based Architecture

**Deferred**: Considered for future phases if third-party extensions needed.

## Implementation Notes

### Phase 0 (Current)

- ✅ Create folder structure
- ✅ Define base adapter interfaces
- ✅ Implement core configuration
- ✅ Setup FastAPI application
- ✅ Health check endpoints

### Future Phases

- Implement concrete adapters (OpenAI, Supabase)
- Build service layer business logic
- Add middleware (auth, rate limiting, logging)
- Implement testing strategy

## References

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [12-Factor App](https://12factor.net/)

## Review

This ADR should be reviewed after:
- Phase 1 completion (after implementing first adapters)
- Any major architectural changes
- Team feedback on developer experience
