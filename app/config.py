"""Application configuration management."""
from typing import List, Optional
from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="Tender Extraction API", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Server settings
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=True, description="Auto-reload on code changes")
    
    # File processing settings
    max_file_size: int = Field(default=50_000_000, description="Maximum file size in bytes (50MB)")
    max_files_per_batch: int = Field(default=20, description="Maximum files per batch request")
    temp_dir: str = Field(default="temp", description="Temporary directory for file processing")
    allowed_file_types: List[str] = Field(default=["application/pdf"], description="Allowed MIME types")
    
    # Processing settings
    default_language: str = Field(default="nl", description="Default processing language")
    supported_languages: List[str] = Field(
        default=["nl", "en", "de", "fr"], 
        description="Supported processing languages"
    )
    
    # Redis settings (for production job storage)
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    use_redis: bool = Field(default=False, description="Use Redis for job storage")
    
    # Security settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"], 
        description="Allowed CORS origins"
    )
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    require_api_key: bool = Field(default=False, description="Require API key for access")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    
    # LangExtract and AI settings
    google_api_key: Optional[str] = Field(default=None, description="Google API key for Gemini")
    extraction_temperature: float = Field(default=0.1, description="LangExtract temperature")
    extraction_max_tokens: int = Field(default=8192, description="Maximum tokens for extraction")
    
    # OCR settings
    perform_ocr: bool = Field(default=True, description="Perform OCR on scanned PDFs")
    ocr_language: str = Field(default="nld+eng", description="OCR languages")
    ocr_confidence_threshold: int = Field(default=30, description="Minimum OCR confidence")
    
    # Caching settings
    enable_extraction_cache: bool = Field(default=True, description="Enable extraction result caching")
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")
    
    # Processing limits
    max_concurrent_extractions: int = Field(default=3, description="Maximum concurrent extractions")
    extraction_timeout_minutes: int = Field(default=30, description="Extraction timeout in minutes")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()