# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based tender document extraction service that processes PDF documents to extract structured information from tender documents. The application supports both single document processing and batch processing with optional document merging capabilities.

## Core Architecture

### Main Components

- **FastAPI Application** (`main.py`): The entire application is contained in a single file with three main endpoints
- **Document Processing Pipeline**: Uses external `tender_extraction.TenderExtractionPipeline` module for PDF processing
- **Job Management**: In-memory job tracking system (noted for Redis replacement in production)
- **Document Classification**: Automatic document type detection based on filename patterns

### Key Data Models

- `BatchExtractionRequest`: Configuration for batch processing operations
- `DocumentExtractionResult`: Individual document extraction results with tender-specific fields
- `MergedTenderResult`: Consolidated results from multiple related documents

### Processing Workflow

1. **Single Document**: Upload → PDF validation → Background processing → Result storage
2. **Batch Processing**: Multiple uploads → Individual processing → Optional merging → Consolidated results
3. **Document Relationships**: Automatic detection of cross-references and parent-child relationships between documents

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Copy environment configuration
cp .env.example .env
```

### Running the Application
```bash
# Run with development runner (recommended)
python run_dev.py

# Or run directly with uvicorn
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Or run main.py directly
python main.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_extraction.py

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/

# Run all quality checks
black app/ tests/ && isort app/ tests/ && flake8 app/ tests/ && mypy app/
```

## API Endpoints

- `GET /health`: Basic health check
- `GET /health/detailed`: Detailed health check with dependency status
- `POST /api/v1/extract-single`: Process single PDF document
- `POST /api/v1/extract-batch`: Process multiple PDF documents with merging options
- `GET /api/v1/status/{job_id}`: Check processing status
- `GET /api/v1/export/{job_id}`: Export results in JSONL format

## Key Features

### Document Classification
Automatic classification based on filename patterns:
- `bestek`/`specifications` → technical_specifications
- `aankondiging`/`announcement` → tender_announcement  
- `bijlage`/`annex` → annex
- `criteria`/`gunning` → evaluation_criteria
- `contract` → contract_terms

### Supported Languages
- Dutch (nl) - default
- English (en)
- German (de) 
- French (fr)

### Document Merging Intelligence
- Consolidates project information from multiple sources
- Handles value conflicts (takes highest estimated value, earliest deadline)
- Deduplicates and merges evaluation criteria
- Calculates completeness and confidence scores

## Dependencies

The application requires:
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `python-multipart`: File upload support
- External `tender_extraction` module (not in repository)

## Project Structure

```
tenderextract/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory
│   ├── config.py                 # Configuration management
│   ├── dependencies.py           # Dependency injection
│   ├── core/                     # Core components
│   │   ├── exceptions.py         # Custom exceptions
│   │   └── logging.py           # Logging configuration
│   ├── models/                   # Data models
│   │   ├── extraction.py         # Extraction result models
│   │   └── jobs.py              # Job management models
│   ├── routers/                  # API endpoints
│   │   ├── extraction.py         # Document extraction endpoints
│   │   └── health.py            # Health check endpoints
│   ├── schemas/                  # Request/response schemas
│   │   └── requests.py          # API request models
│   └── services/                 # Business logic
│       ├── extraction_service.py # Document processing service
│       └── job_storage.py       # Job storage abstraction
├── tests/                        # Test suite
│   ├── test_extraction.py
│   └── test_health.py
├── main.py                       # Application entry point
├── run_dev.py                    # Development server runner
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── pytest.ini                   # Test configuration
├── .env.example                  # Environment template
└── temp/                        # Temporary file storage
```

## Development Best Practices

### Python Development Standards

#### Project Structure & Dependencies
- **Use virtual environments**: `python -m venv venv` or `conda create`
- **Pin dependencies**: Create `requirements.txt` with specific versions
- **Separate dev/prod dependencies**: Use `requirements-dev.txt` for development tools
- **Use dependency management tools**: Consider `poetry` or `pipenv` for better dependency management

#### Code Quality
- **Follow PEP 8**: Use `black`, `flake8`, `isort` for automatic formatting
- **Type hints**: Add type annotations for better code documentation and IDE support
- **Docstrings**: Follow Google, NumPy, or Sphinx docstring conventions
- **Modular structure**: Separate concerns into different modules/packages

#### Quality Assurance
- **Unit testing**: Use `pytest` with good test coverage (`pytest-cov`)
- **Linting**: `flake8`, `pylint`, or `ruff` for code quality
- **Pre-commit hooks**: Automate formatting and linting before commits
- **Type checking**: Use `mypy` for static type analysis

#### Security & Configuration
- **Environment variables**: Use `python-dotenv` for configuration management
- **Never commit secrets**: Use `.gitignore` and environment-specific configs
- **Input validation**: Sanitize and validate all user inputs
- **Dependency scanning**: Regular security audits with `pip-audit` or `safety`

### FastAPI Best Practices

#### Recommended Application Structure
```python
# For larger applications, consider this structure:
app/
├── __init__.py
├── main.py              # FastAPI app creation
├── dependencies.py      # Dependency injection
├── routers/            # Route handlers
│   ├── __init__.py
│   ├── extraction.py   # Extraction endpoints
│   └── jobs.py         # Job management endpoints
├── models/             # Pydantic models
├── schemas/            # Data validation schemas
├── services/           # Business logic
├── database.py         # DB configuration
└── config.py          # Settings management
```

#### Configuration Management
```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Tender Extraction API"
    database_url: str
    secret_key: str
    max_file_size: int = 10_000_000  # 10MB
    
    class Config:
        env_file = ".env"
```

#### Error Handling
- **Use HTTPException** with proper status codes
- **Implement custom exception handlers** for application-specific errors
- **Log errors appropriately** with structured logging
- **Return consistent error response format**

#### Database & Dependencies
- **Use dependency injection** for database sessions, authentication, etc.
- **Implement proper connection pooling** for database connections
- **Use migrations** (Alembic with SQLAlchemy) for database schema management
- **Separate business logic** from route handlers

#### Performance & Production
- **Async/await**: Use async for I/O operations (already implemented for file processing)
- **Background tasks**: Current BackgroundTasks usage is good; consider Celery for complex workflows
- **Caching**: Implement Redis for job status and results caching
- **Rate limiting**: Use `slowapi` for API rate limiting
- **File handling**: Implement proper file cleanup and secure storage

#### Security
- **CORS configuration**: Properly configure CORS middleware
- **Authentication**: Implement proper API authentication (JWT tokens, API keys)
- **Input validation**: Validate file types, sizes, and content
- **File upload security**: Scan uploaded files, limit file sizes
- **Logging**: Log security events and failed attempts

#### Documentation
- **Route documentation**: Add comprehensive docstrings to all endpoints
- **Response models**: Define proper response models and status codes
- **Examples**: Include request/response examples in Pydantic models
- **API versioning**: Consider versioning strategy for future API changes

#### Testing
```python
from fastapi.testclient import TestClient
import pytest

def test_extract_single_document():
    with TestClient(app) as client:
        # Test with valid PDF
        with open("test.pdf", "rb") as f:
            response = client.post(
                "/extract-single",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        assert response.status_code == 200
        assert "job_id" in response.json()
```

### Recommendations for This Project

#### Immediate Improvements
1. **Create `requirements.txt`**: Pin all dependencies with versions
2. **Environment configuration**: Move hardcoded values to environment variables
3. **Error handling**: Add comprehensive exception handling for file operations
4. **Logging**: Implement structured logging for debugging and monitoring
5. **File cleanup**: Add proper temporary file cleanup mechanisms

#### Medium-term Enhancements
1. **Database migration**: Replace in-memory job storage with Redis or PostgreSQL
2. **Authentication**: Add API key or JWT-based authentication
3. **Rate limiting**: Implement request rate limiting
4. **Health checks**: Add `/health` endpoint for monitoring
5. **Testing**: Add comprehensive unit and integration tests

#### Production Readiness
1. **Containerization**: Create Dockerfile with multi-stage builds
2. **Monitoring**: Add metrics and tracing (OpenTelemetry)
3. **Security scanning**: Implement file content scanning
4. **Load balancing**: Use Gunicorn with Uvicorn workers
5. **Backup strategy**: Implement job result persistence and backup

I want to build this project in stages. For now only follow the prompt. I'll give you the next step after reviewing this one.
Test the code you write, with unit tests and integration tests.
