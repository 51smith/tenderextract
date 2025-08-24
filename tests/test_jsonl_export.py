"""Tests for JSONL export service."""
import pytest
import json
import gzip
from datetime import datetime
from unittest.mock import Mock

from app.services.jsonl_export_service import JSONLExportService
from app.models.extraction import DocumentExtractionResult, MergedTenderResult
from app.models.jobs import SingleExtractionJob, BatchExtractionJob, JobStatus, JobType


class TestJSONLExportService:
    """Test cases for JSONLExportService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return JSONLExportService()
    
    @pytest.fixture
    def sample_extraction_result(self):
        """Create sample extraction result for testing."""
        return DocumentExtractionResult(
            document_id="doc_123",
            filename="test_tender.pdf",
            document_type="tender_announcement",
            extraction_timestamp=datetime(2024, 1, 15, 10, 30, 0),
            project_title="IT Infrastructure Modernization",
            contracting_authority="Ministry of Digital Affairs",
            cpv_codes=["48000000-8"],
            estimated_value=500000.0,
            currency="EUR",
            submission_deadline=datetime(2024, 2, 15, 17, 0, 0),
            assessment_criteria={"price": 0.4, "quality": 0.35, "sustainability": 0.25},
            contact_persons=[{"name": "John Doe", "email": "j.doe@ministry.gov"}],
            completeness_score=0.85,
            confidence_scores={"project_overview": 0.9, "contract_details": 0.8},
            source_attribution={
                "project_title": {
                    "source_filename": "test_tender.pdf",
                    "page_number": 1,
                    "char_start": 100,
                    "char_end": 130,
                    "confidence_score": 0.95
                }
            }
        )
    
    @pytest.fixture
    def sample_merged_result(self):
        """Create sample merged result for testing."""
        return MergedTenderResult(
            tender_id="tender_456",
            extraction_timestamp=datetime(2024, 1, 15, 10, 35, 0),
            source_documents=["announcement.pdf", "specs.pdf"],
            project_overview={"title": "IT Infrastructure", "authority": "Ministry"},
            contract_details={"value": 500000, "currency": "EUR"},
            critical_dates={"submission": "2024-02-15T17:00:00"},
            stakeholders=[{"name": "John Doe", "role": "Contact"}],
            evaluation_criteria={"assessment": {"price": 0.4}},
            deliverables_and_requirements={"deliverables": ["Software", "Training"]},
            document_relationships=[{"type": "references", "source": "doc1", "target": "doc2"}],
            completeness_score=0.85,
            confidence_scores={"overall": 0.8}
        )
    
    @pytest.fixture
    def sample_single_job(self, sample_extraction_result):
        """Create sample single extraction job."""
        return SingleExtractionJob(
            job_id="job_123",
            status=JobStatus.COMPLETED,
            job_type=JobType.SINGLE,
            language="nl",
            filename="test.pdf",
            result=sample_extraction_result.model_dump(),
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            updated_at=datetime(2024, 1, 15, 10, 30, 0)
        )
    
    @pytest.fixture
    def sample_batch_job(self, sample_extraction_result, sample_merged_result):
        """Create sample batch extraction job."""
        return BatchExtractionJob(
            job_id="batch_456",
            status=JobStatus.COMPLETED,
            job_type=JobType.BATCH,
            job_name="Test Batch",
            total_documents=2,
            processed_documents=2,
            filenames=["doc1.pdf", "doc2.pdf"],
            language="nl",
            merge_results=True,
            extract_relationships=True,
            merged_result=sample_merged_result.model_dump(),
            individual_results=[sample_extraction_result.model_dump()],
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            updated_at=datetime(2024, 1, 15, 10, 35, 0)
        )
    
    def test_export_single_result(self, service, sample_extraction_result):
        """Test exporting single extraction result."""
        jsonl_output = service.export_single_result(
            sample_extraction_result, 
            include_metadata=True, 
            compress=False
        )
        
        lines = jsonl_output.strip().split('\n')
        assert len(lines) == 2  # metadata + result
        
        # Parse metadata
        metadata = json.loads(lines[0])
        assert metadata["export_type"] == "tender_extraction_results"
        assert metadata["total_documents"] == 1
        assert "export_timestamp" in metadata
        
        # Parse result
        result = json.loads(lines[1])
        assert result["document_id"] == "doc_123"
        assert result["project_title"] == "IT Infrastructure Modernization"
        assert result["result_type"] == "document_extraction"
        assert result["estimated_value"] == 500000.0
    
    def test_export_single_result_compressed(self, service, sample_extraction_result):
        """Test exporting single result with compression."""
        compressed_output = service.export_single_result(
            sample_extraction_result,
            include_metadata=False,
            compress=True
        )
        
        assert isinstance(compressed_output, bytes)
        
        # Decompress and verify
        decompressed = gzip.decompress(compressed_output).decode('utf-8')
        result = json.loads(decompressed.strip())
        assert result["document_id"] == "doc_123"
        assert result["project_title"] == "IT Infrastructure Modernization"
    
    def test_export_batch_results(self, service, sample_extraction_result, sample_merged_result):
        """Test exporting batch results."""
        jsonl_output = service.export_batch_results(
            individual_results=[sample_extraction_result],
            merged_result=sample_merged_result,
            include_metadata=True,
            compress=False
        )
        
        lines = jsonl_output.strip().split('\n')
        assert len(lines) == 3  # metadata + merged + individual
        
        # Parse metadata
        metadata = json.loads(lines[0])
        assert metadata["total_documents"] == 1  # Only individual results are counted as "documents"
        
        # Parse merged result (should come first)
        merged = json.loads(lines[1])
        assert merged["tender_id"] == "tender_456"
        assert merged["result_type"] == "merged_extraction"
        
        # Parse individual result
        individual = json.loads(lines[2])
        assert individual["document_id"] == "doc_123"
        assert individual["result_type"] == "document_extraction"
    
    def test_export_job_results_single(self, service, sample_single_job):
        """Test exporting single job results."""
        jsonl_output = service.export_job_results(
            sample_single_job,
            include_metadata=True,
            compress=False
        )
        
        lines = jsonl_output.strip().split('\n')
        assert len(lines) == 2  # job metadata + result
        
        # Parse job metadata
        metadata = json.loads(lines[0])
        assert metadata["export_type"] == "job_results"
        assert metadata["job_id"] == "job_123"
        assert metadata["job_type"] == "single"
        assert metadata["language"] == "nl"
        
        # Parse result with job context
        result = json.loads(lines[1])
        assert "job_context" in result
        assert result["job_context"]["job_id"] == "job_123"
        assert result["job_context"]["processing_language"] == "nl"
    
    def test_export_job_results_batch(self, service, sample_batch_job):
        """Test exporting batch job results."""
        jsonl_output = service.export_job_results(
            sample_batch_job,
            include_metadata=True,
            compress=False
        )
        
        lines = jsonl_output.strip().split('\n')
        assert len(lines) == 3  # metadata + merged + individual
        
        # Parse job metadata
        metadata = json.loads(lines[0])
        assert metadata["job_type"] == "batch"
        assert metadata["job_name"] == "Test Batch"
        assert metadata["total_documents"] == 2
    
    def test_date_formatting(self, service, sample_extraction_result):
        """Test proper date formatting in exports."""
        jsonl_output = service.export_single_result(
            sample_extraction_result,
            include_metadata=False,
            compress=False
        )
        
        result = json.loads(jsonl_output.strip())
        
        # Dates should be ISO formatted strings
        assert result["extraction_timestamp"] == "2024-01-15T10:30:00"
        assert result["submission_deadline"] == "2024-02-15T17:00:00"
        
        # Source attribution dates should also be formatted
        if "source_attribution" in result:
            for field, attr in result["source_attribution"].items():
                if isinstance(attr, dict) and "extraction_timestamp" in attr:
                    # Should be ISO string, not datetime object
                    assert isinstance(attr["extraction_timestamp"], str)
    
    def test_content_type_and_filename_generation(self, service):
        """Test content type and filename generation."""
        # Test uncompressed
        content_type = service.get_content_type(compress=False)
        assert content_type == "application/x-ndjson"
        
        filename = service.get_filename("job_123", compress=False, timestamp=False)
        assert filename == "tender_extraction_job_123.jsonl"
        
        # Test compressed
        content_type = service.get_content_type(compress=True)
        assert content_type == "application/gzip"
        
        filename = service.get_filename("job_123", compress=True, timestamp=False)
        assert filename == "tender_extraction_job_123.jsonl.gz"
        
        # Test with timestamp
        filename = service.get_filename("job_123", timestamp=True)
        assert "tender_extraction_job_123_" in filename
        assert filename.endswith(".jsonl")
    
    def test_streaming_response_creation(self, service):
        """Test creating streaming response."""
        test_content = '{"test": "data"}\n{"more": "data"}'
        
        # Test with string input
        stream = service.create_streaming_response(test_content, "test.jsonl")
        content = stream.read()
        assert content.decode('utf-8') == test_content
        
        # Test with bytes input
        stream = service.create_streaming_response(test_content.encode('utf-8'), "test.jsonl")
        content = stream.read()
        assert content.decode('utf-8') == test_content
    
    def test_empty_results_handling(self, service):
        """Test handling of empty results."""
        # Test with empty list
        jsonl_output = service.export_batch_results(
            individual_results=[],
            merged_result=None,
            include_metadata=True,
            compress=False
        )
        
        lines = jsonl_output.strip().split('\n')
        assert len(lines) == 1  # Only metadata
        
        metadata = json.loads(lines[0])
        assert metadata["total_documents"] == 0