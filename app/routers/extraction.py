"""Document extraction API endpoints."""
import asyncio
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io
import json

from ..schemas.requests import BatchExtractionRequest
from ..models.jobs import SingleExtractionJob, BatchExtractionJob, JobResponse, BatchJobResponse, JobStatus, JobType
from ..services.job_storage import JobStorageInterface
from ..services.extraction_service import ExtractionService
from ..services.jsonl_export_service import jsonl_export_service
from ..dependencies import (
    get_job_storage, 
    get_extraction_service, 
    get_current_user_id,
    validate_file_upload,
    validate_language
)
from ..core.exceptions import JobNotFoundError, FileProcessingError, ValidationError
from ..core.logging import get_contextual_logger
from ..config import settings

router = APIRouter(prefix="/api/v1", tags=["extraction"])


@router.post("/extract-single", response_model=JobResponse)
async def extract_single_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("nl"),
    job_storage: JobStorageInterface = Depends(get_job_storage),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    user_id: str = Depends(get_current_user_id)
) -> JobResponse:
    """
    Extract information from a single tender document.
    
    Args:
        background_tasks: FastAPI background tasks
        file: PDF file to process
        language: Processing language (nl, en, de, fr)
        job_storage: Job storage service
        extraction_service: Document extraction service  
        user_id: Current user ID
        
    Returns:
        Job response with processing status
        
    Raises:
        HTTPException: If file validation fails
    """
    logger = get_contextual_logger("extraction", user_id=user_id, filename=file.filename)
    logger.info("Starting single document extraction")
    
    # Validate inputs
    validate_file_upload(file.content_type, file.size, file.filename)
    validated_language = validate_language(language)
    
    # Create job
    job = SingleExtractionJob(
        job_id="",  # Will be set by storage
        status=JobStatus.PROCESSING,
        job_type=JobType.SINGLE,
        language=validated_language,
        filename=file.filename
    )
    
    job_id = await job_storage.create_job(job)
    logger = get_contextual_logger("extraction", job_id=job_id, user_id=user_id)
    logger.info("Created single extraction job")
    
    # Read file content before starting background task (UploadFile gets closed after request)
    file_content = await file.read()
    
    # Start background processing
    background_tasks.add_task(
        process_single_document_background,
        job_id,
        file.filename,
        file_content,
        validated_language,
        job_storage,
        extraction_service
    )
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        message="Document processing started"
    )


@router.post("/extract-batch", response_model=BatchJobResponse)  
async def extract_multiple_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    job_name: Optional[str] = Form(None),
    language: str = Form("nl"),
    merge_results: bool = Form(False),
    extract_relationships: bool = Form(True),
    job_storage: JobStorageInterface = Depends(get_job_storage),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    user_id: str = Depends(get_current_user_id)
) -> BatchJobResponse:
    """
    Extract and optionally merge information from multiple tender documents.
    
    Args:
        background_tasks: FastAPI background tasks
        files: List of PDF files to process
        request: Batch processing configuration
        job_storage: Job storage service
        extraction_service: Document extraction service
        user_id: Current user ID
        
    Returns:
        Batch job response with processing status
        
    Raises:
        HTTPException: If validation fails
    """
    logger = get_contextual_logger("extraction", user_id=user_id)
    logger.info(f"Starting batch extraction with {len(files)} documents")
    
    # Create request object from form parameters
    request = BatchExtractionRequest(
        job_name=job_name,
        language=language,
        merge_results=merge_results,
        extract_relationships=extract_relationships
    )
    
    # Validate files
    if len(files) > settings.max_files_per_batch:
        raise ValidationError(f"Maximum {settings.max_files_per_batch} documents per batch")
    
    for file in files:
        validate_file_upload(file.content_type, file.size, file.filename)
    
    # Validate language
    validated_language = validate_language(request.language)
    request.language = validated_language
    
    # Create batch job
    job = BatchExtractionJob(
        job_id="",  # Will be set by storage
        status=JobStatus.PROCESSING,
        job_type=JobType.BATCH,
        job_name=request.job_name or f"Batch_{len(files)}_docs",
        total_documents=len(files),
        processed_documents=0,
        filenames=[f.filename for f in files],
        language=request.language,
        merge_results=request.merge_results,
        extract_relationships=request.extract_relationships
    )
    
    job_id = await job_storage.create_job(job)
    logger = get_contextual_logger("extraction", job_id=job_id, user_id=user_id)
    logger.info("Created batch extraction job")
    
    # Read file contents before starting background task (UploadFile gets closed after request)
    files_content = []
    for file in files:
        file_content = await file.read()
        files_content.append((file.filename, file_content))
    
    # Start background processing
    background_tasks.add_task(
        process_batch_documents_background,
        job_id,
        files_content,
        request,
        job_storage,
        extraction_service
    )
    
    return BatchJobResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        total_documents=len(files),
        processed_documents=0,
        progress=0.0
    )


async def process_single_document_background(
    job_id: str,
    filename: str,
    file_content: bytes,
    language: str,
    job_storage: JobStorageInterface,
    extraction_service: ExtractionService
) -> None:
    """Background task for processing single document."""
    logger = get_contextual_logger("extraction.background", job_id=job_id)
    logger.info("Starting background processing")
    
    try:
        # Save file content directly
        file_path = await extraction_service.save_file_content(file_content, filename, job_id)
        logger.info(f"Saved file to {file_path}")
        
        # Process document with caching support
        result = await extraction_service.process_single_document(
            file_path, filename, language, file_content
        )
        
        # Update job with results
        await job_storage.update_job(job_id, {
            "status": JobStatus.COMPLETED,
            "result": result.model_dump()
        })
        
        logger.info("Single document processing completed successfully")
        
        # Clean up file
        extraction_service.cleanup_temp_file(file_path)
        
    except Exception as e:
        logger.error(f"Error processing single document: {str(e)}")
        await job_storage.update_job(job_id, {
            "status": JobStatus.FAILED,
            "error": str(e)
        })


async def process_batch_documents_background(
    job_id: str,
    files_content: List[tuple[str, bytes]],
    request: BatchExtractionRequest,
    job_storage: JobStorageInterface,
    extraction_service: ExtractionService
) -> None:
    """Background task for processing batch documents."""
    logger = get_contextual_logger("extraction.background", job_id=job_id)
    logger.info("Starting batch background processing")
    
    try:
        individual_results = []
        file_paths = []
        
        for idx, (filename, file_content) in enumerate(files_content):
            # Update progress
            await job_storage.update_job(job_id, {"processed_documents": idx})
            logger.info(f"Processing document {idx + 1}/{len(files_content)}: {filename}")
            
            # Save file content directly
            file_path = await extraction_service.save_file_content(file_content, filename, job_id, idx)
            file_paths.append(file_path)
            
            # Process document with caching support
            result = await extraction_service.process_single_document(
                file_path, filename, request.language, file_content
            )
            individual_results.append(result)
        
        # Process results based on request
        if request.merge_results:
            # Merge all documents into consolidated tender view
            merged_result = extraction_service.merger.merge_tender_documents(
                individual_results,
                extract_relationships=request.extract_relationships
            )
            
            await job_storage.update_job(job_id, {
                "status": JobStatus.COMPLETED,
                "processed_documents": len(files_content),
                "merged_result": merged_result.model_dump(),
                "individual_results": [r.model_dump() for r in individual_results]
            })
        else:
            # Return individual results
            await job_storage.update_job(job_id, {
                "status": JobStatus.COMPLETED,
                "processed_documents": len(files_content),
                "results": [r.model_dump() for r in individual_results]
            })
        
        logger.info("Batch processing completed successfully")
        
        # Clean up files
        for file_path in file_paths:
            extraction_service.cleanup_temp_file(file_path)
            
    except Exception as e:
        logger.error(f"Error processing batch documents: {str(e)}")
        await job_storage.update_job(job_id, {
            "status": JobStatus.FAILED,
            "error": str(e)
        })


@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    job_storage: JobStorageInterface = Depends(get_job_storage),
    user_id: str = Depends(get_current_user_id)
) -> dict:
    """
    Get extraction job status and results.
    
    Args:
        job_id: Job identifier
        job_storage: Job storage service
        user_id: Current user ID
        
    Returns:
        Job status and results
        
    Raises:
        HTTPException: If job not found
    """
    logger = get_contextual_logger("extraction", job_id=job_id, user_id=user_id)
    
    job = await job_storage.get_job(job_id)
    if not job:
        logger.warning("Job not found")
        raise JobNotFoundError(job_id)
    
    return job.model_dump()


@router.get("/export/{job_id}")
async def export_results_jsonl(
    job_id: str,
    compress: bool = False,
    include_metadata: bool = True,
    job_storage: JobStorageInterface = Depends(get_job_storage),
    user_id: str = Depends(get_current_user_id)
) -> StreamingResponse:
    """
    Export extraction results in JSONL format.
    
    Args:
        job_id: Job identifier
        compress: Whether to compress the output with gzip
        include_metadata: Whether to include export metadata
        job_storage: Job storage service
        user_id: Current user ID
        
    Returns:
        JSONL streaming response
        
    Raises:
        HTTPException: If job not found or not completed
    """
    logger = get_contextual_logger("extraction", job_id=job_id, user_id=user_id)
    
    job = await job_storage.get_job(job_id)
    if not job:
        logger.warning("Job not found for export")
        raise JobNotFoundError(job_id)
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(400, "Job not completed")
    
    # Export using JSONL service
    jsonl_content = jsonl_export_service.export_job_results(
        job, 
        include_metadata=include_metadata,
        compress=compress
    )
    
    # Create streaming response
    content_stream = jsonl_export_service.create_streaming_response(
        jsonl_content,
        job_id,
        compress=compress
    )
    
    # Generate filename
    filename = jsonl_export_service.get_filename(job_id, compress=compress)
    content_type = jsonl_export_service.get_content_type(compress=compress)
    
    logger.info(f"Exporting job results: {filename}")
    
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    if compress:
        headers["Content-Encoding"] = "gzip"
    
    return StreamingResponse(
        content_stream,
        media_type=content_type,
        headers=headers
    )