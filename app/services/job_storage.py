"""Job storage service with support for in-memory and Redis backends."""
import json
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Optional, Union
from datetime import datetime

from ..models.jobs import SingleExtractionJob, BatchExtractionJob, JobStatus
from ..config import settings


class JobStorageInterface(ABC):
    """Abstract interface for job storage."""
    
    @abstractmethod
    async def create_job(self, job: Union[SingleExtractionJob, BatchExtractionJob]) -> str:
        """Create a new job and return its ID."""
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Union[SingleExtractionJob, BatchExtractionJob]]:
        """Retrieve a job by ID."""
        pass
    
    @abstractmethod
    async def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job fields."""
        pass
    
    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass


class InMemoryJobStorage(JobStorageInterface):
    """In-memory job storage for development."""
    
    def __init__(self):
        self._jobs: Dict[str, Dict] = {}
    
    async def create_job(self, job: Union[SingleExtractionJob, BatchExtractionJob]) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        job.job_id = job_id
        job.created_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        self._jobs[job_id] = job.model_dump()
        return job_id
    
    async def get_job(self, job_id: str) -> Optional[Union[SingleExtractionJob, BatchExtractionJob]]:
        """Retrieve a job by ID."""
        job_data = self._jobs.get(job_id)
        if not job_data:
            return None
        
        # Determine job type and create appropriate model
        if job_data.get("job_type") == "single":
            return SingleExtractionJob(**job_data)
        else:
            return BatchExtractionJob(**job_data)
    
    async def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job fields."""
        if job_id not in self._jobs:
            return False
        
        updates["updated_at"] = datetime.utcnow()
        self._jobs[job_id].update(updates)
        return True
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False


class RedisJobStorage(JobStorageInterface):
    """Redis-based job storage for production."""
    
    def __init__(self):
        # This would be initialized with Redis connection
        # For now, placeholder implementation
        raise NotImplementedError("Redis storage not implemented yet")
    
    async def create_job(self, job: Union[SingleExtractionJob, BatchExtractionJob]) -> str:
        """Create a new job and return its ID."""
        # Redis implementation would go here
        pass
    
    async def get_job(self, job_id: str) -> Optional[Union[SingleExtractionJob, BatchExtractionJob]]:
        """Retrieve a job by ID."""
        # Redis implementation would go here
        pass
    
    async def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job fields."""
        # Redis implementation would go here
        pass
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        # Redis implementation would go here
        pass


def get_job_storage() -> JobStorageInterface:
    """Factory function to get appropriate job storage backend."""
    if settings.use_redis:
        return RedisJobStorage()
    else:
        return InMemoryJobStorage()


# Global job storage instance
_job_storage_instance = None

def get_job_storage_instance() -> JobStorageInterface:
    """Get singleton job storage instance."""
    global _job_storage_instance
    if _job_storage_instance is None:
        _job_storage_instance = get_job_storage()
    return _job_storage_instance

# For backward compatibility
job_storage = get_job_storage_instance()