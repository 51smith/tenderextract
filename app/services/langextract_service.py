"""LangExtract service for tender document processing."""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid
import os

from langextract import extract
from langextract.data import ExampleData
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
            from langextract.data import Extraction, CharInterval
            
            # Create comprehensive examples covering all TenderExtractionSchema fields
            examples = [
                ExampleData(
                    text="""Tender voor IT Infrastructure Modernization Project

Aanbestedende dienst: Gemeente Amsterdam
Projectomschrijving: Complete modernisering van de IT-infrastructuur voor betere digitale dienstverlening aan inwoners.
Projectomvang: Het project behelst de vervanging van legacy systemen en implementatie van cloud-native oplossingen.

Contractdetails:
- Type contract: Dienstverlening
- Geschatte waarde: €750.000 EUR  
- Contractduur: 24 maanden
- Betalingsvoorwaarden: Maandelijkse termijnen na goedkeuring

Belangrijke datums:
- Publicatiedatum: 10 januari 2024
- Deadline voor vragen: 5 februari 2024
- Inleverdeadline: 15 februari 2024 om 17:00
- Verwachte startdatum: 1 maart 2024

CPV classificatie: 48000000-8 (Software package and information systems)

Uitsluitingscriteria:
- Geen faillissement in afgelopen 3 jaar
- Minimaal 5 jaar ervaring met IT-infrastructuur

Selectiecriteria:
- ISO 27001 certificering vereist  
- Referenties van minimaal 3 vergelijkbare projecten

Gunningscriteria:
- Prijs: 40%
- Technische kwaliteit: 35%
- Duurzaamheid: 25%

Contactpersonen:
- Jan Janssen, Projectmanager, j.janssen@amsterdam.nl, 020-1234567
- Maria de Vries, Inkoop specialist, m.devries@amsterdam.nl

Deliverables:
- Technisch ontwerp en architectuur
- Implementatie en migratie van systemen
- Gebruikerstraining en documentatie

Technische eisen:
- Cloud-native architectuur vereist
- API-first approach
- 99.9% uptime garantie

Compliance eisen:
- AVG/GDPR compliant
- NEN 7510 certificering
- BIO (Baseline Informatiebeveiliging Overheid)""",
                    extractions=[
                        Extraction(extraction_class="project_title", extraction_text="IT Infrastructure Modernization Project", char_interval=CharInterval(start_pos=11, end_pos=50)),
                        Extraction(extraction_class="contracting_authority", extraction_text="Gemeente Amsterdam", char_interval=CharInterval(start_pos=72, end_pos=90)),
                        Extraction(extraction_class="project_description", extraction_text="Complete modernisering van de IT-infrastructuur voor betere digitale dienstverlening aan inwoners.", char_interval=CharInterval(start_pos=108, end_pos=207)),
                        Extraction(extraction_class="project_scope", extraction_text="Het project behelst de vervanging van legacy systemen en implementatie van cloud-native oplossingen.", char_interval=CharInterval(start_pos=224, end_pos=325)),
                        Extraction(extraction_class="contract_type", extraction_text="Dienstverlening", char_interval=CharInterval(start_pos=358, end_pos=373)),
                        Extraction(extraction_class="estimated_value", extraction_text="750000", char_interval=CharInterval(start_pos=395, end_pos=401)),
                        Extraction(extraction_class="currency", extraction_text="EUR", char_interval=CharInterval(start_pos=403, end_pos=406)),
                        Extraction(extraction_class="contract_duration", extraction_text="24 maanden", char_interval=CharInterval(start_pos=424, end_pos=434)),
                        Extraction(extraction_class="payment_terms", extraction_text="Maandelijkse termijnen na goedkeuring", char_interval=CharInterval(start_pos=457, end_pos=495)),
                        Extraction(extraction_class="publication_date", extraction_text="10 januari 2024", char_interval=CharInterval(start_pos=538, end_pos=554)),
                        Extraction(extraction_class="question_deadline", extraction_text="5 februari 2024", char_interval=CharInterval(start_pos=577, end_pos=593)),
                        Extraction(extraction_class="submission_deadline", extraction_text="15 februari 2024 om 17:00", char_interval=CharInterval(start_pos=612, end_pos=638)),
                        Extraction(extraction_class="project_start_date", extraction_text="1 maart 2024", char_interval=CharInterval(start_pos=660, end_pos=672)),
                        Extraction(extraction_class="cpv_codes", extraction_text="48000000-8", char_interval=CharInterval(start_pos=691, end_pos=701)),
                        Extraction(extraction_class="knockout_criteria", extraction_text="Geen faillissement in afgelopen 3 jaar", char_interval=CharInterval(start_pos=767, end_pos=806)),
                        Extraction(extraction_class="knockout_criteria", extraction_text="Minimaal 5 jaar ervaring met IT-infrastructuur", char_interval=CharInterval(start_pos=809, end_pos=856)),
                        Extraction(extraction_class="selection_criteria", extraction_text="ISO 27001 certificering vereist", char_interval=CharInterval(start_pos=876, end_pos=908)),
                        Extraction(extraction_class="selection_criteria", extraction_text="Referenties van minimaal 3 vergelijkbare projecten", char_interval=CharInterval(start_pos=911, end_pos=962)),
                        Extraction(extraction_class="assessment_criteria", extraction_text="Prijs: 40%", char_interval=CharInterval(start_pos=980, end_pos=990)),
                        Extraction(extraction_class="assessment_criteria", extraction_text="Technische kwaliteit: 35%", char_interval=CharInterval(start_pos=993, end_pos=1019)),
                        Extraction(extraction_class="assessment_criteria", extraction_text="Duurzaamheid: 25%", char_interval=CharInterval(start_pos=1022, end_pos=1040)),
                        Extraction(extraction_class="contact_persons", extraction_text="Jan Janssen, Projectmanager, j.janssen@amsterdam.nl, 020-1234567", char_interval=CharInterval(start_pos=1060, end_pos=1126)),
                        Extraction(extraction_class="contact_persons", extraction_text="Maria de Vries, Inkoop specialist, m.devries@amsterdam.nl", char_interval=CharInterval(start_pos=1129, end_pos=1187)),
                        Extraction(extraction_class="deliverables", extraction_text="Technisch ontwerp en architectuur", char_interval=CharInterval(start_pos=1203, end_pos=1237)),
                        Extraction(extraction_class="deliverables", extraction_text="Implementatie en migratie van systemen", char_interval=CharInterval(start_pos=1240, end_pos=1279)),
                        Extraction(extraction_class="deliverables", extraction_text="Gebruikerstraining en documentatie", char_interval=CharInterval(start_pos=1282, end_pos=1317)),
                        Extraction(extraction_class="technical_requirements", extraction_text="Cloud-native architectuur vereist", char_interval=CharInterval(start_pos=1336, end_pos=1370)),
                        Extraction(extraction_class="technical_requirements", extraction_text="API-first approach", char_interval=CharInterval(start_pos=1373, end_pos=1391)),
                        Extraction(extraction_class="technical_requirements", extraction_text="99.9% uptime garantie", char_interval=CharInterval(start_pos=1394, end_pos=1415)),
                        Extraction(extraction_class="compliance_requirements", extraction_text="AVG/GDPR compliant", char_interval=CharInterval(start_pos=1435, end_pos=1453)),
                        Extraction(extraction_class="compliance_requirements", extraction_text="NEN 7510 certificering", char_interval=CharInterval(start_pos=1456, end_pos=1479)),
                        Extraction(extraction_class="compliance_requirements", extraction_text="BIO (Baseline Informatiebeveiliging Overheid)", char_interval=CharInterval(start_pos=1482, end_pos=1528))
                    ]
                )
            ]
            
            # Use functional LangExtract API to extract structured data
            result = extract(
                text_or_documents=text,
                prompt_description=prompt,
                model_id="gemini-2.5-pro",
                api_key=self.api_key,
                temperature=0.1,
                examples=examples
            )
            
            logger.info(f"LangExtract result type: {type(result)}")
            logger.info(f"LangExtract result attributes: {dir(result)}")
            logger.info(f"LangExtract result: {result}")
            
            # Convert the result to our schema format
            if hasattr(result, 'extractions') and result.extractions:
                logger.info(f"Found {len(result.extractions)} extractions")
                
                # Parse extractions into our schema with proper data type conversion
                extracted_data = {}
                
                for extraction in result.extractions:
                    logger.info(f"Extraction: {extraction.extraction_class} = '{extraction.extraction_text}'")
                    
                    field_name = extraction.extraction_class
                    field_value = extraction.extraction_text
                    
                    # Handle field mapping and data type conversion
                    if field_name in extracted_data:
                        # Handle multiple values for list fields that expect dictionaries
                        if field_name in ["knockout_criteria", "selection_criteria", "deliverables"]:
                            if isinstance(extracted_data[field_name], list):
                                extracted_data[field_name].append({"description": field_value, "requirement": field_value})
                        # Handle multiple values for simple list fields
                        elif field_name in ["cpv_codes", "technical_requirements", "compliance_requirements"]:
                            if isinstance(extracted_data[field_name], list):
                                if field_value not in extracted_data[field_name]:
                                    extracted_data[field_name].append(field_value)
                        # Handle multiple values for assessment_criteria dict
                        elif field_name in ["assessment_criteria"]:
                            if isinstance(extracted_data[field_name], dict):
                                # Apply the same parsing logic as in the main handler
                                if ":" in field_value and ("%" in field_value or any(c.isdigit() for c in field_value.split(':')[1])):
                                    try:
                                        parts = field_value.split(":")
                                        if len(parts) == 2:
                                            criteria_name = parts[0].strip()
                                            weight_str = parts[1].strip().replace("%", "")
                                            weight = float(weight_str) / 100.0 if "%" in field_value else float(weight_str)
                                            extracted_data[field_name][criteria_name] = weight
                                    except ValueError:
                                        pass  # Skip invalid values
                        # Handle multiple values for other fields (take the longer/more detailed value)
                        else:
                            if len(field_value) > len(str(extracted_data[field_name])):
                                extracted_data[field_name] = field_value
                    else:
                        # Convert values to appropriate data types
                        if field_name == "estimated_value":
                            try:
                                # Convert to float, handling common formatting
                                clean_value = field_value.replace('.', '').replace(',', '').replace('€', '').replace('EUR', '').replace('-', '').strip()
                                # Handle cases like "120.000 per jaar" - extract just the number part
                                import re
                                number_match = re.search(r'(\d+(?:[,.]?\d+)*)', clean_value)
                                if number_match:
                                    number_str = number_match.group(1).replace(',', '').replace('.', '')
                                    extracted_data[field_name] = float(number_str)
                                else:
                                    logger.warning(f"Could not extract number from estimated_value '{field_value}'")
                                    extracted_data[field_name] = None
                            except (ValueError, TypeError):
                                logger.warning(f"Could not convert estimated_value '{field_value}' to float")
                                extracted_data[field_name] = None
                        elif field_name in ["cpv_codes", "technical_requirements", "compliance_requirements"]:
                            # Handle simple list fields (List[str])
                            if field_name not in extracted_data:
                                extracted_data[field_name] = []
                            if field_value and field_value not in extracted_data[field_name]:
                                extracted_data[field_name].append(field_value)
                        elif field_name in ["deliverables"]:
                            # Handle deliverables list (List[Dict[str, Any]])
                            if field_name not in extracted_data:
                                extracted_data[field_name] = []
                            if field_value:
                                extracted_data[field_name].append({"description": field_value, "name": field_value})
                        elif field_name in ["knockout_criteria", "selection_criteria"]:
                            # Handle criteria lists (List[Dict[str, Any]])
                            if field_name not in extracted_data:
                                extracted_data[field_name] = []
                            if field_value:
                                extracted_data[field_name].append({"description": field_value, "requirement": field_value})
                        elif field_name in ["assessment_criteria"]:
                            # Handle assessment criteria dict - try to parse criteria:weight pairs
                            if field_name not in extracted_data:
                                extracted_data[field_name] = {}
                            if field_value:
                                # Try to parse criteria like "Prijs: 40%" or similar structured patterns
                                if ":" in field_value and ("%" in field_value or any(c.isdigit() for c in field_value.split(':')[1])):
                                    try:
                                        parts = field_value.split(":")
                                        if len(parts) == 2:
                                            criteria_name = parts[0].strip()
                                            weight_str = parts[1].strip().replace("%", "")
                                            weight = float(weight_str) / 100.0 if "%" in field_value else float(weight_str)
                                            extracted_data[field_name][criteria_name] = weight
                                        else:
                                            # If it doesn't look like criteria, skip it (don't add)
                                            logger.info(f"Skipping assessment_criteria value that doesn't match criteria pattern: '{field_value}'")
                                    except ValueError:
                                        # If parsing fails, skip it (don't add)  
                                        logger.info(f"Skipping assessment_criteria value that couldn't be parsed: '{field_value}'")
                                else:
                                    # If it doesn't contain a colon and digits, skip it (don't add general text)
                                    logger.info(f"Skipping assessment_criteria value that doesn't match criteria pattern: '{field_value}'")
                        elif field_name in ["contact_persons"]:
                            # Handle contact persons list
                            if field_name not in extracted_data:
                                extracted_data[field_name] = []
                            if field_value:
                                # Parse contact info - this is simplified
                                extracted_data[field_name].append({"name": field_value})
                        elif field_name.endswith("_date") or field_name.endswith("_deadline"):
                            # Handle date fields - would need proper date parsing
                            try:
                                from dateutil import parser
                                parsed_date = parser.parse(field_value, fuzzy=True)
                                extracted_data[field_name] = parsed_date
                            except:
                                logger.warning(f"Could not parse date '{field_value}' for field '{field_name}'")
                                extracted_data[field_name] = None
                        else:
                            # Regular string fields
                            extracted_data[field_name] = field_value
                
                logger.info(f"Processed extracted data: {extracted_data}")
                
                # Debug: try to create schema and catch detailed validation errors
                try:
                    schema = TenderExtractionSchema(**extracted_data)
                    logger.info(f"Successfully created schema: {schema}")
                    return schema
                except Exception as e:
                    logger.error(f"Schema validation failed: {e}")
                    logger.error(f"Raw extracted data: {extracted_data}")
                    logger.error(f"Error type: {type(e)}")
                    # Print more detailed error info
                    if hasattr(e, 'errors'):
                        logger.error(f"Validation error details: {e.errors()}")
                    # Return empty schema on validation failure 
                    return TenderExtractionSchema()
            else:
                logger.warning("No extractions returned from LangExtract")
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