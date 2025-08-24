"""Caching service for extraction results."""
import hashlib
import json
import pickle
from typing import Any, Optional
from datetime import datetime, timedelta

import redis.asyncio as redis
from ..config import settings
from ..core.logging import get_contextual_logger

logger = get_contextual_logger("cache")


class CacheService:
    """Service for caching extraction results."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.enable_extraction_cache
        
        if self.enabled and settings.use_redis:
            self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=False  # We'll handle binary data
            )
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.enabled = False
    
    def _generate_cache_key(self, content_hash: str, language: str) -> str:
        """Generate cache key for extraction result."""
        return f"extraction:{content_hash}:{language}"
    
    def _calculate_content_hash(self, file_content: bytes) -> str:
        """Calculate hash of file content for caching."""
        return hashlib.sha256(file_content).hexdigest()
    
    async def get_cached_result(
        self, 
        file_content: bytes, 
        language: str
    ) -> Optional[dict]:
        """Get cached extraction result."""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            content_hash = self._calculate_content_hash(file_content)
            cache_key = self._generate_cache_key(content_hash, language)
            
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                result = pickle.loads(cached_data)
                logger.info(f"Cache hit for key: {cache_key}")
                return result
            
            logger.debug(f"Cache miss for key: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached result: {e}")
            return None
    
    async def cache_result(
        self, 
        file_content: bytes, 
        language: str, 
        result: dict
    ) -> bool:
        """Cache extraction result."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            content_hash = self._calculate_content_hash(file_content)
            cache_key = self._generate_cache_key(content_hash, language)
            
            # Add cache metadata
            cache_data = {
                "result": result,
                "cached_at": datetime.utcnow().isoformat(),
                "content_hash": content_hash
            }
            
            # Serialize and cache
            serialized_data = pickle.dumps(cache_data)
            ttl_seconds = settings.cache_ttl_hours * 3600
            
            await self.redis_client.setex(
                cache_key, 
                ttl_seconds, 
                serialized_data
            )
            
            logger.info(f"Cached result for key: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache result: {e}")
            return False
    
    async def invalidate_cache(self, pattern: str = "extraction:*") -> int:
        """Invalidate cache entries matching pattern."""
        if not self.enabled or not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0
    
    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
        
        try:
            info = await self.redis_client.info('memory')
            keys_count = await self.redis_client.dbsize()
            
            return {
                "enabled": True,
                "total_keys": keys_count,
                "used_memory": info.get('used_memory_human', 'unknown'),
                "redis_version": info.get('redis_version', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Global cache service instance
cache_service = CacheService()