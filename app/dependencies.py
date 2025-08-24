"""Dependency injection for FastAPI endpoints."""
from typing import Optional
from fastapi import Depends, HTTPException, Header, status

from .config import settings
from .services.job_storage import JobStorageInterface, get_job_storage_instance
from .services.extraction_service import ExtractionService, extraction_service
from .core.logging import get_contextual_logger


async def get_job_storage() -> JobStorageInterface:
    """Dependency to get job storage service."""
    return get_job_storage_instance()


async def get_extraction_service() -> ExtractionService:
    """Dependency to get extraction service."""
    return extraction_service


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias=settings.api_key_header)
) -> Optional[str]:
    """
    Verify API key if authentication is required.
    
    Args:
        x_api_key: API key from request header
        
    Returns:
        The verified API key or None if not required
        
    Raises:
        HTTPException: If API key is required but missing or invalid
    """
    if not settings.require_api_key:
        return None
    
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required"
        )
    
    # In a real application, you would validate the API key against a database
    # For now, this is a placeholder
    valid_api_keys = ["development-key", "test-key"]  # This would come from database
    
    if x_api_key not in valid_api_keys:
        logger = get_contextual_logger("auth", api_key_prefix=x_api_key[:8] + "...")
        logger.warning("Invalid API key attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return x_api_key


async def get_current_user_id(
    api_key: Optional[str] = Depends(verify_api_key)
) -> Optional[str]:
    """
    Get current user ID based on API key.
    
    Args:
        api_key: Verified API key
        
    Returns:
        User ID associated with the API key, or None if no auth required
    """
    if not api_key:
        return None
    
    # In a real application, you would look up the user associated with the API key
    # For now, return a mock user ID
    return "user_123"


def validate_file_upload(
    content_type: str, 
    file_size: Optional[int], 
    filename: str
) -> None:
    """
    Validate uploaded file requirements.
    
    Args:
        content_type: MIME type of the uploaded file
        file_size: Size of the uploaded file in bytes
        filename: Name of the uploaded file
        
    Raises:
        HTTPException: If file validation fails
    """
    # Check file type
    if content_type not in settings.allowed_file_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{content_type}' not allowed. Supported types: {settings.allowed_file_types}"
        )
    
    # Check file size (skip if None, as in testing)
    if file_size is not None and file_size > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.max_file_size} bytes"
        )
    
    # Check filename
    if not filename or len(filename.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty"
        )


def validate_language(language: str) -> str:
    """
    Validate processing language.
    
    Args:
        language: Language code to validate
        
    Returns:
        Validated language code
        
    Raises:
        HTTPException: If language is not supported
    """
    if language not in settings.supported_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{language}' not supported. Supported languages: {settings.supported_languages}"
        )
    
    return language