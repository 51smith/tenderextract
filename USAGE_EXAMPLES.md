# Tender Document Extraction API - Usage Examples

This document provides comprehensive examples of how to use the Tender Document Extraction API.

## Quick Start

### 1. Setup and Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd tenderextract

# Set up environment
cp .env.example .env
# Edit .env with your Google API key

# Install dependencies
pip install -r requirements.txt

# Run the development server
python run_dev.py
```

### 2. Using Docker

```bash
# Set your Google API key
export GOOGLE_API_KEY="your-api-key-here"

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f tender-extraction-api
```

## API Usage Examples

### Single Document Extraction

#### Basic Single Document Upload

```bash
curl -X POST "http://localhost:8000/api/v1/extract-single" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@tender_document.pdf" \
  -F "language=nl"
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Document processing started"
}
```

#### Check Processing Status

```bash
curl -X GET "http://localhost:8000/api/v1/status/550e8400-e29b-41d4-a716-446655440000"
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "job_type": "single",
  "filename": "tender_document.pdf",
  "language": "nl",
  "result": {
    "document_id": "doc_123",
    "filename": "tender_document.pdf",
    "document_type": "tender_announcement",
    "extraction_timestamp": "2024-01-15T10:30:00Z",
    "project_title": "IT Infrastructure Modernization",
    "contracting_authority": "Ministry of Digital Affairs",
    "cpv_codes": ["48000000-8"],
    "estimated_value": 500000.0,
    "currency": "EUR",
    "submission_deadline": "2024-02-15T17:00:00Z",
    "assessment_criteria": {
      "price": 0.4,
      "quality": 0.35,
      "sustainability": 0.25
    },
    "source_attribution": {
      "project_title": {
        "source_filename": "tender_document.pdf",
        "page_number": 1,
        "char_start": 1250,
        "char_end": 1285,
        "confidence_score": 0.95,
        "bbox": [100, 200, 400, 220]
      }
    },
    "completeness_score": 0.85,
    "confidence_scores": {
      "project_overview": 0.9,
      "contract_details": 0.8,
      "critical_dates": 0.85
    }
  }
}
```

### Batch Document Extraction

#### Process Multiple Documents with Merging

```bash
curl -X POST "http://localhost:8000/api/v1/extract-batch" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@tender_announcement.pdf" \
  -F "files=@technical_specifications.pdf" \
  -F "files=@evaluation_criteria.pdf" \
  -F "job_name=Infrastructure Tender 2024" \
  -F "language=nl" \
  -F "merge_results=true" \
  -F "extract_relationships=true"
```

Response:
```json
{
  "job_id": "batch_456",
  "status": "processing",
  "total_documents": 3,
  "processed_documents": 0,
  "progress": 0.0
}
```

### Export Results as JSONL

#### Basic Export

```bash
curl -X GET "http://localhost:8000/api/v1/export/550e8400-e29b-41d4-a716-446655440000" \
  -H "Accept: application/x-ndjson" \
  -o results.jsonl
```

#### Compressed Export with Metadata

```bash
curl -X GET "http://localhost:8000/api/v1/export/batch_456?compress=true&include_metadata=true" \
  -H "Accept: application/gzip" \
  -o results.jsonl.gz
```

## Example JSONL Output

### Single Document Result
```jsonl
{"export_type": "job_results", "export_timestamp": "2024-01-15T10:30:00Z", "job_id": "550e8400-e29b-41d4-a716-446655440000", "job_type": "single", "language": "nl"}
{"document_id": "doc_123", "filename": "tender_document.pdf", "document_type": "tender_announcement", "extraction_timestamp": "2024-01-15T10:30:00Z", "project_title": "IT Infrastructure Modernization", "contracting_authority": "Ministry of Digital Affairs", "cpv_codes": ["48000000-8"], "estimated_value": 500000.0, "currency": "EUR", "submission_deadline": "2024-02-15T17:00:00Z", "assessment_criteria": {"price": 0.4, "quality": 0.35, "sustainability": 0.25}, "contact_persons": [{"name": "John Doe", "role": "Project Manager", "email": "j.doe@ministry.gov", "phone": "+31-20-1234567"}], "deliverables": [{"name": "Software Implementation", "description": "Custom software solution", "deadline": "2024-06-01"}], "technical_requirements": ["Cloud-based architecture", "24/7 availability", "GDPR compliance"], "source_attribution": {"project_title": {"source_filename": "tender_document.pdf", "page_number": 1, "char_start": 1250, "char_end": 1285, "confidence_score": 0.95, "bbox": [100, 200, 400, 220]}}, "completeness_score": 0.85, "confidence_scores": {"project_overview": 0.9, "contract_details": 0.8}, "result_type": "document_extraction", "job_context": {"job_id": "550e8400-e29b-41d4-a716-446655440000", "job_type": "single", "processing_language": "nl", "processed_at": "2024-01-15T10:30:00Z"}}
```

### Batch Results with Merged Document
```jsonl
{"export_type": "job_results", "export_timestamp": "2024-01-15T10:35:00Z", "job_id": "batch_456", "job_type": "batch", "job_name": "Infrastructure Tender 2024", "total_documents": 3, "language": "nl"}
{"tender_id": "tender_789", "extraction_timestamp": "2024-01-15T10:35:00Z", "source_documents": ["tender_announcement.pdf", "technical_specifications.pdf", "evaluation_criteria.pdf"], "project_overview": {"title": "IT Infrastructure Modernization", "authority": "Ministry of Digital Affairs", "cpv_codes": ["48000000-8"], "sources": {"title": "tender_announcement.pdf", "authority": "tender_announcement.pdf"}}, "contract_details": {"estimated_value": 500000, "currency": "EUR", "contract_duration": "24 months", "value_discrepancies": []}, "evaluation_criteria": {"knockout_criteria": [{"type": "financial_capacity", "requirement": "Minimum €100,000 annual revenue"}], "selection_criteria": [{"type": "technical_experience", "requirement": "5+ years in similar projects"}], "assessment_criteria": {"price": 0.4, "quality": 0.35, "sustainability": 0.25}}, "document_relationships": [{"type": "references", "source": "tender_announcement.pdf", "target": "technical_specifications.pdf"}], "completeness_score": 0.92, "confidence_scores": {"overall": 0.88, "project_overview": 0.9, "evaluation_criteria": 0.85}, "result_type": "merged_extraction"}
```

## Python Client Examples

### Using requests library

```python
import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def extract_single_document(file_path, language="nl"):
    """Extract information from a single document."""
    
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f, 'application/pdf')}
        data = {'language': language}
        
        response = requests.post(f"{API_BASE}/extract-single", 
                               files=files, data=data)
        response.raise_for_status()
        
        return response.json()

def wait_for_completion(job_id, timeout=300):
    """Wait for job completion."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = requests.get(f"{API_BASE}/status/{job_id}")
        response.raise_for_status()
        
        job_data = response.json()
        status = job_data['status']
        
        if status == 'completed':
            return job_data
        elif status == 'failed':
            raise Exception(f"Job failed: {job_data.get('error')}")
        
        time.sleep(5)  # Poll every 5 seconds
    
    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

def export_results(job_id, compress=False):
    """Export results as JSONL."""
    params = {'compress': compress, 'include_metadata': True}
    
    response = requests.get(f"{API_BASE}/export/{job_id}", params=params)
    response.raise_for_status()
    
    return response.content

# Example usage
if __name__ == "__main__":
    # Extract single document
    job_response = extract_single_document("tender_document.pdf", "nl")
    job_id = job_response['job_id']
    print(f"Started extraction job: {job_id}")
    
    # Wait for completion
    result = wait_for_completion(job_id)
    print(f"Extraction completed with score: {result['result']['completeness_score']}")
    
    # Export results
    jsonl_data = export_results(job_id, compress=False)
    
    # Save to file
    with open(f"results_{job_id}.jsonl", 'wb') as f:
        f.write(jsonl_data)
    
    print("Results exported successfully")
```

### Batch Processing Example

```python
import requests
import os
from pathlib import Path

def process_tender_folder(folder_path, job_name=None):
    """Process all PDF files in a folder as a batch."""
    
    pdf_files = list(Path(folder_path).glob("*.pdf"))
    
    if not pdf_files:
        raise ValueError("No PDF files found in folder")
    
    files = []
    for pdf_file in pdf_files:
        files.append(('files', (pdf_file.name, open(pdf_file, 'rb'), 'application/pdf')))
    
    data = {
        'job_name': job_name or f"Batch_{len(pdf_files)}_documents",
        'language': 'nl',
        'merge_results': 'true',
        'extract_relationships': 'true'
    }
    
    try:
        response = requests.post(f"{API_BASE}/extract-batch", 
                               files=files, data=data)
        response.raise_for_status()
        return response.json()
    
    finally:
        # Close all file handles
        for _, (_, file_handle, _) in files:
            file_handle.close()

# Example usage
batch_job = process_tender_folder("tender_documents/", "Q1 2024 Tender")
print(f"Batch job started: {batch_job['job_id']}")
```

## Health Monitoring

### Basic Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

### Detailed Health Check
```bash
curl -X GET "http://localhost:8000/health/detailed"
```

## Error Handling

The API returns structured error responses:

```json
{
  "error": "File type 'text/plain' not allowed. Supported types: ['application/pdf']",
  "type": "ValidationError",
  "details": {
    "filename": "document.txt",
    "provided_type": "text/plain"
  }
}
```

Common error scenarios:
- Invalid file type (non-PDF)
- File too large (>50MB)
- Unsupported language
- Job not found
- Processing timeout

## Performance Tips

1. **Use batch processing** for multiple related documents
2. **Enable caching** in production (`ENABLE_EXTRACTION_CACHE=true`)
3. **Compress exports** for large result sets
4. **Monitor memory usage** during OCR processing
5. **Set appropriate timeouts** for large documents

## Production Deployment

### Using Docker Compose with SSL

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  tender-extraction-api:
    image: tender-extract:latest
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - USE_REDIS=true
      - ENABLE_EXTRACTION_CACHE=true
      - REQUIRE_API_KEY=true
      - LOG_LEVEL=INFO
    volumes:
      - ./ssl:/app/ssl:ro

  nginx:
    profiles: ["with-proxy"]
    volumes:
      - ./nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
```

### Environment Variables for Production

```bash
# Production environment
export GOOGLE_API_KEY="your-production-api-key"
export USE_REDIS=true
export ENABLE_EXTRACTION_CACHE=true
export REQUIRE_API_KEY=true
export LOG_LEVEL=INFO
export MAX_CONCURRENT_EXTRACTIONS=5
export CACHE_TTL_HOURS=168  # 1 week

# Start with production settings
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```