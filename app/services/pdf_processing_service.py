"""PDF processing service with coordinate tracking and OCR support."""
import asyncio
import io
import logging
import os
import tempfile
from typing import Dict, List, Any, Optional, Tuple
import uuid

import pdfplumber
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import cv2
import numpy as np
import magic
import aiofiles

from ..config import settings
from ..core.logging import get_contextual_logger

logger = get_contextual_logger("pdf_processor")


class PDFProcessingService:
    """Service for processing PDF documents with coordinate tracking."""
    
    def __init__(self):
        self.temp_dir = settings.temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def process_pdf_with_coordinates(
        self, 
        file_path: str, 
        perform_ocr: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process PDF and extract text with coordinate information.
        
        Args:
            file_path: Path to the PDF file
            perform_ocr: Whether to perform OCR on scanned pages
            
        Returns:
            List of text chunks with coordinate information
        """
        logger.info(f"Processing PDF: {file_path}")
        
        try:
            # First, try to extract text directly from PDF
            text_with_coords = await self._extract_text_with_coordinates(file_path)
            
            # If no text found or OCR requested, perform OCR
            if not text_with_coords or perform_ocr:
                logger.info("Performing OCR on PDF")
                ocr_results = await self._perform_ocr_extraction(file_path)
                
                # Combine or replace with OCR results
                if not text_with_coords:
                    text_with_coords = ocr_results
                else:
                    # Merge OCR results for pages with little text
                    text_with_coords = self._merge_extraction_results(
                        text_with_coords, ocr_results
                    )
            
            # Post-process and clean text
            text_with_coords = self._clean_and_enhance_text(text_with_coords)
            
            logger.info(f"Extracted {len(text_with_coords)} text chunks from PDF")
            return text_with_coords
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise
    
    async def _extract_text_with_coordinates(
        self, 
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Extract text with coordinates using pdfplumber."""
        text_chunks = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract words with positions
                    words = page.extract_words(
                        x_tolerance=3,
                        y_tolerance=3,
                        keep_blank_chars=True,
                        use_text_flow=True
                    )
                    
                    if not words:
                        continue
                    
                    # Group words into lines and paragraphs
                    grouped_text = self._group_words_into_chunks(words, page_num)
                    text_chunks.extend(grouped_text)
                    
                    # Extract tables if present
                    tables = page.extract_tables()
                    if tables:
                        table_chunks = self._process_tables(tables, page_num)
                        text_chunks.extend(table_chunks)
            
            return text_chunks
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return []
    
    def _group_words_into_chunks(
        self, 
        words: List[Dict], 
        page_num: int
    ) -> List[Dict[str, Any]]:
        """Group words into meaningful text chunks."""
        chunks = []
        current_chunk = {
            "words": [],
            "y_positions": [],
            "x_start": float('inf'),
            "x_end": 0,
        }
        
        for word in words:
            # Start new chunk if significant vertical gap
            if (current_chunk["words"] and 
                abs(word["top"] - np.mean(current_chunk["y_positions"])) > 10):
                
                if current_chunk["words"]:
                    chunk = self._finalize_chunk(current_chunk, page_num)
                    chunks.append(chunk)
                
                current_chunk = {
                    "words": [],
                    "y_positions": [],
                    "x_start": float('inf'),
                    "x_end": 0,
                }
            
            # Add word to current chunk
            current_chunk["words"].append(word["text"])
            current_chunk["y_positions"].append(word["top"])
            current_chunk["x_start"] = min(current_chunk["x_start"], word["x0"])
            current_chunk["x_end"] = max(current_chunk["x_end"], word["x1"])
        
        # Finalize last chunk
        if current_chunk["words"]:
            chunk = self._finalize_chunk(current_chunk, page_num)
            chunks.append(chunk)
        
        return chunks
    
    def _finalize_chunk(self, chunk_data: Dict, page_num: int) -> Dict[str, Any]:
        """Finalize a text chunk with proper formatting."""
        text = " ".join(chunk_data["words"]).strip()
        
        return {
            "text": text,
            "page": page_num,
            "bbox": [
                chunk_data["x_start"],
                min(chunk_data["y_positions"]),
                chunk_data["x_end"],
                max(chunk_data["y_positions"])
            ],
            "char_start": 0,  # Will be calculated later
            "char_end": len(text),
            "extraction_method": "pdfplumber",
            "chunk_type": "paragraph"
        }
    
    def _process_tables(
        self, 
        tables: List[List[List[str]]], 
        page_num: int
    ) -> List[Dict[str, Any]]:
        """Process extracted tables into text chunks."""
        table_chunks = []
        
        for i, table in enumerate(tables):
            # Convert table to text
            table_text = self._table_to_text(table)
            
            if table_text.strip():
                table_chunks.append({
                    "text": table_text,
                    "page": page_num,
                    "bbox": [0, 0, 0, 0],  # Table bbox would need more complex calculation
                    "char_start": 0,
                    "char_end": len(table_text),
                    "extraction_method": "pdfplumber",
                    "chunk_type": "table"
                })
        
        return table_chunks
    
    def _table_to_text(self, table: List[List[str]]) -> str:
        """Convert table data to readable text."""
        if not table:
            return ""
        
        # Create formatted table text
        lines = []
        for row in table:
            if row and any(cell for cell in row if cell):
                clean_row = [cell.strip() if cell else "" for cell in row]
                lines.append(" | ".join(clean_row))
        
        return "\n".join(lines)
    
    async def _perform_ocr_extraction(
        self, 
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Perform OCR extraction using Tesseract."""
        ocr_chunks = []
        
        try:
            # Convert PDF to images
            images = await asyncio.to_thread(
                convert_from_path, file_path, dpi=300
            )
            
            for page_num, image in enumerate(images, 1):
                logger.info(f"Performing OCR on page {page_num}")
                
                # Enhance image for better OCR
                enhanced_image = self._enhance_image_for_ocr(image)
                
                # Perform OCR with bbox information
                ocr_data = pytesseract.image_to_data(
                    enhanced_image, 
                    output_type=pytesseract.Output.DICT,
                    lang='nld+eng',  # Dutch and English
                    config='--psm 6'  # Uniform block of text
                )
                
                # Process OCR results
                page_chunks = self._process_ocr_data(ocr_data, page_num)
                ocr_chunks.extend(page_chunks)
        
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
        
        return ocr_chunks
    
    def _enhance_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Enhance image quality for better OCR results."""
        # Convert PIL image to OpenCV format
        img_array = np.array(image)
        
        # Convert to grayscale
        if len(img_array.shape) == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply image enhancements
        # 1. Noise removal
        img_array = cv2.medianBlur(img_array, 3)
        
        # 2. Contrast enhancement
        img_array = cv2.convertScaleAbs(img_array, alpha=1.2, beta=10)
        
        # 3. Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
        
        # Convert back to PIL Image
        return Image.fromarray(img_array)
    
    def _process_ocr_data(
        self, 
        ocr_data: Dict, 
        page_num: int
    ) -> List[Dict[str, Any]]:
        """Process Tesseract OCR data into text chunks."""
        chunks = []
        current_chunk = {
            "words": [],
            "confidences": [],
            "bbox": [float('inf'), float('inf'), 0, 0]
        }
        
        for i, text in enumerate(ocr_data['text']):
            if int(ocr_data['conf'][i]) > 30 and text.strip():  # Confidence threshold
                word = text.strip()
                conf = int(ocr_data['conf'][i])
                
                x, y, w, h = (
                    ocr_data['left'][i], 
                    ocr_data['top'][i],
                    ocr_data['width'][i], 
                    ocr_data['height'][i]
                )
                
                # Group words by line (similar y-coordinate)
                if (current_chunk["words"] and 
                    abs(y - current_chunk["bbox"][1]) > 20):
                    
                    # Finalize current chunk
                    if current_chunk["words"]:
                        chunk = self._finalize_ocr_chunk(current_chunk, page_num)
                        chunks.append(chunk)
                    
                    # Start new chunk
                    current_chunk = {
                        "words": [],
                        "confidences": [],
                        "bbox": [float('inf'), float('inf'), 0, 0]
                    }
                
                # Add word to current chunk
                current_chunk["words"].append(word)
                current_chunk["confidences"].append(conf)
                current_chunk["bbox"][0] = min(current_chunk["bbox"][0], x)
                current_chunk["bbox"][1] = min(current_chunk["bbox"][1], y)
                current_chunk["bbox"][2] = max(current_chunk["bbox"][2], x + w)
                current_chunk["bbox"][3] = max(current_chunk["bbox"][3], y + h)
        
        # Finalize last chunk
        if current_chunk["words"]:
            chunk = self._finalize_ocr_chunk(current_chunk, page_num)
            chunks.append(chunk)
        
        return chunks
    
    def _finalize_ocr_chunk(
        self, 
        chunk_data: Dict, 
        page_num: int
    ) -> Dict[str, Any]:
        """Finalize an OCR text chunk."""
        text = " ".join(chunk_data["words"]).strip()
        avg_confidence = np.mean(chunk_data["confidences"]) / 100.0
        
        return {
            "text": text,
            "page": page_num,
            "bbox": chunk_data["bbox"],
            "char_start": 0,
            "char_end": len(text),
            "extraction_method": "tesseract_ocr",
            "chunk_type": "ocr_line",
            "confidence": avg_confidence
        }
    
    def _merge_extraction_results(
        self, 
        text_chunks: List[Dict[str, Any]], 
        ocr_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge text extraction and OCR results intelligently."""
        # Group by page
        text_by_page = {}
        ocr_by_page = {}
        
        for chunk in text_chunks:
            page = chunk["page"]
            if page not in text_by_page:
                text_by_page[page] = []
            text_by_page[page].append(chunk)
        
        for chunk in ocr_chunks:
            page = chunk["page"]
            if page not in ocr_by_page:
                ocr_by_page[page] = []
            ocr_by_page[page].append(chunk)
        
        merged_results = []
        
        # For each page, decide whether to use text extraction or OCR
        all_pages = set(text_by_page.keys()) | set(ocr_by_page.keys())
        
        for page in sorted(all_pages):
            text_chunks_page = text_by_page.get(page, [])
            ocr_chunks_page = ocr_by_page.get(page, [])
            
            # Calculate text density
            text_char_count = sum(len(chunk["text"]) for chunk in text_chunks_page)
            ocr_char_count = sum(len(chunk["text"]) for chunk in ocr_chunks_page)
            
            # Use OCR if text extraction yielded very little content
            if text_char_count < 100 and ocr_char_count > text_char_count:
                merged_results.extend(ocr_chunks_page)
                logger.info(f"Using OCR results for page {page}")
            else:
                merged_results.extend(text_chunks_page)
                logger.info(f"Using text extraction results for page {page}")
        
        return merged_results
    
    def _clean_and_enhance_text(
        self, 
        text_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Clean and enhance extracted text."""
        cleaned_chunks = []
        char_offset = 0
        
        for chunk in text_chunks:
            # Clean text
            text = chunk["text"]
            text = self._clean_text(text)
            
            if len(text.strip()) < 3:  # Skip very short chunks
                continue
            
            # Update character positions
            chunk["text"] = text
            chunk["char_start"] = char_offset
            chunk["char_end"] = char_offset + len(text)
            char_offset += len(text) + 1  # +1 for space between chunks
            
            cleaned_chunks.append(chunk)
        
        return cleaned_chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers patterns
        text = re.sub(r'\bPagina?\s*\d*\b', '', text, flags=re.IGNORECASE)  # Remove Pagina with optional number
        text = re.sub(r'\b\d+\s*$', '', text)  # Remove trailing numbers
        
        # Clean up common OCR errors for Dutch text
        text = re.sub(r'\b[Ii]n\s+plaats\s+van\b', 'in plaats van', text)
        text = re.sub(r'\baan\s+be\s*steding\b', 'aanbesteding', text, flags=re.IGNORECASE)
        
        # Remove artifacts
        text = re.sub(r'[^\w\s.,;:!?()-€$%&@#]', '', text)
        
        # Final whitespace cleanup
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    async def validate_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """Validate PDF file and return metadata."""
        try:
            # Check file type
            mime_type = magic.from_file(file_path, mime=True)
            if not mime_type.startswith('application/pdf'):
                return {
                    "valid": False,
                    "error": f"Invalid file type: {mime_type}"
                }
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > settings.max_file_size:
                return {
                    "valid": False,
                    "error": f"File too large: {file_size} bytes"
                }
            
            # Try to open and get basic info
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                
                # Check if PDF is encrypted
                if pdf.metadata and pdf.metadata.get('encrypted'):
                    return {
                        "valid": False,
                        "error": "PDF is encrypted"
                    }
            
            return {
                "valid": True,
                "page_count": page_count,
                "file_size": file_size,
                "mime_type": mime_type
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"PDF validation failed: {str(e)}"
            }


# Global service instance
pdf_processing_service = PDFProcessingService()