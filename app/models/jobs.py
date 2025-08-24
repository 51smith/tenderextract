"""Job management data models."""
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Job processing type."""
    SINGLE = "single"
    BATCH = "batch"


class JobBase(BaseModel):
    """Base job information."""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    job_type: JobType = Field(..., description="Type of processing job")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    language: str = Field("nl", description="Processing language")


class SingleExtractionJob(JobBase):
    """Single document extraction job."""
    job_type: Literal[JobType.SINGLE] = Field(default=JobType.SINGLE)
    filename: str = Field(..., description="Source document filename")
    result: Optional[Dict[str, Any]] = Field(None, description="Extraction result")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchExtractionJob(JobBase):
    """Batch document extraction job."""
    job_type: Literal[JobType.BATCH] = Field(default=JobType.BATCH)
    job_name: Optional[str] = Field(None, description="Human-readable job name")
    total_documents: int = Field(..., description="Total number of documents to process")
    processed_documents: int = Field(default=0, description="Number of processed documents")
    filenames: List[str] = Field(..., description="List of source document filenames")
    merge_results: bool = Field(False, description="Whether to merge results")
    extract_relationships: bool = Field(True, description="Whether to extract relationships")
    
    # Results
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Individual extraction results")
    merged_result: Optional[Dict[str, Any]] = Field(None, description="Merged result if requested")
    individual_results: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Individual results when merging is used"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    @property
    def progress(self) -> float:
        """Calculate processing progress as percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100


class JobResponse(BaseModel):
    """Standard job response model."""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    message: Optional[str] = Field(None, description="Status message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_789",
                "status": "processing",
                "message": "Document processing started"
            }
        }
    )


class BatchJobResponse(JobResponse):
    """Batch job response with additional information."""
    total_documents: int = Field(..., description="Total documents to process")
    processed_documents: int = Field(default=0, description="Documents processed so far")
    progress: float = Field(..., description="Processing progress percentage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "batch_456",
                "status": "processing",
                "total_documents": 5,
                "processed_documents": 2,
                "progress": 40.0
            }
        }
    )