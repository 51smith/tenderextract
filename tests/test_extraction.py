"""Tests for extraction endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import io

from app.main import app

client = TestClient(app)


def create_test_pdf_file():
    """Create a mock PDF file for testing."""
    # This creates a minimal file that can be used for testing
    # In a real scenario, you'd want to use an actual PDF
    content = io.BytesIO(b"Mock PDF content")
    content.seek(0, 2)  # Go to end
    size = content.tell()  # Get size
    content.seek(0)  # Reset to beginning
    return ("test.pdf", content, "application/pdf", size)


def test_extract_single_document():
    """Test single document extraction endpoint."""
    filename, file_content, content_type, size = create_test_pdf_file()
    
    response = client.post(
        "/api/v1/extract-single",
        files={"file": (filename, file_content, content_type)},
        data={"language": "nl"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"


def test_extract_single_document_invalid_file_type():
    """Test single document extraction with invalid file type."""
    response = client.post(
        "/api/v1/extract-single",
        files={"file": ("test.txt", io.BytesIO(b"Text content"), "text/plain")},
        data={"language": "nl"}
    )
    
    assert response.status_code == 400
    response_data = response.json()
    assert "error" in response_data or "detail" in response_data
    error_message = response_data.get("error", response_data.get("detail", "")).lower()
    assert "not allowed" in error_message


def test_extract_single_document_invalid_language():
    """Test single document extraction with invalid language."""
    filename, file_content, content_type, size = create_test_pdf_file()
    
    response = client.post(
        "/api/v1/extract-single",
        files={"file": (filename, file_content, content_type)},
        data={"language": "invalid"}
    )
    
    assert response.status_code == 400
    response_data = response.json()
    assert "error" in response_data or "detail" in response_data
    error_message = response_data.get("error", response_data.get("detail", "")).lower()
    assert "not supported" in error_message


def test_batch_extraction():
    """Test batch document extraction."""
    file1 = create_test_pdf_file()
    content2 = io.BytesIO(b"Mock PDF content 2")
    content2.seek(0, 2); size2 = content2.tell(); content2.seek(0)
    file2 = ("test2.pdf", content2, "application/pdf", size2)
    
    response = client.post(
        "/api/v1/extract-batch",
        files=[
            ("files", (file1[0], file1[1], file1[2])),
            ("files", (file2[0], file2[1], file2[2]))
        ],
        data={
            "job_name": "Test Batch",
            "language": "nl",
            "merge_results": "true",
            "extract_relationships": "true"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"
    assert data["total_documents"] == 2


def test_get_job_status_not_found():
    """Test getting status of non-existent job."""
    response = client.get("/api/v1/status/nonexistent-job-id")
    assert response.status_code == 404


def test_export_results_not_found():
    """Test exporting results of non-existent job."""
    response = client.get("/api/v1/export/nonexistent-job-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_storage():
    """Test job storage functionality."""
    from app.services.job_storage import InMemoryJobStorage
    from app.models.jobs import SingleExtractionJob, JobStatus, JobType
    
    storage = InMemoryJobStorage()
    
    # Create a job
    job = SingleExtractionJob(
        job_id="",
        status=JobStatus.PROCESSING,
        job_type=JobType.SINGLE,
        language="nl",
        filename="test.pdf"
    )
    
    job_id = await storage.create_job(job)
    assert job_id
    
    # Retrieve the job
    retrieved_job = await storage.get_job(job_id)
    assert retrieved_job is not None
    assert retrieved_job.filename == "test.pdf"
    assert retrieved_job.language == "nl"
    
    # Update the job
    success = await storage.update_job(job_id, {"status": JobStatus.COMPLETED})
    assert success
    
    # Verify update
    updated_job = await storage.get_job(job_id)
    assert updated_job.status == JobStatus.COMPLETED