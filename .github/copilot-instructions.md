# LEO Backend: Philippine Labor Law Chatbot

Build a robust backend for **LEO**, a multi-turn, citation-driven chatbot focused on **Philippine labor law**
that also provides context-aware suggested actions to users.The system uses **Python 3.11+** and **FastAPI** 
to deliver a scalable, modular **RAG (retrieval-augmented generation)** pipeline with multilingual support 
(English, Filipino, Cebuano).

---

## Tech Stack

- **FastAPI** – REST API with Server-Sent Events (SSE) for streaming chat  
- **Supabase Postgres + pgvector** – persistent, cloud-hosted embeddings with HNSW indexes  
- **OpenAI GPT-4 Turbo** – conversational grounding with streaming, natural citations  
- **OpenAI GPT-4o-mini** – fast query analysis with smart clarification detection
- **OpenAI text-embedding-3-small** – for embeddings (swappable via adapter) with LRU cache  
- **LangChain** – multi-turn chat memory (conversation history only)  
- **PostgreSQL Full-Text Search** – keyword-based retrieval with GIN indexes
- **Google Cloud Translation API v3** – conditional fallback for Cebuano/low-confidence detection  
- **Google Maps Places API** *(optional)* – for legal aid referrals  
- **DistilBERT** – intent classifier (confidence-gated, improves retrieval focus)  
- **Safety** – OpenAI moderation, domain guardrails, auto-disclaimer post-processing  

---

## Features

- Multi-turn chat with memory and **smart LLM-based clarification** for vague queries  
- **Streaming responses** via Server-Sent Events (SSE) for improved perceived performance
- **Multi-strategy retrieval**: keyword search + semantic search + direct article lookup
- Multilingual input normalization and output (English, Filipino, Cebuano)  
- Citation-driven answers with strict context grounding  
- **Context-aware conversation handling** with pronoun resolution and follow-up detection
- Optional location-based legal aid referrals  
- Modular adapters for easy provider/model swaps  

---

## Implementation Guidelines

### Development Principles

**1. Modular Architecture**
- Implement clean separation between API layer, business logic, and infrastructure
- Use dependency injection for all external services (databases, APIs, models)
- Create adapter patterns for swappable components (embeddings, LLMs, translation services)
- Follow domain-driven design principles with clear bounded contexts

**2. Code Quality Standards**
- Follow PEP 8 style guidelines with Black formatter
- Implement comprehensive type hints using Python 3.11+ features
- Write docstrings for all public methods using Google/NumPy style
- Maintain test coverage above 80% with pytest
- Use pre-commit hooks for code quality enforcement

**3. Error Handling & Resilience**
- Implement graceful degradation for external service failures
- Use circuit breaker patterns for API calls
- Add comprehensive logging with structured JSON format
- Implement retry mechanisms with exponential backoff
- Create custom exception classes for domain-specific errors

**4. Security & Safety**
- Validate all inputs with Pydantic models
- Implement rate limiting and request throttling
- Add OpenAI moderation checks for user inputs
- Use environment variables for all sensitive configuration
- Implement proper CORS and security headers

**5. Performance & Scalability**
- Use async/await patterns throughout the application
- Implement connection pooling for database operations
- Add caching layers for frequently accessed data
- Use background tasks for non-blocking operations
- Optimize database queries with proper indexing

**6. Configuration Management**
- Use Pydantic Settings for configuration validation
- Support multiple environments (dev, staging, prod)
- Implement feature flags for gradual rollouts
- Use dependency injection for configuration access

**7. Testing Strategy**
- Write unit tests for all business logic
- Create integration tests for API endpoints
- Mock external dependencies in tests
- Use factories for test data generation
- Implement contract testing for external APIs

**8. Documentation & Monitoring**
- Generate OpenAPI documentation automatically
- Add health check endpoints for monitoring
- Implement structured logging for observability
- Create deployment and setup documentation
- Add performance metrics and monitoring hooks

# Modular & scalable folder structure

> Goal: easy to swap models/providers/stores; clean separation of API, domain, adapters, and infra. Also friendly to tests and CI/CD.

Adopt a clean layered architecture with clear boundaries with caveats in boilerplate, learning curve, and slight performance overhead due to DI.
### Mitigations
- Comprehensive documentation and examples
- Code generation tools for adapters
- Architecture decision records
- refer to docs/adr/001-architecture-and-boundaries.md

```
leo-backend/
├─ api/
│  ├─ v1/
│  │  ├─ routes_chat.py           # POST /v1/chat
│  │  ├─ routes_embed.py          # POST /v1/embed
│  │  ├─ routes_health.py         # GET /v1/healthz, /v1/readyz
│  │  ├─ routes_maps.py           # GET /v1/nearby-legal-aid
│  │  └─ __init__.py
│  ├─ deps.py                     # FastAPI Depends() providers (auth, rate limit, svc locators)
│  └─ __init__.py
├─ core/
│  ├─ config.py                   # Pydantic Settings + runtime flags (ENABLE_TRANSLATION, etc.)
│  ├─ logging.py                  # JSON logs for Cloud Run (uvicorn + structlog)
│  ├─ exceptions.py               # AppError, ValidationError, HTTP mapping
│  ├─ rate_limit.py               # token-bucket or Redis stub (optional)
│  └─ __init__.py
├─ app/                           # Application composition (wires API ↔ services)
│  ├─ main.py                     # FastAPI app factory, routers mount, lifespan hooks
│  ├─ settings.py                 # (thin wrapper around core.config for app-level usage)
│  ├─ containers.py               # lightweight DI/service locator (construct adapters)
│  └─ middleware/
│     ├─ request_id.py
│     └─ cors.py
├─ services/                      # "Use-cases" (pure business flow, no HTTP or SDK specifics)
│  ├─ pipeline/
│  │  ├─ conversation.py           # manages chat history, memory state
│  │  ├─ query_analysis.py         # GPT-4o-mini: smart clarification + concept extraction
│  │  ├─ nlp_ingress.py            # lang detect → (optional) translate → (optional) intent
│  │  ├─ retrieval.py              # multi-strategy: keyword + semantic + direct article lookup
│  │  ├─ grounding.py              # construct rich-context prompt for GPT-4.1 streaming
│  │  ├─ generation.py             # call LLM with streaming support (SSE)
│  │  └─ postprocess.py            # disclaimers, linkify, redaction
│  ├─ chat_orchestrator.py        # coordinates full RAG pipeline with smart clarification
│  ├─ maps_referral.py            # high-level "find nearest legal aid"
│  ├─ moderation.py               # policy guardrails + model moderation result mapping
│  └─ __init__.py
├─ adapters/                      # All external I/O; each has base interface + impl
│  ├─ llm/
│  │  ├─ base.py                  # interface: generate(), stream()
│  │  └─ openai_llm.py            # GPT-4.1 with streaming support
│  ├─ embeddings/
│  │  ├─ base.py                  # embed_text(), embed_batch()
│  │  └─ openai_embed.py          # text-embedding-3-small with LRU cache
│  ├─ vectorstore/
│  │  ├─ base.py                  # upsert(), query(), delete()
│  │  └─ supabase_store.py        # multi-strategy: keyword + semantic + direct lookup
│  │  └─ memory/                  # HNSW index, connection pooling, embedding cache
│  │     ├─ base.py              # abstract MemoryStore interface (get, append)
│  │     ├─ redis_memory.py      # optional runtime cache
│  │     └─ langchain_memory.py  # wrapper around LangChain ConversationBuffer
│  ├─ translate/
│  │  ├─ base.py                  # translate(text, src, tgt)
│  │  └─ gtranslate.py
│  ├─ maps/
│  │  ├─ base.py                  # nearby_places(lat,lng,types,limit)
│  │  └─ google_places.py
│  ├─ moderation/
│  │  ├─ base.py                  # check(text) -> label/score
│  │  └─ openai_moderation.py
│  └─ __init__.py
├─ nlp/
│  ├─ lang_detect/
│  │  ├─ fasttext_detector.py     # returns (lang, confidence, is_mixed)
│  │  └─ resources/               # lid.176.bin (mounted at runtime)
│  ├─ intent/
│  │  ├─ distilbert_classifier.py # torch/transformers or ONNX
│  │  └─ taxonomy.py              # Table-1 categories, id↔label map
│  └─ heuristics.py               # quick domain/out-of-scope checks
├─ retrieval/
│  ├─ chunking.py                 # KB splitting rules (conditional: only for >1000 word articles)
│  └─ ranking.py                  # result merging, deduplication, and ranking algorithm
├─ kb/
│  ├─ docs/                       # raw legal texts/handbooks
│  ├─ ingest/
│  │  ├─ loaders/                 # pdf/docx/html loaders
│  │  ├─ normalizers/             # clean → md/txt + metadata
│  │  └─ sync_to_vectorstore.py   # CLI: index to Supabase
│  └─ manifests/                  # provenance + changelog
├─ utils/
│  ├─ redact.py
│  ├─ timing.py
│  └─ ids.py
├─ tests/
│  ├─ unit/                       # adapters, services, nlp
│  ├─ integration/                # end-to-end chat happy-path
│  └─ data/
├─ infra/
│  ├─ Dockerfile
│  ├─ cloudrun.yaml               # service config (CPU=OnDemand, concurrency, min instances)
│  ├─ supabase/
│  │  ├─ schema.sql               # tables with HNSW indexes, GIN for FTS, pgvector ext, RLS
│  │  └─ seed.sql                 # optional
│  └─ terraform/
│     ├─ modules/
│     │  ├─ cloud_run_service/
│     │  ├─ artifact_registry/
│     │  ├─ secret_manager/
│     │  ├─ supabase_init/        # alt: invoke SQL via pg client or use Flyway container
│     │  └─ workload_identity/
│     ├─ envs/
│     │  ├─ dev/
│     │  │  └─ main.tf
│     │  └─ prod/
│     │     └─ main.tf
│     └─ versions.tf
├─ scripts/
│  ├─ download_fasttext.sh
│  ├─ prepare_kb.py
│  └─ smoke_chat.sh
├─ .env.example
├─ pyproject.toml
└─ README.md
```

---

## API Contracts

Please refer to docs/BACKEND_API_SPECIFICATIONS.md for detailed API endpoint specifications, request/response schemas, and error codes.

## Implementation Roadmap
Please refer to the complete implementation roadmap in ImplementationSequence.md file of the root directory for detailed milestones, targets, and checklists to ensure all features are developed according to project standards.
