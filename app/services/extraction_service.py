"""Document extraction service with LangExtract integration."""
import os
import json
import uuid
import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import UploadFile
import aiofiles

from ..models.extraction import DocumentExtractionResult, MergedTenderResult
from ..config import settings
from ..core.logging import get_contextual_logger
from .pdf_processing_service import pdf_processing_service
from .langextract_service import langextract_service
from .cache_service import cache_service


class DocumentClassifier:
    """Service for classifying document types."""
    
    @staticmethod
    def classify_document_type(filename: str, content: bytes = None) -> str:
        """
        Classify document type based on filename and optionally content patterns.
        
        Args:
            filename: The document filename
            content: Optional document content for content-based classification
            
        Returns:
            Document type classification string
        """
        filename_lower = filename.lower()

        # Filename-based classification
        if 'bestek' in filename_lower or 'specifications' in filename_lower:
            return 'technical_specifications'
        elif 'aankondiging' in filename_lower or 'announcement' in filename_lower:
            return 'tender_announcement'
        elif 'bijlage' in filename_lower or 'annex' in filename_lower:
            return 'annex'
        elif 'criteria' in filename_lower or 'gunning' in filename_lower:
            return 'evaluation_criteria'
        elif 'contract' in filename_lower:
            return 'contract_terms'
        else:
            # Content-based classification would go here if content is provided
            return 'general_tender_document'


class DocumentMerger:
    """Service for merging multiple document extraction results."""
    
    @staticmethod
    def merge_tender_documents(
        documents: List[DocumentExtractionResult],
        extract_relationships: bool = True
    ) -> MergedTenderResult:
        """
        Intelligently merge multiple tender documents into consolidated result.
        
        Args:
            documents: List of individual document extraction results
            extract_relationships: Whether to extract document relationships
            
        Returns:
            Merged tender result
        """
        merged = MergedTenderResult(
            tender_id=str(uuid.uuid4()),
            extraction_timestamp=datetime.utcnow(),
            source_documents=[doc.filename for doc in documents],
            project_overview={},
            contract_details={},
            critical_dates={},
            evaluation_criteria={},
            deliverables_and_requirements={},
            completeness_score=0.0
        )

        # Consolidate project overview (take most complete)
        project_titles = [d.project_title for d in documents if d.project_title]
        contracting_authorities = [d.contracting_authority for d in documents if d.contracting_authority]

        merged.project_overview = {
            "title": project_titles[0] if project_titles else None,
            "contracting_authority": contracting_authorities[0] if contracting_authorities else None,
            "cpv_codes": list(set(sum([d.cpv_codes for d in documents], []))),
            "sources": DocumentMerger._identify_sources(documents, ['project_title', 'contracting_authority'])
        }

        # Merge contract details (handle conflicts)
        values = [d.estimated_value for d in documents if d.estimated_value]
        deadlines = [d.submission_deadline for d in documents if d.submission_deadline]

        merged.contract_details = {
            "estimated_value": max(values) if values else None,  # Take highest value
            "submission_deadline": min(deadlines) if deadlines else None,  # Earliest deadline
            "value_discrepancies": DocumentMerger._detect_value_conflicts(documents)
        }

        # Consolidate evaluation criteria (combine and deduplicate)
        all_knockout = sum([d.knockout_criteria for d in documents], [])
        all_selection = sum([d.selection_criteria for d in documents], [])

        # Merge assessment criteria weights
        assessment_weights = {}
        for doc in documents:
            for criterion, weight in doc.assessment_criteria.items():
                if criterion in assessment_weights:
                    # Average if multiple documents specify same criterion
                    assessment_weights[criterion] = (assessment_weights[criterion] + weight) / 2
                else:
                    assessment_weights[criterion] = weight

        merged.evaluation_criteria = {
            "knockout_criteria": DocumentMerger._deduplicate_criteria(all_knockout),
            "selection_criteria": DocumentMerger._deduplicate_criteria(all_selection),
            "assessment_criteria": assessment_weights,
            "criteria_sources": DocumentMerger._identify_criteria_sources(documents)
        }

        # Extract document relationships
        if extract_relationships:
            merged.document_relationships = DocumentMerger._extract_document_relationships(documents)

        # Calculate quality metrics
        merged.completeness_score = DocumentMerger._calculate_completeness(merged)
        merged.confidence_scores = DocumentMerger._calculate_confidence_scores(documents)

        return merged

    @staticmethod
    def _deduplicate_criteria(criteria_list: List[Dict]) -> List[Dict]:
        """Remove duplicate criteria while preserving source information."""
        seen = set()
        unique = []

        for criterion in criteria_list:
            # Create hashable representation
            criterion_key = json.dumps(criterion, sort_keys=True)

            if criterion_key not in seen:
                seen.add(criterion_key)
                unique.append(criterion)

        return unique

    @staticmethod
    def _extract_document_relationships(documents: List[DocumentExtractionResult]) -> List[Dict]:
        """Identify relationships between documents."""
        relationships = []

        for i, doc1 in enumerate(documents):
            for doc2 in documents[i+1:]:
                # Check for cross-references
                if DocumentMerger._references_document(doc1, doc2):
                    relationships.append({
                        "type": "references",
                        "source": doc1.filename,
                        "target": doc2.filename
                    })

                # Check for parent-child relationships
                if DocumentMerger._is_annex_of(doc2, doc1):
                    relationships.append({
                        "type": "annex",
                        "parent": doc1.filename,
                        "child": doc2.filename
                    })

        return relationships

    @staticmethod
    def _identify_sources(documents: List[DocumentExtractionResult], fields: List[str]) -> Dict[str, str]:
        """Identify source documents for specific fields."""
        # Placeholder implementation
        return {}

    @staticmethod
    def _detect_value_conflicts(documents: List[DocumentExtractionResult]) -> List[Dict]:
        """Detect conflicts in estimated values across documents."""
        # Placeholder implementation
        return []

    @staticmethod
    def _identify_criteria_sources(documents: List[DocumentExtractionResult]) -> Dict:
        """Identify sources of evaluation criteria."""
        # Placeholder implementation
        return {}

    @staticmethod
    def _references_document(doc1: DocumentExtractionResult, doc2: DocumentExtractionResult) -> bool:
        """Check if doc1 references doc2."""
        # Placeholder implementation - would analyze document content for references
        return False

    @staticmethod
    def _is_annex_of(child: DocumentExtractionResult, parent: DocumentExtractionResult) -> bool:
        """Check if child document is an annex of parent document."""
        # Simple check based on document type and naming
        return child.document_type == 'annex' and 'annex' in child.filename.lower()

    @staticmethod
    def _calculate_completeness(result: MergedTenderResult) -> float:
        """Calculate how complete the extraction is."""
        required_fields = [
            result.project_overview.get("title"),
            result.project_overview.get("contracting_authority"),
            result.contract_details.get("estimated_value"),
            result.contract_details.get("submission_deadline"),
            len(result.evaluation_criteria.get("assessment_criteria", {})) > 0
        ]

        return sum(1 for f in required_fields if f) / len(required_fields)

    @staticmethod
    def _calculate_confidence_scores(documents: List[DocumentExtractionResult]) -> Dict[str, float]:
        """Calculate average confidence scores by category."""
        confidence_scores = {}

        for category in ["project_overview", "contract_details", "evaluation_criteria"]:
            scores = []
            for doc in documents:
                # Get confidence from source attribution
                for field, attribution in doc.source_attribution.items():
                    if category in field:
                        scores.append(attribution.get("confidence", 0.0))

            if scores:
                confidence_scores[category] = sum(scores) / len(scores)

        return confidence_scores


class ExtractionService:
    """Main service for document extraction operations with LangExtract."""
    
    def __init__(self):
        self.classifier = DocumentClassifier()
        self.merger = DocumentMerger()
        self.logger = get_contextual_logger("extraction_service")
        self._extraction_semaphore = asyncio.Semaphore(settings.max_concurrent_extractions)
    
    async def save_uploaded_file(self, file: UploadFile, job_id: str, index: int = 0) -> tuple[str, bytes]:
        """
        Save uploaded file to temporary storage and return file path and content.
        
        Args:
            file: The uploaded file
            job_id: Job identifier for file organization  
            index: File index for batch processing
            
        Returns:
            Tuple of (file_path, file_content)
        """
        # Ensure temp directory exists
        os.makedirs(settings.temp_dir, exist_ok=True)
        
        # Generate safe filename
        safe_filename = f"{job_id}_{index}_{file.filename}"
        file_path = os.path.join(settings.temp_dir, safe_filename)
        
        # Read file content (handle closed file gracefully)
        try:
            await file.seek(0)
        except ValueError as e:
            if "I/O operation on closed file" in str(e):
                raise ValueError(f"File {file.filename} stream is closed. This usually happens when the HTTP request ends before the background task can process the file.")
            else:
                raise
        
        content = await file.read()
        
        if not content:
            raise ValueError(f"No content read from file {file.filename}. File may have been previously read or is empty.")
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        self.logger.info(f"Saved file: {file_path} ({len(content)} bytes)")
        return file_path, content
    
    async def save_file_content(self, file_content: bytes, filename: str, job_id: str, index: int = 0) -> str:
        """
        Save file content directly to temporary storage.
        
        Args:
            file_content: Raw file content bytes
            filename: Original filename
            job_id: Job identifier for file organization  
            index: File index for batch processing
            
        Returns:
            File path where content was saved
        """
        # Ensure temp directory exists
        os.makedirs(settings.temp_dir, exist_ok=True)
        
        # Generate safe filename
        safe_filename = f"{job_id}_{index}_{filename}"
        file_path = os.path.join(settings.temp_dir, safe_filename)
        
        if not file_content:
            raise ValueError(f"No content provided for file {filename}")
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        self.logger.info(f"Saved file content: {file_path} ({len(file_content)} bytes)")
        return file_path
    
    async def process_single_document(
        self, 
        file_path: str, 
        filename: str, 
        language: str,
        file_content: Optional[bytes] = None
    ) -> DocumentExtractionResult:
        """
        Process a single document with the complete extraction pipeline.
        
        Args:
            file_path: Path to document file
            filename: Original filename
            language: Processing language
            file_content: Optional file content for caching
            
        Returns:
            Document extraction result
        """
        async with self._extraction_semaphore:  # Limit concurrent extractions
            try:
                # Load file content if not provided
                if file_content is None:
                    async with aiofiles.open(file_path, 'rb') as f:
                        file_content = await f.read()
                
                # Check cache first
                if settings.enable_extraction_cache:
                    cached_result = await cache_service.get_cached_result(
                        file_content, language
                    )
                    if cached_result:
                        self.logger.info(f"Using cached result for {filename}")
                        return DocumentExtractionResult(**cached_result["result"])
                
                # Validate PDF file
                validation_result = await pdf_processing_service.validate_pdf_file(file_path)
                if not validation_result["valid"]:
                    raise ValueError(f"Invalid PDF: {validation_result['error']}")
                
                self.logger.info(f"Processing PDF: {filename} ({validation_result['page_count']} pages)")
                
                # Process PDF with coordinate extraction
                text_with_coords = await pdf_processing_service.process_pdf_with_coordinates(
                    file_path, perform_ocr=settings.perform_ocr
                )
                
                if not text_with_coords:
                    raise ValueError("No text content extracted from PDF")
                
                # Perform LangExtract extraction
                extraction_result = await langextract_service.extract_tender_information(
                    text_with_coords, filename, language
                )
                
                # Calculate quality metrics
                extraction_result = self._enhance_result_with_metrics(
                    extraction_result, text_with_coords
                )
                
                # Cache the result
                if settings.enable_extraction_cache:
                    await cache_service.cache_result(
                        file_content, language, extraction_result.model_dump()
                    )
                
                self.logger.info(f"Successfully processed {filename}")
                return extraction_result
                
            except Exception as e:
                self.logger.error(f"Error processing document {filename}: {str(e)}")
                
                # Return error result
                return DocumentExtractionResult(
                    document_id=str(uuid.uuid4()),
                    filename=filename,
                    document_type="error",
                    extraction_timestamp=datetime.utcnow(),
                    source_attribution={"extraction_error": str(e)},
                    completeness_score=0.0
                )
    
    def _enhance_result_with_metrics(
        self, 
        result: DocumentExtractionResult,
        text_chunks: List[Dict[str, Any]]
    ) -> DocumentExtractionResult:
        """Enhance extraction result with quality metrics."""
        # Calculate completeness score
        completeness_score = self._calculate_completeness_score(result)
        result.completeness_score = completeness_score
        
        # Calculate confidence scores by category
        confidence_scores = self._calculate_confidence_scores(result, text_chunks)
        result.confidence_scores = confidence_scores
        
        return result
    
    def _calculate_completeness_score(self, result: DocumentExtractionResult) -> float:
        """Calculate completeness score based on extracted fields."""
        total_fields = 0
        filled_fields = 0
        
        # Core fields with higher weight
        core_fields = [
            result.project_title,
            result.contracting_authority,
            result.estimated_value,
            result.submission_deadline
        ]
        
        for field in core_fields:
            total_fields += 2  # Higher weight
            if field is not None:
                filled_fields += 2
        
        # Secondary fields
        secondary_fields = [
            result.project_description,
            result.contract_type,
            result.currency,
            result.contract_duration,
            result.publication_date,
            result.question_deadline,
            result.project_start_date
        ]
        
        for field in secondary_fields:
            total_fields += 1
            if field is not None:
                filled_fields += 1
        
        # List fields
        if result.cpv_codes:
            filled_fields += 1
        total_fields += 1
        
        if result.contact_persons:
            filled_fields += 1
        total_fields += 1
        
        if result.assessment_criteria:
            filled_fields += 1
        total_fields += 1
        
        return filled_fields / total_fields if total_fields > 0 else 0.0
    
    def _calculate_confidence_scores(
        self, 
        result: DocumentExtractionResult,
        text_chunks: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate confidence scores by category."""
        # Average OCR confidence if available
        ocr_confidences = [
            chunk.get("confidence", 1.0) 
            for chunk in text_chunks 
            if chunk.get("extraction_method") == "tesseract_ocr"
        ]
        
        base_confidence = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0.9
        
        confidence_scores = {}
        
        # Project overview confidence
        project_fields = [result.project_title, result.project_description, result.contracting_authority]
        project_filled = sum(1 for field in project_fields if field)
        confidence_scores["project_overview"] = min(base_confidence * (project_filled / len(project_fields)), 1.0)
        
        # Contract details confidence
        contract_fields = [result.estimated_value, result.contract_type, result.currency]
        contract_filled = sum(1 for field in contract_fields if field)
        confidence_scores["contract_details"] = min(base_confidence * (contract_filled / len(contract_fields)), 1.0)
        
        # Dates confidence
        date_fields = [result.publication_date, result.submission_deadline, result.question_deadline]
        date_filled = sum(1 for field in date_fields if field)
        confidence_scores["critical_dates"] = min(base_confidence * (date_filled / len(date_fields)), 1.0)
        
        # Criteria confidence
        criteria_filled = len(result.assessment_criteria) + len(result.knockout_criteria)
        confidence_scores["evaluation_criteria"] = min(base_confidence * min(criteria_filled / 3, 1), 1.0)
        
        return confidence_scores
    
    def cleanup_temp_file(self, file_path: str) -> None:
        """
        Clean up temporary file.
        
        Args:
            file_path: Path to file to clean up
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            self.logger.warning(f"Could not clean up file {file_path}: {str(e)}")


# Global extraction service instance
extraction_service = ExtractionService()