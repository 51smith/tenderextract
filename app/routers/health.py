"""Health check and monitoring endpoints."""
from fastapi import APIRouter, Depends
from typing import Dict, Any

from ..services.job_storage import JobStorageInterface
from ..dependencies import get_job_storage
from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


@router.get("/health/detailed")
async def detailed_health_check(
    job_storage: JobStorageInterface = Depends(get_job_storage)
) -> Dict[str, Any]:
    """
    Detailed health check with dependency status.
    
    Args:
        job_storage: Job storage service
        
    Returns:
        Detailed health information
    """
    health_info = {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "dependencies": {
            "job_storage": "healthy"
        },
        "configuration": {
            "max_file_size": settings.max_file_size,
            "max_files_per_batch": settings.max_files_per_batch,
            "supported_languages": settings.supported_languages,
            "temp_dir": settings.temp_dir
        }
    }
    
    # Test job storage connectivity
    try:
        # This is a simple test - in a real implementation you might
        # want to test actual storage operations
        if job_storage:
            health_info["dependencies"]["job_storage"] = "healthy"
        else:
            health_info["dependencies"]["job_storage"] = "unavailable"
            health_info["status"] = "degraded"
    except Exception as e:
        health_info["dependencies"]["job_storage"] = f"error: {str(e)}"
        health_info["status"] = "degraded"
    
    return health_info