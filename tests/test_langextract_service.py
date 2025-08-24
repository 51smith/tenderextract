"""Tests for LangExtract service."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.services.langextract_service import TenderLangExtractService, TenderExtractionSchema


class TestTenderLangExtractService:
    """Test cases for TenderLangExtractService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        with patch('app.services.langextract_service.settings.google_api_key', 'test-api-key'):
            return TenderLangExtractService()
    
    @pytest.fixture
    def mock_text_chunks(self):
        """Mock text chunks with coordinates."""
        return [
            {
                "text": "Aanbesteding IT Infrastructure Modernization",
                "page": 1,
                "bbox": [100, 200, 400, 220],
                "char_start": 0,
                "char_end": 42
            },
            {
                "text": "Aanbestedende dienst: Ministry of Digital Affairs",
                "page": 1,
                "bbox": [100, 250, 500, 270],
                "char_start": 43,
                "char_end": 92
            },
            {
                "text": "Geschatte waarde: €500000.0 EUR",
                "page": 2,
                "bbox": [100, 300, 300, 320],
                "char_start": 93,
                "char_end": 119
            }
        ]
    
    def test_classification(self, service):
        """Test document type classification."""
        test_cases = [
            ("aankondiging_tender.pdf", "tender_announcement"),
            ("bestek_specifications.pdf", "technical_specifications"),
            ("bijlage_annex.pdf", "annex"),
            ("gunning_criteria.pdf", "evaluation_criteria"),
            ("contract_agreement.pdf", "contract_terms"),
            ("random_document.pdf", "general_tender_document")
        ]
        
        for filename, expected_type in test_cases:
            result = service._classify_document_type(filename)
            assert result == expected_type
    
    def test_text_combination(self, service, mock_text_chunks):
        """Test combining text chunks."""
        combined = service._combine_text_chunks(mock_text_chunks)
        expected = "Aanbesteding IT Infrastructure Modernization\nAanbestedende dienst: Ministry of Digital Affairs\nGeschatte waarde: €500000.0 EUR"
        assert combined == expected
    
    def test_prompt_generation(self, service):
        """Test extraction prompt generation."""
        nl_prompt = service._get_tender_extraction_prompt("nl")
        en_prompt = service._get_tender_extraction_prompt("en")
        
        assert "aanbestedingsdocument" in nl_prompt.lower()
        assert "tender document" in en_prompt.lower()
        assert "projecttitel" in nl_prompt.lower()
        assert "project title" in en_prompt.lower()
    
    def test_text_matching(self, service):
        """Test finding best text match for extracted content."""
        text_coord_map = {
            "Ministry of Digital Affairs": {
                "page": 1,
                "char_start": 43,
                "char_end": 92,
                "bbox": [100, 250, 500, 270]
            },
            "€500.000": {
                "page": 2,
                "char_start": 93,
                "char_end": 119,
                "bbox": [100, 300, 300, 320]
            }
        }
        
        # Test exact match
        match = service._find_best_text_match("Ministry of Digital Affairs", text_coord_map)
        assert match is not None
        assert match["page"] == 1
        
        # Test partial match
        match = service._find_best_text_match("Ministry Digital", text_coord_map)
        assert match is not None
        assert match["page"] == 1
        
        # Test no match
        match = service._find_best_text_match("Random text", text_coord_map)
        assert match is None
    
    @pytest.mark.asyncio
    async def test_source_attribution_building(self, service, mock_text_chunks):
        """Test building source attribution."""
        # Mock extraction result
        extraction_result = TenderExtractionSchema(
            project_title="IT Infrastructure Modernization",
            contracting_authority="Ministry of Digital Affairs",
            estimated_value=500000.0
        )
        
        attribution = service._build_source_attribution(
            extraction_result, mock_text_chunks, "test.pdf"
        )
        
        # Check that attribution was created for fields with values
        assert "project_title" in attribution
        assert "contracting_authority" in attribution
        # Note: estimated_value might not match due to format differences
        
        # Check attribution structure
        title_attr = attribution["project_title"]
        assert title_attr["source_filename"] == "test.pdf"
        assert title_attr["confidence_score"] == 0.85
        assert "extraction_timestamp" in title_attr
    
    @pytest.mark.asyncio
    async def test_extraction_with_mock(self, service, mock_text_chunks):
        """Test extraction with mocked LangExtract."""
        # Mock the extraction result
        mock_result = TenderExtractionSchema(
            project_title="IT Infrastructure Modernization",
            contracting_authority="Ministry of Digital Affairs",
            estimated_value=500000.0,
            currency="EUR"
        )
        
        # Mock the perform_extraction method
        service._perform_extraction = Mock(return_value=mock_result)
        
        result = await service.extract_tender_information(
            mock_text_chunks, "test.pdf", "nl"
        )
        
        # Verify result structure
        assert result.filename == "test.pdf"
        assert result.project_title == "IT Infrastructure Modernization"
        assert result.contracting_authority == "Ministry of Digital Affairs"
        assert result.estimated_value == 500000.0
        assert result.currency == "EUR"
        assert result.source_attribution is not None
    
    @pytest.mark.asyncio
    async def test_extraction_error_handling(self, mock_text_chunks):
        """Test error handling in extraction."""
        # Create service without API key
        with patch('app.services.langextract_service.settings.google_api_key', None):
            service = TenderLangExtractService()
            
            with pytest.raises(RuntimeError, match="Google API key not available"):
                await service.extract_tender_information(
                    mock_text_chunks, "test.pdf", "nl"
                )
    
    @pytest.mark.asyncio
    async def test_extraction_with_exception(self, service, mock_text_chunks):
        """Test extraction when LangExtract throws exception."""
        # Mock _perform_extraction to raise exception
        service._perform_extraction = Mock(side_effect=Exception("Extraction failed"))
        
        result = await service.extract_tender_information(
            mock_text_chunks, "test.pdf", "nl"
        )
        
        # Should return error result
        assert result.filename == "test.pdf"
        assert result.document_type == "error"
        assert "Extraction failed" in str(result.source_attribution.get("extraction_error", ""))
    
    def test_schema_validation(self):
        """Test TenderExtractionSchema validation."""
        # Valid schema
        schema = TenderExtractionSchema(
            project_title="Test Project",
            estimated_value=100000.0,
            currency="EUR",
            cpv_codes=["12345678-9"],
            assessment_criteria={"price": 0.4, "quality": 0.6}
        )
        
        assert schema.project_title == "Test Project"
        assert schema.estimated_value == 100000.0
        assert len(schema.cpv_codes) == 1
        assert schema.assessment_criteria["price"] == 0.4
        
        # Test defaults
        empty_schema = TenderExtractionSchema()
        assert empty_schema.cpv_codes == []
        assert empty_schema.knockout_criteria == []
        assert empty_schema.contact_persons == []