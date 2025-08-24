"""Data models for extraction results."""
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TenderSourceAttribution(BaseModel):
    """Source attribution for extracted information."""
    
    source_filename: str = Field(..., description="Source document filename")
    page_number: int = Field(..., description="Page number where information was found")
    char_start: int = Field(..., description="Character start position")
    char_end: int = Field(..., description="Character end position")
    bbox: List[float] = Field(default_factory=list, description="Bounding box coordinates [x1,y1,x2,y2]")
    confidence_score: float = Field(..., description="Extraction confidence score 0-1")
    extraction_timestamp: datetime = Field(..., description="When extraction was performed")


class DocumentExtractionResult(BaseModel):
    """Individual document extraction result with comprehensive tender information."""
    
    # Document metadata
    document_id: str = Field(..., description="Unique identifier for the document")
    filename: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="Document type classification")
    extraction_timestamp: datetime = Field(..., description="When extraction was performed")

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

    # Source attribution for each field
    source_attribution: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Source attribution for extracted fields"
    )
    
    # Quality metrics
    completeness_score: Optional[float] = Field(None, description="Completeness score 0-1")
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict, 
        description="Confidence scores by category"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "doc_123",
                "filename": "tender_announcement.pdf",
                "document_type": "tender_announcement",
                "extraction_timestamp": "2024-01-15T10:30:00Z",
                "project_title": "IT Infrastructure Modernization",
                "contracting_authority": "Ministry of Digital Affairs",
                "cpv_codes": ["48000000-8"],
                "estimated_value": 500000.0,
                "submission_deadline": "2024-02-15T17:00:00Z"
            }
        }
    )


class MergedTenderResult(BaseModel):
    """Merged result from multiple documents."""
    
    tender_id: str = Field(..., description="Unique identifier for the merged tender")
    extraction_timestamp: datetime = Field(..., description="When merging was performed")
    source_documents: List[str] = Field(..., description="List of source document filenames")

    # Consolidated tender information
    project_overview: Dict = Field(..., description="Consolidated project overview")
    contract_details: Dict = Field(..., description="Contract details and values")
    critical_dates: Dict = Field(..., description="Important dates and deadlines")
    stakeholders: List[Dict] = Field(
        default_factory=list, 
        description="Stakeholders and contacts"
    )
    evaluation_criteria: Dict = Field(..., description="Consolidated evaluation criteria")
    deliverables_and_requirements: Dict = Field(
        ..., 
        description="Consolidated deliverables and requirements"
    )

    # Document relationships
    document_relationships: List[Dict] = Field(
        default_factory=list, 
        description="Relationships between source documents"
    )

    # Extraction quality metrics
    completeness_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Completeness score (0-1)"
    )
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict, 
        description="Confidence scores by category"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tender_id": "tender_456",
                "extraction_timestamp": "2024-01-15T10:35:00Z",
                "source_documents": ["announcement.pdf", "specs.pdf"],
                "completeness_score": 0.85,
                "confidence_scores": {
                    "project_overview": 0.9,
                    "contract_details": 0.8
                }
            }
        }
    )