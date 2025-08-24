"""LangExtract service for tender document processing."""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid
import os

from langextract import extract
import google.generativeai as genai
from pydantic import BaseModel, Field

from ..config import settings
from ..models.extraction import DocumentExtractionResult, TenderSourceAttribution
from ..core.logging import get_contextual_logger

logger = get_contextual_logger("langextract")


class TenderExtractionSchema(BaseModel):
    """Schema for tender document extraction."""
    
    # Project Overview
    project_title: Optional[str] = Field(None, description="Main project or tender title")
    project_description: Optional[str] = Field(None, description="Detailed project description")
    contracting_authority: Optional[str] = Field(None, description="Aanbestedende dienst/contracting authority")
    cpv_codes: List[str] = Field(default_factory=list, description="CPV classification codes")
    project_scope: Optional[str] = Field(None, description="Project scope and objectives")
    
    # Contract Details  
    contract_type: Optional[str] = Field(None, description="Type of contract (services, goods, works)")
    estimated_value: Optional[float] = Field(None, description="Estimated contract value")
    currency: Optional[str] = Field(None, description="Currency of the estimated value")
    contract_duration: Optional[str] = Field(None, description="Contract duration or period")
    payment_terms: Optional[str] = Field(None, description="Payment terms and conditions")
    
    # Critical Dates
    publication_date: Optional[datetime] = Field(None, description="Tender publication date")
    question_deadline: Optional[datetime] = Field(None, description="Deadline for questions")
    submission_deadline: Optional[datetime] = Field(None, description="Tender submission deadline")
    project_start_date: Optional[datetime] = Field(None, description="Expected project start date")
    
    # Evaluation Criteria
    knockout_criteria: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Pass/fail requirements that must be met"
    )
    selection_criteria: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Qualification requirements for bidders"
    )
    assessment_criteria: Dict[str, float] = Field(
        default_factory=dict, 
        description="Assessment criteria with weights/scores"
    )
    
    # Stakeholders
    contact_persons: List[Dict[str, str]] = Field(
        default_factory=list, 
        description="Contact persons with name, role, email, phone"
    )
    
    # Deliverables & Requirements
    deliverables: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Required deliverables and outputs"
    )
    technical_requirements: List[str] = Field(
        default_factory=list, 
        description="Technical specifications and requirements"
    )
    compliance_requirements: List[str] = Field(
        default_factory=list, 
        description="Compliance and regulatory requirements"
    )


class TenderLangExtractService:
    """Service for extracting tender information using LangExtract."""
    
    def __init__(self):
        self.api_key = settings.google_api_key
        self._initialize_api()
    
    def _initialize_api(self):
        """Initialize Gemini API."""
        try:
            if self.api_key:
                genai.configure(api_key=self.api_key)
                logger.info("Gemini API configured for LangExtract")
            else:
                logger.warning("Google API key not found, LangExtract not available")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            self.api_key = None
    
    def _get_tender_extraction_prompt(self, language: str = "nl") -> str:
        """Get the extraction prompt for tender documents."""
        prompts = {
            "nl": """
Je bent een expert in het analyseren van Nederlandse aanbestedingsdocumenten. 
Extracteer de volgende informatie uit het aanbestedingsdocument:

PROJECTOVERZICHT:
- Projecttitel en beschrijving
- Aanbestedende dienst/organisatie
- CPV codes
- Projectomvang en doelstellingen

CONTRACTDETAILS:
- Type contract (diensten, leveringen, werken)
- Geschatte waarde (met valuta)
- Contractduur
- Betalingsvoorwaarden

KRITIEKE DATUMS:
- Publicatiedatum
- Deadline voor vragen
- Inleverdeadline
- Verwachte startdatum project

GUNNINGSCRITERIA:
- Uitsluitingsgronden (knock-out criteria)
- Selectiecriteria (geschiktheidseisen)
- Gunningscriteria met wegingen/puntenverdeling

STAKEHOLDERS:
- Contactpersonen met naam, functie, email, telefoon

DELIVERABLES & EISEN:
- Te leveren producten/diensten
- Technische specificaties
- Compliance en regelgevingseisen

Voor elke geëxtraheerde informatie, geef de paginanummer en positie in het document aan.
Zorg voor nauwkeurige extractie van Nederlandse aanbestedingstermen.
""",
            "en": """
You are an expert in analyzing Dutch tender documents in English. 
Extract the following information from the tender document:

PROJECT OVERVIEW:
- Project title and description
- Contracting authority/organization
- CPV codes
- Project scope and objectives

CONTRACT DETAILS:
- Contract type (services, goods, works)
- Estimated value (with currency)
- Contract duration
- Payment terms

CRITICAL DATES:
- Publication date
- Question deadline
- Submission deadline
- Expected project start date

EVALUATION CRITERIA:
- Knockout criteria (exclusion grounds)
- Selection criteria (qualification requirements)
- Assessment criteria with weights/scoring

STAKEHOLDERS:
- Contact persons with name, role, email, phone

DELIVERABLES & REQUIREMENTS:
- Required products/services
- Technical specifications
- Compliance and regulatory requirements

For each extracted information, provide the page number and position in the document.
Ensure accurate extraction of Dutch procurement terminology.
"""
        }
        return prompts.get(language, prompts["en"])
    
    async def extract_tender_information(
        self, 
        text_with_coords: List[Dict[str, Any]], 
        filename: str,
        language: str = "nl"
    ) -> DocumentExtractionResult:
        """
        Extract tender information from text with coordinate information.
        
        Args:
            text_with_coords: List of text chunks with coordinate information
            filename: Source filename
            language: Processing language
            
        Returns:
            DocumentExtractionResult with source attribution
        """
        if not self.api_key:
            raise RuntimeError("Google API key not available for LangExtract.")
        
        logger.info(f"Starting tender extraction for {filename}")
        
        try:
            # Combine text chunks for extraction
            full_text = self._combine_text_chunks(text_with_coords)
            
            # Get extraction prompt
            prompt = self._get_tender_extraction_prompt(language)
            
            # Perform extraction using LangExtract
            extraction_result = await asyncio.to_thread(
                self._perform_extraction,
                full_text,
                prompt,
                TenderExtractionSchema
            )
            
            # Build source attribution
            source_attribution = self._build_source_attribution(
                extraction_result,
                text_with_coords,
                filename
            )
            
            # Create final result
            result = DocumentExtractionResult(
                document_id=str(uuid.uuid4()),
                filename=filename,
                document_type=self._classify_document_type(filename),
                extraction_timestamp=datetime.utcnow(),
                
                # Project overview
                project_title=extraction_result.project_title,
                project_description=extraction_result.project_description,
                contracting_authority=extraction_result.contracting_authority,
                cpv_codes=extraction_result.cpv_codes,
                project_scope=extraction_result.project_scope,
                
                # Contract details
                contract_type=extraction_result.contract_type,
                estimated_value=extraction_result.estimated_value,
                currency=extraction_result.currency,
                contract_duration=extraction_result.contract_duration,
                payment_terms=extraction_result.payment_terms,
                
                # Critical dates
                publication_date=extraction_result.publication_date,
                question_deadline=extraction_result.question_deadline,
                submission_deadline=extraction_result.submission_deadline,
                project_start_date=extraction_result.project_start_date,
                
                # Evaluation criteria
                knockout_criteria=extraction_result.knockout_criteria,
                selection_criteria=extraction_result.selection_criteria,
                assessment_criteria=extraction_result.assessment_criteria,
                
                # Stakeholders
                contact_persons=extraction_result.contact_persons,
                
                # Deliverables & requirements
                deliverables=extraction_result.deliverables,
                technical_requirements=extraction_result.technical_requirements,
                compliance_requirements=extraction_result.compliance_requirements,
                
                # Source attribution
                source_attribution=source_attribution
            )
            
            logger.info(f"Extraction completed for {filename}")
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed for {filename}: {e}")
            # Return minimal result with error information
            return DocumentExtractionResult(
                document_id=str(uuid.uuid4()),
                filename=filename,
                document_type="error",
                extraction_timestamp=datetime.utcnow(),
                source_attribution={"extraction_error": str(e)}
            )
    
    def _perform_extraction(
        self, 
        text: str, 
        prompt: str, 
        schema: type
    ) -> TenderExtractionSchema:
        """Perform the actual LangExtract extraction."""
        try:
            # Use functional LangExtract API to extract structured data
            result = extract(
                text_or_documents=text,
                prompt_description=prompt,
                model_id="gemini-1.5-pro",
                api_key=self.api_key,
                temperature=0.1,
                format_type="json"
            )
            # Convert the result to our schema format
            if hasattr(result, 'data') and result.data:
                return TenderExtractionSchema(**result.data[0])
            else:
                return TenderExtractionSchema()
        except Exception as e:
            logger.error(f"LangExtract extraction failed: {e}")
            # Return empty schema on failure
            return TenderExtractionSchema()
    
    def _combine_text_chunks(self, text_with_coords: List[Dict[str, Any]]) -> str:
        """Combine text chunks into a single text for extraction."""
        return "\n".join([
            chunk.get("text", "") 
            for chunk in text_with_coords
        ])
    
    def _build_source_attribution(
        self, 
        extraction_result: TenderExtractionSchema,
        text_with_coords: List[Dict[str, Any]],
        filename: str
    ) -> Dict[str, Any]:
        """Build source attribution for extracted fields."""
        attribution = {}
        
        # Create a mapping of text content to coordinates
        text_coord_map = {
            chunk["text"]: {
                "page": chunk.get("page", 1),
                "bbox": chunk.get("bbox", [0, 0, 0, 0]),
                "char_start": chunk.get("char_start", 0),
                "char_end": chunk.get("char_end", 0)
            }
            for chunk in text_with_coords
        }
        
        # For each extracted field, try to find source attribution
        for field_name, field_value in extraction_result.model_dump().items():
            if field_value is not None and field_value != [] and field_value != {}:
                # Find the best matching text chunk
                best_match = self._find_best_text_match(
                    str(field_value), text_coord_map
                )
                
                if best_match:
                    attribution[field_name] = TenderSourceAttribution(
                        source_filename=filename,
                        page_number=best_match["page"],
                        char_start=best_match["char_start"],
                        char_end=best_match["char_end"],
                        bbox=best_match["bbox"],
                        confidence_score=0.85,  # Default confidence
                        extraction_timestamp=datetime.utcnow()
                    ).model_dump()
        
        return attribution
    
    def _find_best_text_match(
        self, 
        extracted_text: str, 
        text_coord_map: Dict[str, Dict]
    ) -> Optional[Dict]:
        """Find the best matching text chunk for extracted content."""
        extracted_words = set(extracted_text.lower().split())
        best_score = 0
        best_match = None
        
        for text_chunk, coords in text_coord_map.items():
            chunk_words = set(text_chunk.lower().split())
            
            # Calculate overlap score
            if extracted_words and chunk_words:
                overlap = len(extracted_words.intersection(chunk_words))
                score = overlap / len(extracted_words)
                
                if score > best_score and score > 0.3:  # Minimum 30% overlap
                    best_score = score
                    best_match = coords
        
        return best_match
    
    def _classify_document_type(self, filename: str) -> str:
        """Classify document type based on filename."""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ["aankondiging", "announcement"]):
            return "tender_announcement"
        elif any(term in filename_lower for term in ["bestek", "specifications"]):
            return "technical_specifications"
        elif any(term in filename_lower for term in ["bijlage", "annex"]):
            return "annex"
        elif any(term in filename_lower for term in ["criteria", "gunning", "award"]):
            return "evaluation_criteria"
        elif any(term in filename_lower for term in ["contract", "overeenkomst"]):
            return "contract_terms"
        elif any(term in filename_lower for term in ["vraag", "question", "clarification"]):
            return "clarification"
        else:
            return "general_tender_document"


# Global service instance
langextract_service = TenderLangExtractService()