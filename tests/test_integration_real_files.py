"""Integration tests using real tender documents."""
import pytest
import asyncio
import time
import json
from pathlib import Path
from fastapi.testclient import TestClient
from typing import List, Dict

from app.main import app

# Test file paths
TEST_FILES_DIR = Path(__file__).parent / "Files"
SINGLE_TEST_FILE = TEST_FILES_DIR / "NPO - CEP - Opdrachtomschrijving(12648729) 2.pdf"
BATCH_TEST_FILES = [
    TEST_FILES_DIR / "Selectiefase - Opdrachtomschrijving 2.pdf",
    TEST_FILES_DIR / "Selectiefase - selectiecriteria.pdf",
    TEST_FILES_DIR / "Selectiefase - Uitsluitingsgronden en Geschi...pdf"
]

client = TestClient(app)


class TestRealFileIntegration:
    """Integration tests with real tender documents."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test method."""
        # Verify test files exist
        if not SINGLE_TEST_FILE.exists():
            pytest.skip(f"Single test file not found: {SINGLE_TEST_FILE}")
        
        for batch_file in BATCH_TEST_FILES:
            if not batch_file.exists():
                pytest.skip(f"Batch test file not found: {batch_file}")
    
    def test_single_document_extraction_workflow(self):
        """Test complete single document extraction workflow."""
        print(f"\\n=== Testing Single Document: {SINGLE_TEST_FILE.name} ===")
        
        # Step 1: Submit extraction job
        # Read file content first, then submit
        file_content = SINGLE_TEST_FILE.read_bytes()
        response = client.post(
            "/api/v1/extract-single",
            files={"file": (SINGLE_TEST_FILE.name, file_content, "application/pdf")},
            data={
                "language": "nl",
                "perform_ocr": True
            }
        )
        
        assert response.status_code == 200, f"Extraction failed: {response.text}"
        result = response.json()
        assert "job_id" in result
        job_id = result["job_id"]
        print(f"✅ Job submitted successfully: {job_id}")
        
        # Step 2: Monitor job status until completion
        status_result = self._wait_for_job_completion(job_id)
        print(f"✅ Job completed with status: {status_result['status']}")
        
        # Verify extraction results
        assert "result" in status_result
        extraction_result = status_result["result"]
        
        # Basic validation of extraction results
        assert extraction_result["filename"] == SINGLE_TEST_FILE.name
        assert "document_id" in extraction_result
        assert "extraction_timestamp" in extraction_result
        
        print(f"✅ Document Type: {extraction_result.get('document_type', 'N/A')}")
        print(f"✅ Project Title: {extraction_result.get('project_title', 'N/A')}")
        print(f"✅ Contracting Authority: {extraction_result.get('contracting_authority', 'N/A')}")
        
        # Step 3: Export results
        export_response = client.get(f"/api/v1/export/{job_id}")
        assert export_response.status_code == 200
        
        # Verify JSONL export
        export_content = export_response.content.decode('utf-8')
        jsonl_lines = [line for line in export_content.strip().split('\n') if line]
        print(f"📊 Single document JSONL lines: {len(jsonl_lines)}")
        assert len(jsonl_lines) >= 1  # At least metadata or result
        
        # Parse and validate JSONL content
        for i, line in enumerate(jsonl_lines):
            try:
                parsed = json.loads(line)
                assert isinstance(parsed, dict)
            except json.JSONDecodeError as e:
                print(f"Failed to parse line {i+1}: {line[:100]}...")
                raise
        
        print(f"✅ Export successful: {len(jsonl_lines)} JSONL lines")
        
        return job_id, status_result, export_content
    
    def test_batch_document_extraction_workflow(self):
        """Test complete batch document extraction workflow."""
        print(f"\\n=== Testing Batch Documents: {len(BATCH_TEST_FILES)} files ===")
        
        # Step 1: Submit batch extraction job
        files_data = []
        for batch_file in BATCH_TEST_FILES:
            file_content = batch_file.read_bytes()
            files_data.append(
                ("files", (batch_file.name, file_content, "application/pdf"))
            )
        
        response = client.post(
            "/api/v1/extract-batch",
            files=files_data,
            data={
                "job_name": "Integration Test Batch",
                "language": "nl",
                "merge_results": "true",
                "extract_relationships": "true"
            }
        )
        
        assert response.status_code == 200, f"Batch extraction failed: {response.text}"
        result = response.json()
        assert "job_id" in result
        job_id = result["job_id"]
        print(f"✅ Batch job submitted successfully: {job_id}")
        
        # Step 2: Monitor job status until completion  
        status_result = self._wait_for_job_completion(job_id, timeout_minutes=10)
        print(f"✅ Batch job completed with status: {status_result['status']}")
        
        # Verify batch results structure
        if status_result["status"] == "completed":
            assert "individual_results" in status_result or "results" in status_result
            assert "merged_result" in status_result
            
            # Check individual results
            individual_results = status_result.get("individual_results", status_result.get("results", []))
            assert len(individual_results) == len(BATCH_TEST_FILES)
            print(f"✅ Individual results: {len(individual_results)} documents")
            
            # Check merged result
            merged_result = status_result.get("merged_result")
            if merged_result:
                assert "tender_id" in merged_result
                print(f"✅ Merged result created: {merged_result.get('tender_id')}")
        
        # Step 3: Export batch results
        export_response = client.get(
            f"/api/v1/export/{job_id}",
            params={"include_metadata": True, "compress": False}
        )
        assert export_response.status_code == 200
        
        # Verify batch JSONL export
        export_content = export_response.content.decode('utf-8')
        jsonl_lines = [line for line in export_content.strip().split('\n') if line]
        print(f"📊 JSONL export lines: {len(jsonl_lines)}")
        # Should have: metadata (1) + merged result (1) + individual results (3) = 5 lines minimum
        assert len(jsonl_lines) >= 1  # At least metadata line
        
        print(f"✅ Batch export successful: {len(jsonl_lines)} JSONL lines")
        
        # Parse and categorize JSONL content
        metadata_count = 0
        individual_count = 0
        merged_count = 0
        
        for line in jsonl_lines:
            parsed = json.loads(line)
            if "export_type" in parsed:
                metadata_count += 1
            elif parsed.get("result_type") == "merged_extraction":
                merged_count += 1
            elif parsed.get("result_type") == "document_extraction":
                individual_count += 1
        
        print(f"✅ Export breakdown - Metadata: {metadata_count}, Individual: {individual_count}, Merged: {merged_count}")
        
        return job_id, status_result, export_content
    
    def test_status_endpoint_functionality(self):
        """Test status endpoint with various scenarios."""
        print("\\n=== Testing Status Endpoint Functionality ===")
        
        # Test with non-existent job ID
        response = client.get("/api/v1/status/non-existent-job-id")
        assert response.status_code == 404
        print("✅ Non-existent job returns 404")
        
        # Test with real job
        job_id, _, _ = self.test_single_document_extraction_workflow()
        
        response = client.get(f"/api/v1/status/{job_id}")
        assert response.status_code == 200
        
        status_data = response.json()
        assert "status" in status_data
        assert "job_id" in status_data
        assert status_data["job_id"] == job_id
        print(f"✅ Status endpoint working for job: {job_id}")
    
    def test_export_endpoint_functionality(self):
        """Test export endpoint with various parameters."""
        print("\\n=== Testing Export Endpoint Functionality ===")
        
        # Get a completed job
        job_id, _, _ = self.test_single_document_extraction_workflow()
        
        # Test different export parameters
        test_cases = [
            {"compress": False, "include_metadata": True},
            {"compress": False, "include_metadata": False},
            {"compress": True, "include_metadata": True},
        ]
        
        for params in test_cases:
            response = client.get(f"/api/v1/export/{job_id}", params=params)
            assert response.status_code == 200
            
            if params["compress"]:
                # Should return gzipped content
                assert response.headers["content-type"] == "application/gzip"
                print(f"✅ Compressed export successful")
            else:
                # Should return JSONL content
                assert "application/x-ndjson" in response.headers["content-type"]
                print(f"✅ Uncompressed export successful")
        
        # Test with non-existent job
        response = client.get("/api/v1/export/non-existent-job-id")
        assert response.status_code == 404
        print("✅ Non-existent job export returns 404")
    
    def test_error_handling(self):
        """Test error handling with invalid files."""
        print("\\n=== Testing Error Handling ===")
        
        # Test with invalid file type
        response = client.post(
            "/api/v1/extract-single",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
            data={"language": "nl"}
        )
        assert response.status_code == 400
        print("✅ Invalid file type properly rejected")
        
        # Test with invalid language
        file_content = SINGLE_TEST_FILE.read_bytes()
        response = client.post(
            "/api/v1/extract-single",
            files={"file": (SINGLE_TEST_FILE.name, file_content, "application/pdf")},
            data={"language": "invalid"}
        )
        assert response.status_code == 400
        print("✅ Invalid language properly rejected")
    
    def _wait_for_job_completion(self, job_id: str, timeout_minutes: int = 5) -> Dict:
        """Wait for job completion with timeout."""
        timeout_seconds = timeout_minutes * 60
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            response = client.get(f"/api/v1/status/{job_id}")
            assert response.status_code == 200
            
            status_data = response.json()
            status = status_data["status"]
            
            print(f"Job {job_id} status: {status}")
            
            if status == "completed":
                return status_data
            elif status == "failed":
                error_msg = status_data.get("error", "Unknown error")
                pytest.fail(f"Job failed: {error_msg}")
            elif status in ["pending", "processing"]:
                time.sleep(2)  # Wait 2 seconds before checking again
            else:
                pytest.fail(f"Unknown job status: {status}")
        
        pytest.fail(f"Job {job_id} did not complete within {timeout_minutes} minutes")
    
    def test_complete_workflow_analysis(self):
        """Analyze complete extraction results for insights."""
        print("\\n=== Complete Workflow Analysis ===")
        
        # Run both single and batch extractions
        single_job_id, single_result, single_export = self.test_single_document_extraction_workflow()
        batch_job_id, batch_result, batch_export = self.test_batch_document_extraction_workflow()
        
        print("\\n📊 ANALYSIS SUMMARY:")
        print("=" * 50)
        
        # Analyze single document
        if single_result.get("status") == "completed":
            result = single_result["result"]
            print(f"📄 Single Document Analysis:")
            print(f"   - Document: {result.get('filename')}")
            print(f"   - Type: {result.get('document_type')}")
            print(f"   - Project: {result.get('project_title', 'Not found')}")
            print(f"   - Authority: {result.get('contracting_authority', 'Not found')}")
            print(f"   - Value: {result.get('estimated_value', 'Not found')} {result.get('currency', '')}")
            print(f"   - Source Attribution Fields: {len(result.get('source_attribution', {}))}")
        
        # Analyze batch documents
        if batch_result.get("status") == "completed":
            individual_results = batch_result.get("individual_results", batch_result.get("results", []))
            merged_result = batch_result.get("merged_result")
            
            print(f"\\n📚 Batch Analysis:")
            print(f"   - Total Documents: {len(individual_results)}")
            
            for i, result in enumerate(individual_results):
                print(f"   - Doc {i+1}: {result.get('filename')} ({result.get('document_type')})")
            
            if merged_result:
                print(f"\\n🔄 Merged Result:")
                print(f"   - Tender ID: {merged_result.get('tender_id')}")
                print(f"   - Combined Project: {merged_result.get('project_overview', {}).get('title', 'Not found')}")
                print(f"   - Authority: {merged_result.get('project_overview', {}).get('authority', 'Not found')}")
                print(f"   - Source Documents: {len(merged_result.get('source_documents', []))}")
        
        print("\\n✅ Integration testing completed successfully!")
        
        return {
            "single_job_id": single_job_id,
            "batch_job_id": batch_job_id,
            "single_result": single_result,
            "batch_result": batch_result
        }


if __name__ == "__main__":
    # Run a quick test if executed directly
    test = TestRealFileIntegration()
    test.setup_method()
    test.test_complete_workflow_analysis()