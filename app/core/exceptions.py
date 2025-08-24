"""Custom application exceptions."""
from typing import Any, Dict, Optional


class TenderExtractionException(Exception):
    """Base exception for tender extraction application."""
    
    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(TenderExtractionException):
    """Validation error exception."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details, status_code=400)


class FileProcessingError(TenderExtractionException):
    """File processing error exception."""
    
    def __init__(self, message: str, filename: str, details: Optional[Dict[str, Any]] = None):
        self.filename = filename
        details = details or {}
        details["filename"] = filename
        super().__init__(message, details, status_code=422)


class JobNotFoundError(TenderExtractionException):
    """Job not found error exception."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        message = f"Job with ID '{job_id}' not found"
        details = {"job_id": job_id}
        super().__init__(message, details, status_code=404)


class ExtractionPipelineError(TenderExtractionException):
    """Extraction pipeline error exception."""
    
    def __init__(self, message: str, pipeline_stage: str, details: Optional[Dict[str, Any]] = None):
        self.pipeline_stage = pipeline_stage
        details = details or {}
        details["pipeline_stage"] = pipeline_stage
        super().__init__(message, details, status_code=500)


class StorageError(TenderExtractionException):
    """Storage operation error exception."""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        self.operation = operation
        details = details or {}
        details["operation"] = operation
        super().__init__(message, details, status_code=500)