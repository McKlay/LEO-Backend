# LEO Backend - Philippine Labor Law Chatbot

A robust, production-ready backend API for **LEO**, a multi-turn, citation-driven chatbot focused on Philippine labor law. Built with Python 3.11+ and FastAPI, delivering a scalable, modular RAG (retrieval-augmented generation) pipeline with multilingual support.

## Features

- **Multi-turn Chat**: Conversation memory and context-aware responses
- **Citation-driven Answers**: All legal responses backed by authoritative sources
- **Multilingual Support**: English, Filipino (Tagalog), and Cebuano
- **RAG Pipeline**: Retrieval-augmented generation with Supabase pgvector
- **Safety & Compliance**: Content moderation and legal compliance guardrails
- **Production-ready**: Cloud Run deployment, health checks, and monitoring

## Tech Stack

- **FastAPI** - Modern async web framework
- **Supabase + pgvector** - Vector database for semantic search
- **OpenAI GPT-4.1** - Language model for grounded generation
- **LangChain** - Conversation memory management
- **Google Cloud** - Optional translation and maps services
- **Docker** - Containerized deployment

## Architecture

```
leo-backend/
├── api/          # API routes and endpoints
├── app/          # Application factory and middleware
├── core/         # Configuration, logging, exceptions
├── services/     # Business logic and use cases
├── adapters/     # External service integrations
├── nlp/          # NLP utilities (language detection, intent)
├── kb/           # Knowledge base management
└── tests/        # Unit and integration tests
```

## Quick Start

### Prerequisites

- Python 3.11+
- Supabase account
- OpenAI API key

### Installation

1. **Clone the repository**
```powershell
git clone <repository-url>
cd LEO-Backend
```

2. **Create virtual environment**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

3. **Install dependencies**
```powershell
pip install -e ".[dev]"
```

4. **Configure environment**
```powershell
cp .env.example .env
# Edit .env with your API keys and configuration
```

5. **Run the application**
```powershell
python -m uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## Testing

Run the test suite:

```powershell
# All tests
pytest

# Unit tests only
pytest tests/unit

# Integration tests only
pytest tests/integration

# With coverage
pytest --cov=. --cov-report=html
```

## Docker Deployment

Build and run with Docker:

```powershell
# Build image
docker build -t leo-backend .

# Run container
docker run -p 8000:8000 --env-file .env leo-backend
```

## Development

### Code Quality

```powershell
# Format code
black .

# Sort imports
isort .

# Type checking
mypy .

# Linting
flake8 .
```

### Project Status

Currently in **Phase 0** - Repository Scaffold & Contracts

See `ImplementationSequence.md` for the complete development roadmap.

## Environment Variables

Key environment variables (see `.env.example` for complete list):

```env
# OpenAI
OPENAI_API_KEY=your-key-here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# Security
JWT_SECRET_KEY=your-secret-key
```

## API Endpoints

### Health & Status
- `GET /api/v1/healthz` - Health check
- `GET /api/v1/readyz` - Readiness probe

### Coming Soon
- `POST /api/auth/session` - Anonymous session creation
- `POST /api/chat/message` - Send chat message
- `GET /api/conversations` - List conversations
- And more...

## Documentation

- [API Specifications](docs/BACKEND_API_SPECIFICATIONS.md)
- [Implementation Roadmap](ImplementationSequence.md)
- [Architecture Guidelines](.github/copilot-instructions.md)

## Contributing

This project follows strict development principles:

1. **Modular Architecture** - Clean separation of concerns
2. **Type Safety** - Comprehensive type hints
3. **Test Coverage** - >80% coverage requirement
4. **Code Quality** - Black formatting, strict linting
5. **Documentation** - Google-style docstrings

## License

MIT License - See LICENSE file for details

## Links

- Documentation: See `docs/` directory
- Issues: GitHub Issues
- API Reference: See inline API documentation

---

**Phase 0 Complete** ✅
- Folder structure initialized
- Core configuration implemented
- Health endpoints operational
- Adapter interfaces defined
- Testing infrastructure ready
