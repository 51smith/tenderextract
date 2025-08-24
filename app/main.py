"""FastAPI application factory and configuration."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .core.logging import setup_logging, get_logger
from .core.exceptions import TenderExtractionException
from .routers import extraction, health

# Setup logging
setup_logging()
logger = get_logger("main")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for extracting structured information from tender documents",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Add routers
    app.include_router(health.router)
    app.include_router(extraction.router)

    # Add exception handlers
    @app.exception_handler(TenderExtractionException)
    async def tender_extraction_exception_handler(
        request: Request, 
        exc: TenderExtractionException
    ) -> JSONResponse:
        """Handle custom application exceptions."""
        logger.error(f"Application error: {exc.message}", extra={"details": exc.details})
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details,
                "type": exc.__class__.__name__
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, 
        exc: HTTPException
    ) -> JSONResponse:
        """Handle HTTP exceptions with consistent format."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "type": "HTTPException"
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, 
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "type": "InternalServerError"
            }
        )

    @app.on_event("startup")
    async def startup_event():
        """Application startup event."""
        logger.info(f"Starting {settings.app_name} v{settings.app_version}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"Max file size: {settings.max_file_size} bytes")
        logger.info(f"Supported languages: {settings.supported_languages}")

    @app.on_event("shutdown") 
    async def shutdown_event():
        """Application shutdown event."""
        logger.info(f"Shutting down {settings.app_name}")
        # Add cleanup logic here if needed

    return app


# Create application instance
app = create_app()