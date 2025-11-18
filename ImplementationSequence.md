# Phased Implementation Sequence

---

## Overview

Build a Philippine labor law chatbot backend using Python/FastAPI with:
- RAG pipeline (retrieval-augmented generation)
- Multilingual support (English, Filipino, Cebuano)
- OpenAI + Supabase + Google Cloud integration
- Citation-driven responses with suggested actions
- Multi-turn capability via Langchain memory + clarification branch for vague queries.

---

## PHASE-0 — Repo Scaffold & Contracts (1–2 days)

**Goals**

* Lock folder structure, envs, and API contracts.

**Tasks**

* Initialize repo with final tree (api/core/app/services/adapters/nlp/kb/infra/tests).
* Implement `core.config`, JSON logging, exception map.
* Wire `app/main.py` with `/v1/healthz` + readiness.
* Stub adapters’ `base.py` interfaces (LLM, embeddings, vectorstore, translate, maps, moderation).
* Create `.env.example`, `Dockerfile`, `cloudrun.yaml`.

**Deliverables**

* Running FastAPI service: `/v1/healthz` returns 200.
* ADR-001: “Architecture & Boundaries”.

**Exit criteria**

* Static type check + unit test pipeline green.

---

## PHASE-1 — Core Chat API + Authentication (4–6 days)

**Goals**

* Implement anonymous session management and core chat API endpoint following API specifications exactly.
* End-to-end chat pipeline (`POST /api/chat/message`) returns citation-driven answers with proper data models.
* Multi-turn conversation support with session persistence and proper error handling.

**Tasks**

**1.A Authentication & Session Management:**
* Implement `api/v1/routes_auth.py`:
  - `POST /api/auth/session` - Anonymous session creation with JWT tokens
  - Session validation middleware for protected endpoints
  - JWT token generation/validation with expiry handling
* Add session management service in `services/auth/`

**1.B Core Chat Infrastructure:**
* Implement `adapters/vectorstore/supabase_store.py` for upsert/query (pgvector)
* Implement `adapters/llm/openai_llm.py` with streaming support
* Build `services/pipeline/` modules: `retrieval.py`, `grounding.py`, `generation.py`, `postprocess.py`
* Add `services/pipeline/conversation.py`: session-based memory management
* Add `adapters/memory/langchain_memory.py` (in-memory + optional Redis)

**1.C Chat API Implementation:**
* Implement `api/v1/routes_chat.py`:
  - `POST /api/chat/message` with full API spec compliance
  - Request validation (2000 char limit, language codes, required fields)
  - Response with exact schema: messageId, content, citations[], suggestions[], metadata
  - Multi-turn context handling via conversationId
  - Rate limiting (10 requests/minute per session)
  - Comprehensive error handling with proper HTTP status codes

**1.D Knowledge Base Setup:**
* Implement `kb/ingest/sync_to_vectorstore.py`: chunking and indexing CLI
* Seed 20-30 Philippine Labor Code sections with proper metadata
* Citation validation with canonical URLs (Lawphil, DOLE, NLRC)

**1.E Integration Testing & Debugging:** ✅ **COMPLETE** (November 5, 2025)
* End-to-end testing with real OpenAI + Supabase (no mocks) ✅
* Validate complete RAG pipeline with populated KB ✅
* Test multi-turn conversations with actual context ✅
* Verify citation quality and URL accessibility ✅
* Performance benchmarking and optimization ✅
* Manual QA testing with 5+ conversation scenarios ✅
* Bug fixes for issues discovered during integration testing ✅
* **All 8/8 integration tests passing**
* **Known limitations documented in ADR-002**

**Deliverables**

* `POST /api/auth/session`: creates anonymous sessions with JWT tokens
* `POST /api/chat/message`: fully compliant with API spec including all required fields
* Session-based conversation memory with proper persistence
* Comprehensive error responses matching specification format
* Rate limiting with proper headers (X-RateLimit-*)
* **NEW**: Working end-to-end chat with real legal citations
* **NEW**: Integration test suite with real API calls
* **NEW**: Performance baseline documentation

**Exit criteria**

* Integration tests pass: ✅
  - `test_anonymous_session_creation` ✅
  - `test_chat_message_full_schema` ✅
  - `test_multi_turn_conversation` ✅
  - `test_rate_limiting_enforcement` ✅
  - `test_error_response_format` ✅
  - `test_e2e_chat_with_real_kb` (8 scenarios) ✅
  - `test_citation_quality_validation` ✅
  - `test_multi_turn_context_preservation` ✅
* All API responses match exact schema in specifications ✅
* Session tokens work across requests ✅
* Citations include valid, clickable URLs ✅
* Average response time < 15 seconds (real LLM calls) ✅ (12.4s average)
* Manual QA checklist 100% complete ✅
* All critical bugs fixed and verified ✅
* **Known limitations documented in ADR-002** ✅

---

## PHASE-1.0.5 — RAG Pipeline Enhancement (2–3 days) ⬅️ **CRITICAL: DO BEFORE PHASE 1.1**

**Goal:** Implement multi-strategy RAG pipeline with direct rich-context grounding to address Phase 1.E limitations before frontend integration.

**Why Critical:** Current single-strategy semantic search has low confidence scores (0.3-0.4), struggles with broad queries, and has 3-4s Supabase retrieval bottleneck. Must fix before frontend integration to avoid refactoring after frontend is built.

**Reference:** See `docs/adr/002-rag-pipeline-limitations-and-future-architecture.md` for detailed architecture.

---

## PHASE-1.0.5 — RAG Pipeline Enhancement (Complete ✅)

**Status**: Days 1-4 Complete | KB Ingestion Next  
**Duration**: 2-3 days (completed Nov 2025)

**Summary**: Enhanced RAG with multi-strategy retrieval, smart clarification, streaming responses, and dual-table architecture for better accuracy and performance.

### Completed Features ✅

**Multi-Strategy Retrieval**:
- GPT-4o-mini query analysis with concept extraction
- Smart clarification (LLM-based vagueness detection, context-aware)
- Parallel retrieval: keyword (FTS) + semantic (HNSW) + direct article lookup
- Result merging, deduplication, and intelligent ranking

**Database Optimization**:
- HNSW vector indexes (faster than IVFFlat, <2s queries)
- Connection pooling (psycopg2 ThreadedConnectionPool)
- Embedding LRU cache (>30% hit rate target)
- New schema: `labor_law_sections`, `labor_law_chunks`, `labor_law_sources`

**Streaming & Grounding**:
- Single-step rich-context grounding with GPT-4.1
- Server-Sent Events (SSE) streaming API
- Natural citation integration (not robotic)
- Time-to-first-token: <3.5s (measured: 2.5-3.5s)

**KB Infrastructure**:
- Incremental ingestion tracker (SHA-256 hash-based)
- LLM-driven chunking (GPT-4o structure analysis)
- Source management system (10 sources populated)
- ChunkSummarizer: GPT-4.1 with 500 max_tokens for rich summaries

### Performance Metrics

| Metric | Phase 1.E | Phase 1.0.5 Target | Status |
|--------|-----------|-------------------|--------|
| Clear Query Latency | 12.4s | <9s | Pending ingestion |
| Vague Query Latency | 12.4s | <1.5s | Pending ingestion |
| Time-to-First-Token | N/A | <3.5s | ✅ 2.5-3.5s |
| KB Coverage | 5 docs | 65 chunks | 0 (ready) |
| Clarification | Generic | Specific | ✅ Working |
| Cache Hit Rate | 0% | >30% | ✅ Implemented |

### Next Steps (Current Roadmap)

See [PHASE_1.0.5_IMPLEMENTATION_CHECKLIST.md](docs/PHASE_1.0.5_IMPLEMENTATION_CHECKLIST.md) for summary.  
See [CURRENT_IMPLEMENTATION_ROADMAP.md](docs/CURRENT_IMPLEMENTATION_ROADMAP.md) for detailed steps.

1. **Test auto-chunker** (1h) - Verify paragraph splitting works
2. **Dry-run ingestion** (30m) - Test 65 chunks without DB write
3. **Full PD-No-442 ingestion** (1-2h) - 65 sections + 40-60 sub-chunks (~$2 cost)
4. **Update retrieval** (2-3h) 🔴 CRITICAL - Add `query_with_chunks()` for dual-table search
5. **Accuracy testing** (2-3h) - 20 queries, 90% accuracy target
6. **Performance testing** (1h) - Verify latency targets
7. **Integration tests** (1-2h) - Update and verify all passing
8. **Frontend connection** (2-3h) - End-to-end user flows

**Total Time**: 12-16 hours remaining (1.5-2 days)

### Key Technical Details

**Dual-Table Architecture**:
- `labor_law_sections`: Full articles with summaries and embeddings
- `labor_law_chunks`: Auto-split sub-chunks for articles >1000 words
- Retrieval queries both tables, merges results, deduplicates, re-ranks

**Smart Clarification**:
- LLM-based vagueness detection (not deterministic rules)
- Context-aware (uses conversation history to avoid false triggers)
- Generates 3-4 specific follow-up questions (not generic "please clarify")
- Early pipeline exit saves 87% cost and 6.5s latency for vague queries

**Streaming Architecture**:
- Server-Sent Events (SSE) format: `data: {json}\n\n`
- Token-by-token streaming from GPT-4.1
- Graceful client disconnection handling
- Fallback to non-streaming for older clients

---

## PHASE-1.1 — Conversation Management API (3–4 days)

**Goal:** Complete conversation lifecycle management matching API specifications.

**Prerequisites:** ✅ Phase 1.0.5 (RAG Enhancement) MUST be complete

**Tasks**

**Conversation CRUD Operations:**
* Implement `api/v1/routes_conversations.py`:
  - `POST /api/conversations` - Create new conversation with title, language, metadata
  - `GET /api/conversations` - List conversations with pagination, filtering, search
  - `GET /api/conversations/:id` - Get conversation with full message history
  - `PATCH /api/conversations/:id` - Update title, archive status
  - `DELETE /api/conversations/:id` - Delete conversation and all messages
  - `GET /api/conversations/:id/export` - Export conversation (TXT, JSON formats)

**Conversation Services:**
* Implement `services/conversations/` module:
  - Conversation creation/retrieval logic
  - Message history management 
  - Pagination and search functionality
  - Archive/unarchive operations
  - Export utilities (TXT, JSON formats)

**Database Models:**
* Create conversation and message tables with proper relationships
* Add indexes for performance (user sessions, timestamps, language)
* Implement soft delete for conversations

**Search Functionality:**
* Implement `api/v1/routes_search.py`:
  - `GET /api/search/conversations` - Full-text search across conversations
  - Search highlighting and relevance scoring
  - Language-aware search filtering

**Deliverables**

* Complete conversation management API matching specifications
* Pagination with proper metadata (total, hasMore, etc.)
* Search functionality with highlighted results
* Export functionality for conversation history
* Proper error handling for all edge cases

**Exit criteria**

* All conversation endpoints return exact schema from API spec
* Tests pass: CRUD operations, pagination, search, export
* Performance meets requirements (<500ms for list operations)
* Soft delete works properly (deleted conversations not visible)

---

## PHASE-1.2 — Feedback & Rating System (2–3 days)

**Goal:** Complete feedback collection system for message quality improvement.

**Tasks**

**Feedback API Implementation:**
* Implement `api/v1/routes_feedback.py`:
  - `POST /api/feedback/rating` - Submit 1-5 star ratings for messages
  - `POST /api/feedback/flag` - Flag incorrect/problematic responses
  - `GET /api/feedback/stats` - Get aggregated feedback statistics

**Feedback Services:**
* Implement `services/feedback/` module:
  - Rating validation and storage
  - Flag reason categorization and storage
  - Statistics aggregation and analytics
  - Duplicate feedback prevention

**Database Models:**
* Create feedback tables with proper relationships to messages/conversations
* Support both ratings and flag reasons
* Track feedback metadata (timestamps, user agents, etc.)

**Analytics Integration:**
* Implement feedback statistics calculation
* Rating distribution analytics
* Common flag reason tracking
* Message quality scoring based on feedback

**Deliverables**

* Complete feedback API matching specifications
* Rating system with 1-5 star validation
* Flag system with reason tracking
* Statistics API with aggregated data
* Duplicate feedback handling

**Exit criteria**

* All feedback endpoints match API specifications exactly
* Tests pass: rating submission, flag submission, statistics
* Analytics provide meaningful insights
* System prevents feedback spam/duplicates

---

## PHASE-2 — Citations & Suggested Actions Enhancement (3–4 days)

**Goals**

* Implement comprehensive citation validation and context-aware suggested actions matching API specifications.
* Ensure all legal citations are authoritative, clickable, and properly formatted.

**Tasks**

**Citation System:**
* Implement strict `Citation` model validation with all required fields:
  - id, text, source, article, url, confidence (all mandatory per API spec)
  - Canonical URLs to Lawphil, DOLE, NLRC official sources
  - Confidence scoring based on retrieval accuracy
* Enrich knowledge base metadata with authoritative source URLs
* Add citation post-processing for link validation and formatting

**Suggested Actions Framework:**
* Implement `SuggestedAction` model with strict type validation:
  - Support all action types: contact, form, link, query, info
  - Context-aware action generation based on legal topic classification
  - Action data validation for each type (contact info, form instructions, etc.)
* Create authoritative content mapping for DOLE/SEnA resources:
  - DOLE contact information and hotlines
  - SEnA form procedures and download links
  - PAO/IBP referral information
  - Legal aid resource directory

**Context-Aware Action Generation:**
* Implement topic classification for action suggestions:
  - Dismissal/termination → SEnA filing + legal aid contact
  - Wage/overtime issues → DOLE complaint process + forms
  - General inquiries → Information resources + follow-up queries
* Ensure maximum 3-4 actions per response to avoid UI clutter
* Add action personalization based on user's language preference

**Deliverables**

* All citations include required fields with valid, clickable URLs
* Context-aware suggested actions for core labor law scenarios
* Comprehensive legal resource integration
* Action validation ensuring UI functionality
* Multilingual action labels and descriptions

**Exit criteria**

* Tests pass:
  - `test_citation_completeness` (all required fields present)
  - `test_citation_urls_valid` (all links accessible)
  - `test_actions_by_scenario` (correct actions for each legal topic)
  - `test_action_data_validation` (all action data properly formatted)
* All citations link to authoritative Philippine legal sources
* Suggested actions trigger proper UI behaviors (modals, links, queries)
* Action generation is deterministic and context-appropriate

---

## PHASE-3 — Multilingual Support & Translation (3–4 days)

**Goals**

* Robust language handling with cost-controlled translation.

**Tasks**

* `nlp/lang_detect/fasttext_detector.py` + resource download script.
* `adapters.translate.gtranslate` with toggle `ENABLE_TRANSLATION`.
* `services.pipeline.nlp_ingress`: detect → (conditional) translate in → normalize; back-translate out if needed.
* Output language selection: `locale` in request or auto.

**Deliverables**

* Same prompt, but responds in user’s language.
* Toggle to disable translation for A/B tests.

**Exit criteria**

* Unit tests: mixed Taglish, pure Cebuano, and English inputs produce coherent outputs and correct language tag.

---

## PHASE-4 — Intent Classification & Retrieval Enhancement (2–3 days)

**Goals**

* Improve retrieval precision and response quality through intelligent intent classification.
* Implement confidence-based filtering to enhance legal topic matching.

**Tasks**

**Intent Classification System:**
* Implement `nlp/intent/distilbert_classifier.py` (HuggingFace or ONNX runtime)
* Create `nlp/intent/taxonomy.py` with Philippine labor law topic categories:
  - Dismissal/Termination, Wages/Overtime, Benefits, Workplace Rights, etc.
  - Map topics to relevant KB sections and citation priorities
* Add confidence gating with `INTENT_CONF_THRESHOLD` configuration
* Create fallback mechanisms for low-confidence classifications

**Enhanced Retrieval Pipeline:**
* Update `services/pipeline/retrieval.py` with intent-aware filtering:
  - Use intent classification to narrow vector search scope
  - Apply metadata tags and topic filters when confidence ≥ threshold
  - Implement hybrid search (semantic + intent-based)
* Add retrieval result re-ranking based on intent alignment
* Create retrieval quality metrics and logging

**Performance Optimization:**
* Implement retrieval result caching for common intents
* Add query expansion based on legal topic relationships
* Create retrieval pipeline monitoring and analytics

**Deliverables**

* Intent classification with labor law topic taxonomy
* Enhanced retrieval precision through intent filtering
* Comprehensive logging of retrieval performance metrics
* Fallback handling for ambiguous or out-of-scope queries
* Performance improvements in response relevance

**Exit criteria**

* Tests pass:
  - `test_intent_classification_accuracy` (>85% on labeled dataset)
  - `test_retrieval_precision_improvement` (measurable improvement vs baseline)
  - `test_fallback_handling` (proper fallback when intent confidence low)
* Retrieval precision increases on Philippine labor law test set
* Intent confidence scores correlate with retrieval quality
* System maintains performance when intent classification fails

---

## PHASE-5 — Safety, Content Moderation & Legal Compliance (2–3 days)

**Goals**

* Implement comprehensive safety guardrails and content moderation to prevent unauthorized practice of law.
* Ensure legal compliance with Philippine bar regulations and ethical guidelines.

**Tasks**

**Content Moderation System:**
* Implement `services/moderation.py` with comprehensive policy enforcement:
  - Detect requests for personalized legal advice vs general information
  - Flag attempts to create attorney-client relationships
  - Identify and reject inappropriate content (harassment, threats, etc.)
* Integrate `adapters/moderation/openai_moderation.py` for content filtering
* Create custom moderation rules specific to Philippine legal context

**Legal Compliance Framework:**
* Implement `nlp/heuristics.py` for domain-specific guardrails:
  - UPL (Unauthorized Practice of Law) detection and prevention
  - Scope limiting to general legal information only
  - Automatic disclaimer injection for all legal responses
* Create refusal templates for:
  - Non-labor law topics (criminal, civil, family law, etc.)
  - Requests for specific legal advice or case strategy
  - Attorney-client privilege violations

**Content Policy Enforcement:**
* Add automatic disclaimer text to all legal responses
* Implement referral suggestions when declining to provide advice
* Create escalation procedures for flagged content
* Log all moderation decisions for audit purposes

**Response Filtering:**
* Post-process all LLM responses for compliance:
  - Remove any language suggesting attorney-client relationship
  - Add appropriate disclaimers and limitations
  - Ensure responses stay within general information bounds
  - Flag potentially problematic responses for review

**Deliverables**

* Comprehensive content moderation matching legal compliance requirements
* Automatic UPL prevention with appropriate refusals
* Disclaimer injection for all legal responses
* Audit logging for all moderation decisions
* Legal compliance documentation and procedures

**Exit criteria**

* Tests pass:
  - `test_upl_prevention` (rejects personalized legal advice requests)
  - `test_scope_limiting` (stays within labor law domain)
  - `test_disclaimer_injection` (all responses include disclaimers)
  - `test_content_filtering` (inappropriate content blocked)
* Legal review confirms compliance with Philippine bar regulations
* Safety test suite passes all scenarios
* Moderation decisions logged and auditable

---

## PHASE-6 — Search API & Legal Aid Referrals (2–3 days)

**Goals**

* Implement conversation search functionality and legal aid referral system as specified in API documentation.
* Provide actionable next steps through nearby legal service providers.

**Tasks**

**Search API Implementation:**
* Implement `api/v1/routes_search.py`:
  - `GET /api/search/conversations` - Full-text search across user conversations
  - Search query processing with highlighting and relevance scoring
  - Language-aware search filtering (en, fil, ceb)
  - Pagination and result limiting as per API specifications
* Add search indexing for conversation content:
  - Full-text indexing of messages and titles
  - Search result ranking and relevance scoring
  - Search performance optimization

**Legal Aid Referral System:**
* Implement `adapters/maps/google_places.py`:
  - Google Places API integration for legal service provider search
  - Location-based search with radius filtering
  - Result deduplication and quality filtering
* Implement `services/maps_referral.py`:
  - Legal aid provider categorization (PAO, IBP, private lawyers, etc.)
  - Contact information validation and formatting
  - Distance calculation and sorting
  - Result capping and relevance filtering

**Integration with Chat System:**
* Add location sharing support to chat API:
  - Optional lat/lng parameters in chat requests
  - Privacy-conscious location handling (no storage)
  - Location-based suggested actions generation
* Create referral suggestions in chat responses:
  - Context-aware referral recommendations
  - Proper contact information formatting
  - Integration with suggested actions framework

**Privacy and Security:**
* Implement location data handling policies:
  - No persistent storage of location data
  - Opt-in location sharing mechanism
  - Clear privacy disclosures for location usage

**Deliverables**

* Full-text search API matching specifications
* Legal aid referral system with location services
* Privacy-compliant location handling
* Integration with chat system for contextual referrals
* Search result highlighting and relevance scoring

**Exit criteria**

* Tests pass:
  - `test_conversation_search` (search returns relevant results with highlighting)
  - `test_search_pagination` (proper pagination and result limits)
  - `test_legal_aid_referrals` (accurate nearby provider results)
  - `test_location_privacy` (no location data stored)
* Search performance meets requirements (<1 second response time)
* Legal aid referrals are accurate and up-to-date
* Location data handling complies with privacy requirements

---

## PHASE-7 — Performance Optimization & Rate Limiting (2–3 days)

**Goals**

* Implement comprehensive performance monitoring, rate limiting, and observability features.
* Ensure system meets all performance requirements specified in API documentation.

**Tasks**

**Rate Limiting System:**
* Implement `core/rate_limit.py` with token-bucket algorithm:
  - Per-endpoint rate limiting as specified (10/min for chat, 100/min for conversations)
  - Session-based and IP-based rate limiting
  - Proper rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
  - Rate limit exceeded error responses matching API specification
* Add rate limiting middleware to all API endpoints
* Create rate limit bypass for admin/testing endpoints

**Performance Monitoring:**
* Implement comprehensive request/response logging:
  - Request IDs for tracing (`middleware/request_id.py`)
  - Structured JSON logging with latency, status codes, user agents
  - Token usage tracking for LLM costs
  - Cache hit/miss ratios and performance metrics
* Add performance metrics collection:
  - Response time percentiles (p50, p95, p99)
  - Error rates by endpoint and error type
  - Chat response quality metrics (citation count, confidence scores)

**Caching and Optimization:**
* Implement caching layers:
  - LRU cache for frequent embeddings queries
  - Response caching for identical questions (configurable TTL)
  - Knowledge base chunk caching for retrieval
* Database query optimization:
  - Add proper indexes for conversation and message queries
  - Implement database connection pooling
  - Optimize pagination queries

**Health and Monitoring Endpoints:**
* Enhance `api/v1/routes_health.py`:
  - Deep health checks for all external dependencies (Supabase, OpenAI, Google APIs)
  - System resource monitoring (memory, CPU usage)
  - Cache status and performance metrics
  - Database connectivity and query performance

**Deliverables**

* Comprehensive rate limiting matching API specifications
* Performance monitoring and observability
* Caching systems for improved response times
* Enhanced health monitoring for all system components
* Structured logging for debugging and analytics

**Exit criteria**

* Tests pass:
  - `test_rate_limiting_enforcement` (all endpoints respect limits)
  - `test_performance_monitoring` (metrics collected accurately)
  - `test_caching_functionality` (cache improves response times)
  - `test_health_checks` (all dependencies monitored)
* System meets performance targets (<5s chat, <500ms conversations)
* Rate limiting prevents abuse while allowing normal usage
* Monitoring provides actionable insights for optimization

---

## PHASE-8 — Infrastructure as Code & CI/CD (3–4 days)

**Goals**

* Implement production-ready infrastructure automation and continuous deployment pipeline.
* Ensure secure, scalable, and maintainable cloud infrastructure.

**Tasks**

**Infrastructure Automation:**
* Create Terraform modules in `infra/terraform/modules/`:
  - `cloud_run_service/` - API service deployment configuration
  - `artifact_registry/` - Container image registry setup
  - `secret_manager/` - Secure credential management
  - `workload_identity/` - Google Cloud service authentication
  - `supabase_integration/` - Database and vector store configuration
* Implement environment-specific configurations:
  - `infra/terraform/envs/dev/` - Development environment
  - `infra/terraform/envs/staging/` - Staging environment for testing
  - `infra/terraform/envs/prod/` - Production environment
  - Environment-specific variable files and scaling configurations

**CI/CD Pipeline:**
* Implement GitHub Actions workflows:
  - `.github/workflows/ci.yml` - Automated testing and code quality checks
  - `.github/workflows/build.yml` - Container image building and pushing
  - `.github/workflows/deploy-dev.yml` - Automated development deployments
  - `.github/workflows/deploy-prod.yml` - Production deployment with approvals
* Add deployment safety measures:
  - Automated rollback on health check failures
  - Blue-green deployment strategy for zero-downtime updates
  - Environment promotion gates and manual approvals

**Security and Configuration:**
* Implement secure secret management:
  - All API keys and credentials in Google Secret Manager
  - Runtime secret injection (no plaintext in CI/CD)
  - Rotation policies for sensitive credentials
* Add infrastructure security:
  - Network security policies and firewall rules
  - IAM roles and permissions with principle of least privilege
  - Container security scanning and vulnerability management

**Monitoring and Alerts:**
* Set up infrastructure monitoring:
  - Cloud Run service health monitoring
  - Database performance and connection monitoring
  - API response time and error rate alerting
  - Cost monitoring and budget alerts

**Deliverables**

* Complete infrastructure as code with Terraform modules
* Automated CI/CD pipeline with proper security gates
* Environment-specific configurations (dev, staging, prod)
* Secure credential management and rotation policies
* Infrastructure monitoring and alerting setup

**Exit criteria**

* Tests pass:
  - `test_infrastructure_provisioning` (terraform apply succeeds)
  - `test_deployment_pipeline` (full CI/CD workflow works)
  - `test_security_configuration` (proper IAM and secrets)
  - `test_monitoring_setup` (alerts and dashboards functional)
* Fresh environment bootstrap yields healthy API endpoints
* Deployment pipeline supports rollbacks and zero-downtime updates
* Security audit passes for infrastructure and CI/CD configuration

---

## PHASE-9 — Quality Assurance & Testing (3–4 days)

**Goals**

* Comprehensive system testing and quality validation to ensure production readiness.
* Establish accuracy baselines and performance benchmarks.

**Tasks**

**Test Data and Evaluation Framework:**
* Create comprehensive test datasets:
  - Gold standard Q&A set with expert legal review (50-100 questions)
  - Philippine labor law scenarios covering all major topics
  - Edge cases and boundary conditions (out-of-scope, ambiguous queries)
  - Multilingual test cases (English, Filipino, Cebuano, code-switching)
* Implement evaluation metrics:
  - Retrieval@k precision and recall for knowledge base queries
  - Citation correctness and groundedness validation
  - Response quality scoring (legal accuracy, completeness, helpfulness)
  - Multilingual response quality assessment

**Automated Testing Suite:**
* Comprehensive API testing:
  - All endpoints tested with valid and invalid inputs
  - Authentication and authorization testing
  - Rate limiting and error handling validation
  - Performance and load testing with realistic traffic patterns
* Integration testing:
  - End-to-end conversation flows
  - Multi-turn conversation memory validation
  - Cross-language functionality testing
  - External API integration testing (OpenAI, Google APIs)

**Performance and Security Validation:**
* Load testing with realistic usage patterns:
  - Concurrent user simulation (target: 100+ simultaneous users)
  - API response time validation (<5s chat, <500ms other endpoints)
  - System stability under sustained load
* Security testing:
  - Input validation and sanitization testing
  - Authentication bypass attempts
  - Rate limiting effectiveness
  - Data privacy compliance validation

**Quality Metrics and Monitoring:**
* Implement quality tracking:
  - Automated quality regression testing in CI/CD
  - Performance benchmarking and trend analysis
  - User feedback correlation with quality metrics
  - A/B testing framework for improvements

**Deliverables**

* Comprehensive test suite covering all functionality
* Quality evaluation framework with established baselines
* Performance benchmarks and monitoring dashboards
* Security validation and penetration testing results
* Regression testing integrated into CI/CD pipeline

**Exit criteria**

* Tests pass:
  - `test_quality_benchmarks` (≥80% groundedness, ≥90% citation accuracy)
  - `test_performance_targets` (all response time requirements met)
  - `test_security_validation` (no critical vulnerabilities found)
  - `test_multilingual_accuracy` (consistent quality across languages)
* Load testing supports target concurrent users
* Quality metrics meet production readiness standards
* Security audit passes with no high-severity issues

---

## PHASE-10 — Production Hardening & Beta Preparation (2–3 days)

**Goals**

* Make it safe to pilot with users.

**Tasks**

* Rate limits tuned; error messages localized.
* Backoff/retry for transient errors; circuit breakers around external APIs.
* Backup/restore docs for KB; provenance manifests finalized.

**Deliverables**

* “Beta Readiness” checklist passed.
* Privacy note & ToS text (for frontend) aligned with backend behavior.

**Exit criteria**

* Go/No-Go: all critical bugs closed; SLOs green for 48h in dev.

---

## PHASE-11 — Cost Optimization & GA Polish (2–3 days)

**Goals**

* Optimize operational costs and add production-grade API management features.
* Prepare system for general availability with comprehensive monitoring.

**Tasks**

**Cost Optimization:**
* Implement cost reduction measures:
  - Batch embedding requests to reduce OpenAI API costs
  - Response truncation and citation capping to control token usage
  - Intelligent caching for frequent queries (LRU cache with TTL)
  - Database query optimization and connection pooling tuning
* Add cost monitoring and alerting:
  - API usage tracking and cost forecasting
  - Budget alerts and automatic cost controls
  - Usage analytics and optimization recommendations

**Production API Features:**
* Add operational endpoints:
  - `GET /api/version` - API version and build information
  - `GET /api/config` - Public configuration flags for frontend
  - `GET /api/metrics` - System health and performance metrics (admin only)
  - Enhanced `/api/healthz` with detailed dependency status
* Implement API versioning strategy:
  - Version headers and backward compatibility
  - Deprecation notices and migration paths
  - API documentation versioning

**Advanced Features:**
* Optional streaming responses for chat API:
  - Server-Sent Events (SSE) support for real-time typing indicators
  - Chunked response delivery for improved perceived performance
  - WebSocket support preparation (future enhancement)
* Enhanced error handling:
  - Detailed error codes for different failure modes
  - User-friendly error messages with suggested actions
  - Admin notification system for critical errors

**Final Polish:**
* Complete API documentation:
  - OpenAPI 3.0 specification with all endpoints
  - Interactive API documentation (Swagger/Redoc)
  - SDK examples and integration guides
  - Postman collection for testing

**Deliverables**

* Cost-optimized system with usage monitoring
* Complete API versioning and documentation
* Production-grade operational endpoints
* Optional streaming capabilities for enhanced UX
* Comprehensive system monitoring and alerting

**Exit criteria**

* Tests pass:
  - `test_cost_optimization` (reduced token usage without quality loss)
  - `test_api_versioning` (proper version handling and compatibility)
  - `test_operational_endpoints` (health, metrics, config APIs work)
  - `test_streaming_capabilities` (SSE/WebSocket if implemented)
* Cost per 100 conversations meets target budget
* API documentation is complete and accurate
* System ready for general availability launch

---

## Release Gates & Milestones

### MVP Release (Phases 0-1.E + Selected Later Phases)
**Target:** Core functionality with legal compliance and working chatbot

**Foundation (Required)**:
* ✅ **Phase 0 - Scaffold & Contracts**
* ✅ **Phase 1.A - Authentication & Session Management**
* ✅ **Phase 1.B - Core Chat Infrastructure**
* ✅ **Phase 1.C - Chat API Implementation**
* ✅ **Phase 1.D - Knowledge Base Setup**
* 🚧 **Phase 1.E - Integration Testing & Debugging** ⬅️ **CURRENT PHASE**

**Enhanced Features (Build on Foundation)**:
* ⏸️ **Phase 1.1 - Conversation Management** (requires 1.E complete)
* ⏸️ **Phase 1.2 - Feedback & Rating System** (requires 1.E complete)
* ⏸️ **Phase 2 - Citations & Suggested Actions Enhancement**
* ⏸️ **Phase 3 - Multilingual Support** (optional for MVP)
* ⏸️ **Phase 5 - Safety & Legal Compliance** (critical for production)
* ⏸️ **Phase 7 - Performance Optimization & Rate Limiting**
* ⏸️ **Phase 8 - Infrastructure as Code & CI/CD**

### Critical Path to MVP:
```
Phase 0 → 1.A → 1.B → 1.C → 1.D → 1.E (INTEGRATION) → 1.1 → 1.2 → 5 → 8
   ✅      ✅     ✅     ✅     ✅     🚧                 ⏸️   ⏸️   ⏸️  ⏸️

Legend:
✅ Complete
🚧 In Progress / Next Up
⏸️ Pending (blocked by 1.E)
```

### Why Phase 1.E is Critical:

**Without Phase 1.E**:
- ❌ No confidence that chat actually works end-to-end
- ❌ Unknown if citations are correct with real data
- ❌ Multi-turn conversations untested in practice
- ❌ Performance issues discovered late (during Phase 1.1+)
- ❌ Integration bugs mixed with Phase 1.1 feature bugs
- ❌ Higher risk of production failures

**With Phase 1.E**:
- ✅ Proven working chatbot before adding features
- ✅ Citation quality validated with real legal content
- ✅ Multi-turn conversations verified
- ✅ Performance baseline established
- ✅ Clean separation: integration bugs vs feature bugs
- ✅ Confidence to proceed to Phase 1.1

**Decision Point**: Phase 1.E completion is a **MANDATORY GATE** before Phase 1.1.

---

### Beta Release (MVP + Enhancements)
**Target:** User-facing pilot with full conversation management

* All MVP phases complete
* Phase 1.1 (Conversation Management) complete
* Phase 1.2 (Feedback System) complete
* Phase 3 (Multilingual) complete
* Phase 6 (Search & Legal Aid) complete
* Phase 9 (QA Testing) complete
* Phase 10 (Beta Hardening) complete

### General Availability (Production Ready)
**Target:** Public launch with full feature set

* All Beta phases complete
* Phase 4 (Intent Classification) complete
* Phase 11 (Cost Optimization) complete
* Security audit passed
* Performance SLOs met for 7 days
* Legal compliance review approved

---
* ✅ **Performance & Monitoring** (Phase 7)
* ✅ **Infrastructure & CI/CD** (Phase 8)

### Beta Release (MVP + Phases 4 + 6 + 9-10)
**Target:** Production-ready system with full feature set
* ✅ **All MVP features** (stable and tested)
* ✅ **Enhanced Retrieval & Intent** (Phase 4)
* ✅ **Search & Legal Aid** (Phase 6)
* ✅ **Quality Assurance** (Phase 9)
* ✅ **Production Hardening** (Phase 10)

### GA Release (Beta + Phase 11)
**Target:** Optimized system ready for scale
* ✅ **All Beta features** (performance validated)
* ✅ **Cost Optimization** (Phase 11)
* ✅ **Complete API Documentation**
* ✅ **Operational Excellence**

---

## API Implementation Checklist

### Core Endpoints (MVP Required)
- [ ] `POST /api/auth/session` - Anonymous session creation
- [ ] `POST /api/chat/message` - Main chat functionality with citations
- [ ] `POST /api/conversations` - Create conversation
- [ ] `GET /api/conversations` - List conversations with pagination
- [ ] `GET /api/conversations/:id` - Get conversation with messages
- [ ] `PATCH /api/conversations/:id` - Update conversation
- [ ] `DELETE /api/conversations/:id` - Delete conversation
- [ ] `POST /api/feedback/rating` - Submit message ratings
- [ ] `POST /api/feedback/flag` - Flag incorrect responses

### Enhanced Endpoints (Beta Required)
- [ ] `GET /api/conversations/:id/export` - Export conversation data
- [ ] `GET /api/search/conversations` - Search across conversations
- [ ] `GET /api/feedback/stats` - Feedback analytics

### Operational Endpoints (GA Required)
- [ ] `GET /api/healthz` - Health check with dependencies
- [ ] `GET /api/version` - API version information
- [ ] `GET /api/config` - Public configuration flags

### Cross-Cutting Requirements (All Phases)
- [ ] **Rate Limiting**: All endpoints respect specified limits
- [ ] **Multilingual**: Support for en, fil, ceb languages
- [ ] **Error Handling**: Consistent error format across all endpoints
- [ ] **Authentication**: JWT-based session management
- [ ] **Performance**: Meet response time requirements
- [ ] **Security**: Input validation, CORS, security headers
- [ ] **Documentation**: OpenAPI spec for all endpoints
- [ ] **Testing**: Comprehensive test coverage

---

## Workstreams & Ownership

### Backend Core Team (Phases 1-3, 5)
* Authentication and session management
* Chat API and conversation pipeline
* Citations and suggested actions system
* Multilingual support implementation
* Safety and content moderation

### Infrastructure Team (Phases 7-8, 11)
* Cloud infrastructure and deployment
* CI/CD pipeline and automation
* Performance optimization and monitoring
* Cost management and optimization

### NLP/AI Team (Phases 2, 4)
* Intent classification and retrieval enhancement
* Language detection and translation
* Knowledge base management and RAG pipeline
* Response quality and grounding validation

### QA/Testing Team (Phases 9-10)
* Comprehensive testing framework
* Performance and load testing
* Security validation and compliance
* Beta preparation and quality assurance

### Product/Documentation Team (All Phases)
* API specification maintenance
* Legal compliance and privacy policies
* User documentation and integration guides
* Release planning and communication

---

## Global Acceptance Criteria

### Technical Requirements
* ✅ All API endpoints match specifications exactly
* ✅ Comprehensive OpenAPI documentation with examples
* ✅ >95% test coverage across all modules
* ✅ Performance targets met (<5s chat, <500ms other endpoints)
* ✅ Security validation passes (input sanitization, auth, CORS)

### Legal and Compliance
* ✅ Every legal response includes proper citations or refusal
* ✅ UPL (Unauthorized Practice of Law) prevention implemented
* ✅ Privacy compliance (no personal data persistence)
* ✅ Content moderation and safety guardrails active

### Operational Excellence
* ✅ Swappable adapters (proven by substituting test implementations)
* ✅ Comprehensive monitoring and alerting
* ✅ Disaster recovery and backup procedures
* ✅ Cost optimization and budget controls
* ✅ Multi-environment deployment capability (dev, staging, prod)
