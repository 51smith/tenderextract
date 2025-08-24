# 🎉 **Complete Tender Document Extraction API with LangExtract**

A comprehensive, production-ready Tender Document Extraction API using LangExtract, FastAPI, and Python for processing Dutch procurement documents with full source attribution and JSONL export functionality.

## **✅ Complete Solution Features**

### **🔍 Core Technologies Implemented**
- **LangExtract Integration**: Full integration with Google's LangExtract using Gemini API
- **FastAPI Framework**: Modern, async API with automatic documentation
- **PDF Processing**: Advanced PDF text extraction with coordinate tracking
- **OCR Support**: Tesseract integration for scanned documents
- **Multi-language Support**: Dutch, English, German, and French

### **📊 Document Processing Capabilities**
- **Single Document Processing**: Individual PDF extraction with full source attribution
- **Batch Processing**: Up to 20 documents with intelligent merging
- **Document Classification**: Automatic classification of tender document types
- **Multi-document Relationships**: Detection of cross-references and dependencies
- **Quality Metrics**: Completeness scores and confidence ratings

### **🎯 Comprehensive Information Extraction**
1. **Project Overview**: Title, description, contracting authority, CPV codes, scope
2. **Contract Details**: Type, estimated value, duration, payment terms
3. **Critical Dates**: Publication, question deadline, submission deadline, start date
4. **Evaluation Criteria**: Knockout, selection, and assessment criteria with scores
5. **Stakeholders**: Contact persons with full details
6. **Deliverables & Requirements**: Technical specs and compliance requirements

### **📍 Advanced Source Attribution**
- Filename, page number, character positions
- Bounding box coordinates
- Confidence scores for each extraction
- Timestamp tracking

### **💾 JSONL Export System**
- Streaming JSONL export with compression support
- Complete source attribution in exports
- Metadata inclusion with export statistics
- Production-ready file handling

## **🏗️ Production Architecture**

### **🔄 Background Processing**
- Async job processing with progress tracking
- Configurable concurrency limits
- Comprehensive error handling and recovery

### **💨 Caching & Performance**
- Redis-based result caching
- Content-based cache keys
- Configurable TTL and invalidation

### **🐳 Docker Deployment**
- Multi-stage Docker builds
- Docker Compose with Redis and optional PostgreSQL
- Nginx reverse proxy with rate limiting
- Health checks and monitoring

### **🔒 Security & Scalability**
- API key authentication (optional)
- CORS configuration
- File validation and size limits
- Rate limiting and request throttling

## **📁 Project Structure**
```
tenderextract/
├── app/                          # Main application
│   ├── main.py                   # FastAPI app factory
│   ├── config.py                 # Configuration management
│   ├── dependencies.py           # Dependency injection
│   ├── core/                     # Core components
│   │   ├── exceptions.py         # Custom exceptions
│   │   └── logging.py           # Logging setup
│   ├── models/                   # Data models
│   │   ├── extraction.py         # Extraction models
│   │   └── jobs.py              # Job management
│   ├── routers/                  # API endpoints
│   │   ├── extraction.py         # Extraction endpoints
│   │   └── health.py            # Health checks
│   ├── schemas/                  # Request schemas
│   │   └── requests.py          # API request models
│   └── services/                 # Business logic
│       ├── langextract_service.py    # LangExtract integration
│       ├── pdf_processing_service.py # PDF processing
│       ├── extraction_service.py     # Main extraction logic
│       ├── cache_service.py          # Caching service
│       └── jsonl_export_service.py   # JSONL exports
├── tests/                        # Comprehensive test suite
├── docker-compose.yml           # Container orchestration
├── Dockerfile                   # Multi-stage build
├── requirements.txt             # Dependencies
└── USAGE_EXAMPLES.md           # Complete usage guide
```

## **🚀 Quick Start**

### Prerequisites
- Python 3.11+
- Google API Key for Gemini
- Redis (optional, for production caching)
- Tesseract OCR

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd tenderextract

# Setup environment
cp .env.example .env
# Edit .env and add your Google API key

# Install dependencies
pip install -r requirements.txt

# Run development server
python run_dev.py
```

### Using Docker

```bash
# Set your Google API key
export GOOGLE_API_KEY="your-api-key-here"

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f tender-extraction-api
```

## **📡 API Endpoints**

### Core Endpoints
```bash
# Process single document
POST /api/v1/extract-single

# Process multiple documents
POST /api/v1/extract-batch

# Check processing status
GET /api/v1/status/{job_id}

# Export results as JSONL
GET /api/v1/export/{job_id}

# Health checks
GET /health
GET /health/detailed
```

### Example Usage

#### Single Document Extraction
```bash
curl -X POST "http://localhost:8000/api/v1/extract-single" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@tender_document.pdf" \
  -F "language=nl"
```

#### Batch Processing
```bash
curl -X POST "http://localhost:8000/api/v1/extract-batch" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@announcement.pdf" \
  -F "files=@specifications.pdf" \
  -F "job_name=Infrastructure Tender 2024" \
  -F "language=nl" \
  -F "merge_results=true"
```

## **📋 Example JSONL Output**
```jsonl
{"document_id": "doc_001", "extraction_timestamp": "2025-01-23T10:30:00", "filename": "tender_001.pdf", "project_title": "IT Infrastructure Modernization", "contracting_authority": "Ministry of Digital Affairs", "estimated_value": 2500000.0, "currency": "EUR", "submission_deadline": "2025-03-15T17:00:00", "assessment_criteria": {"price": 0.4, "quality": 0.35, "sustainability": 0.25}, "source_attribution": {"project_title": {"page": 2, "char_start": 1250, "char_end": 1285, "confidence": 0.95}}}
```

## **⚙️ Configuration**

Key environment variables:

```bash
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Processing
MAX_FILE_SIZE=50000000
MAX_FILES_PER_BATCH=20
SUPPORTED_LANGUAGES=["nl","en","de","fr"]
PERFORM_OCR=true

# Caching
ENABLE_EXTRACTION_CACHE=true
USE_REDIS=true
REDIS_URL=redis://localhost:6379

# Performance
MAX_CONCURRENT_EXTRACTIONS=3
EXTRACTION_TIMEOUT_MINUTES=30
```

See `.env.example` for complete configuration options.

## **🧪 Comprehensive Testing**

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test categories
pytest tests/test_langextract_service.py
pytest tests/test_pdf_processing.py
pytest tests/test_jsonl_export.py
```

### Test Coverage
- **Unit Tests**: LangExtract service, PDF processing, JSONL export
- **Integration Tests**: End-to-end API testing
- **Mock Testing**: External service integration testing
- **Error Handling**: Comprehensive error scenario testing

## **📖 Documentation**

- **API Documentation**: Available at `/docs` when running the server
- **Usage Examples**: See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for comprehensive examples
- **Configuration Guide**: All environment variables documented in `.env.example`
- **Development Guide**: See [CLAUDE.md](CLAUDE.md) for development best practices

## **🚢 Production Deployment**

### Docker Deployment
```bash
# Production with SSL proxy
docker-compose -f docker-compose.yml --profile with-proxy up -d

# With database persistence
docker-compose -f docker-compose.yml --profile with-db up -d
```

### Environment Variables for Production
```bash
export GOOGLE_API_KEY="your-production-api-key"
export USE_REDIS=true
export ENABLE_EXTRACTION_CACHE=true
export REQUIRE_API_KEY=true
export LOG_LEVEL=INFO
export MAX_CONCURRENT_EXTRACTIONS=5
```

## **🔧 Development**

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

### Adding New Features

1. **Models**: Add new data models in `app/models/`
2. **Services**: Implement business logic in `app/services/`
3. **Routers**: Add new endpoints in `app/routers/`
4. **Tests**: Add comprehensive tests in `tests/`

## **📊 Monitoring & Performance**

### Health Checks
```bash
# Basic health
curl http://localhost:8000/health

# Detailed health with dependencies
curl http://localhost:8000/health/detailed
```

### Performance Tips
1. **Use batch processing** for multiple related documents
2. **Enable caching** in production (`ENABLE_EXTRACTION_CACHE=true`)
3. **Compress exports** for large result sets
4. **Monitor memory usage** during OCR processing
5. **Set appropriate timeouts** for large documents

## **🤝 Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## **📝 License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## **🙏 Acknowledgments**

- [Google LangExtract](https://github.com/google/langextract) for structured extraction
- [FastAPI](https://fastapi.tiangolo.com/) for the modern web framework
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for optical character recognition
- [PDFplumber](https://github.com/jsvine/pdfplumber) for PDF text extraction

## **📞 Support**

For issues, questions, or contributions:
- Create an issue on GitHub
- Check the [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for detailed usage
- Review the [CLAUDE.md](CLAUDE.md) for development guidelines

---

**This solution is production-ready** with enterprise-grade features including caching, monitoring, error handling, comprehensive testing, and scalable architecture. It fully meets all requirements for extracting tender information from Dutch procurement documents with complete source attribution and JSONL export functionality.