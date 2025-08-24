"""Request schemas for API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BatchExtractionRequest(BaseModel):
    """Request model for batch document processing."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_name": "Infrastructure_Tender_2024",
                "language": "nl",
                "merge_results": True,
                "extract_relationships": True
            }
        }
    )
    
    job_name: Optional[str] = Field(
        None, 
        description="Name for this extraction batch"
    )
    language: str = Field(
        "nl", 
        description="Primary language: nl, en, de, fr",
        pattern="^(nl|en|de|fr)$"
    )
    merge_results: bool = Field(
        False, 
        description="Merge all documents into single tender result"
    )
    extract_relationships: bool = Field(
        True, 
        description="Extract relationships between documents"
    )