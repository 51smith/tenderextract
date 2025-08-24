"""Tests for PDF processing service."""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import numpy as np

from app.services.pdf_processing_service import PDFProcessingService


class TestPDFProcessingService:
    """Test cases for PDFProcessingService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        return PDFProcessingService()
    
    @pytest.fixture
    def mock_pdf_file(self):
        """Create a mock PDF file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            # Write minimal PDF content
            f.write(b'%PDF-1.4\n%%EOF')
            return f.name
    
    def test_word_grouping(self, service):
        """Test grouping words into chunks."""
        mock_words = [
            {"text": "Aanbesteding", "top": 100, "x0": 50, "x1": 150},
            {"text": "IT", "top": 102, "x0": 160, "x1": 180},
            {"text": "Project", "top": 101, "x0": 190, "x1": 240},
            {"text": "Next", "top": 130, "x0": 50, "x1": 90},  # New line
            {"text": "Line", "top": 132, "x0": 100, "x1": 130}
        ]
        
        chunks = service._group_words_into_chunks(mock_words, page_num=1)
        
        # Should group into 2 chunks based on y-position
        assert len(chunks) == 2
        assert chunks[0]["text"] == "Aanbesteding IT Project"
        assert chunks[1]["text"] == "Next Line"
        assert chunks[0]["page"] == 1
        assert chunks[1]["page"] == 1
    
    def test_chunk_finalization(self, service):
        """Test finalizing text chunks."""
        chunk_data = {
            "words": ["Aanbesteding", "IT", "Project"],
            "y_positions": [100, 102, 101],
            "x_start": 50,
            "x_end": 240
        }
        
        chunk = service._finalize_chunk(chunk_data, page_num=1)
        
        assert chunk["text"] == "Aanbesteding IT Project"
        assert chunk["page"] == 1
        assert chunk["bbox"] == [50, 100, 240, 102]
        assert chunk["extraction_method"] == "pdfplumber"
        assert chunk["chunk_type"] == "paragraph"
    
    def test_table_to_text(self, service):
        """Test converting table to text."""
        mock_table = [
            ["Header 1", "Header 2", "Header 3"],
            ["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3"],
            ["Row 2 Col 1", "", "Row 2 Col 3"]  # Empty cell
        ]
        
        text = service._table_to_text(mock_table)
        lines = text.split('\n')
        
        assert len(lines) == 3
        assert "Header 1 | Header 2 | Header 3" in text
        assert "Row 1 Col 1 | Row 1 Col 2 | Row 1 Col 3" in text
        assert "Row 2 Col 1 |  | Row 2 Col 3" in text
    
    def test_image_enhancement(self, service):
        """Test image enhancement for OCR."""
        # Create a mock PIL image
        image_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        image = Image.fromarray(image_array)
        
        enhanced = service._enhance_image_for_ocr(image)
        
        # Should return a PIL Image
        assert isinstance(enhanced, Image.Image)
        # Should be converted to grayscale
        assert enhanced.mode in ['L', 'P']
    
    def test_ocr_chunk_finalization(self, service):
        """Test finalizing OCR chunks."""
        chunk_data = {
            "words": ["Test", "OCR", "Text"],
            "confidences": [85, 90, 88],
            "bbox": [10, 20, 150, 40]
        }
        
        chunk = service._finalize_ocr_chunk(chunk_data, page_num=1)
        
        assert chunk["text"] == "Test OCR Text"
        assert chunk["page"] == 1
        assert chunk["bbox"] == [10, 20, 150, 40]
        assert chunk["extraction_method"] == "tesseract_ocr"
        assert chunk["chunk_type"] == "ocr_line"
        assert 0.85 <= chunk["confidence"] <= 0.95  # Average of confidences
    
    def test_text_cleaning(self, service):
        """Test text cleaning functionality."""
        dirty_text = "   Aanbesteding    \n\nIT   Project   \t Pagina 1  "
        clean_text = service._clean_text(dirty_text)
        
        assert clean_text == "Aanbesteding IT Project"
        
        # Test Dutch OCR error correction
        ocr_errors = "aan be steding in plaats van"
        cleaned = service._clean_text(ocr_errors)
        assert "aanbesteding" in cleaned
        assert "in plaats van" in cleaned
    
    @patch('app.services.pdf_processing_service.pdfplumber')
    @pytest.mark.asyncio
    async def test_pdf_validation_valid(self, mock_pdfplumber, service, mock_pdf_file):
        """Test PDF validation with valid file."""
        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(), MagicMock()]  # 2 pages
        mock_pdf.metadata = {"encrypted": False}
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        
        # Mock magic for file type detection
        with patch('app.services.pdf_processing_service.magic') as mock_magic:
            mock_magic.from_file.return_value = "application/pdf"
            
            result = await service.validate_pdf_file(mock_pdf_file)
            
            assert result["valid"] is True
            assert result["page_count"] == 2
            assert result["mime_type"] == "application/pdf"
    
    @patch('app.services.pdf_processing_service.magic')
    @pytest.mark.asyncio
    async def test_pdf_validation_invalid_type(self, mock_magic, service, mock_pdf_file):
        """Test PDF validation with invalid file type."""
        mock_magic.from_file.return_value = "text/plain"
        
        result = await service.validate_pdf_file(mock_pdf_file)
        
        assert result["valid"] is False
        assert "Invalid file type" in result["error"]
    
    def test_merge_extraction_results(self, service):
        """Test merging text extraction and OCR results."""
        text_chunks = [
            {"page": 1, "text": "Rich text content", "extraction_method": "pdfplumber"}
        ]
        
        ocr_chunks = [
            {"page": 1, "text": "OCR text", "extraction_method": "tesseract_ocr"},
            {"page": 2, "text": "Page 2 OCR content", "extraction_method": "tesseract_ocr"}
        ]
        
        merged = service._merge_extraction_results(text_chunks, ocr_chunks)
        
        # Should prefer text extraction for page 1 (has rich content)
        # Should use OCR for page 2 (no text extraction)
        page_1_results = [c for c in merged if c["page"] == 1]
        page_2_results = [c for c in merged if c["page"] == 2]
        
        assert len(page_1_results) == 1
        assert page_1_results[0]["extraction_method"] == "pdfplumber"
        
        assert len(page_2_results) == 1
        assert page_2_results[0]["extraction_method"] == "tesseract_ocr"
    
    def test_process_ocr_data(self, service):
        """Test processing Tesseract OCR data."""
        mock_ocr_data = {
            'text': ['', 'Aanbesteding', 'IT', '', 'Project', ''],
            'conf': [0, 85, 90, 0, 88, 0],
            'left': [0, 50, 150, 0, 250, 0],
            'top': [0, 100, 102, 0, 130, 0],
            'width': [0, 80, 20, 0, 60, 0],
            'height': [0, 20, 18, 0, 22, 0]
        }
        
        chunks = service._process_ocr_data(mock_ocr_data, page_num=1)
        
        # Should group words by similar y-coordinates
        assert len(chunks) >= 1
        # First chunk should contain words from similar y-positions
        first_chunk = chunks[0]
        assert "Aanbesteding" in first_chunk["text"]
        assert first_chunk["page"] == 1
    
    def cleanup(self):
        """Clean up test files."""
        # This would be called after tests to clean up temp files
        pass