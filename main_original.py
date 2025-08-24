from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import uuid
import asyncio
from datetime import datetime
import json

app = FastAPI(title="Multi-Document Tender Extraction API")

# Job tracking store (use Redis in production)
extraction_jobs: Dict[str, dict] = {}

class BatchExtractionRequest(BaseModel):
    """Request model for batch document processing"""
    job_name: Optional[str] = Field(None, description="Name for this extraction batch")
    language: str = Field("nl", description="Primary language: nl, en, de, fr")
    merge_results: bool = Field(False, description="Merge all documents into single tender result")
    extract_relationships: bool = Field(True, description="Extract relationships between documents")

class DocumentExtractionResult(BaseModel):
    """Individual document extraction result"""
    document_id: str
    filename: str
    document_type: str  # main_tender, annex, technical_specs, etc.
    extraction_timestamp: datetime

    # All tender fields as before
    project_title: Optional[str] = None
    contracting_authority: Optional[str] = None
    cpv_codes: List[str] = Field(default=[])
    estimated_value: Optional[float] = None
    submission_deadline: Optional[datetime] = None

    # Evaluation criteria with detailed structure
    knockout_criteria: List[Dict] = Field(default=[])
    selection_criteria: List[Dict] = Field(default=[])
    assessment_criteria: Dict[str, float] = Field(default={})

    # Requirements and deliverables
    deliverables: List[Dict] = Field(default=[])
    requirements: List[str] = Field(default=[])

    # Source attribution for each field
    source_attribution: Dict = Field(default={})

class MergedTenderResult(BaseModel):
    """Merged result from multiple documents"""
    tender_id: str
    extraction_timestamp: datetime
    source_documents: List[str]

    # Consolidated tender information
    project_overview: Dict
    contract_details: Dict
    critical_dates: Dict
    stakeholders: List[Dict]
    evaluation_criteria: Dict
    deliverables_and_requirements: Dict

    # Document relationships
    document_relationships: List[Dict]

    # Extraction quality metrics
    completeness_score: float
    confidence_scores: Dict[str, float]

@app.post("/extract-single")
async def extract_single_document(
        file: UploadFile = File(...),
        language: str = "nl",
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Extract information from a single tender document"""

    if not file.content_type.startswith('application/pdf'):
        raise HTTPException(400, "Only PDF files are supported")

    job_id = str(uuid.uuid4())

    # Initialize job
    extraction_jobs[job_id] = {
        "status": "processing",
        "type": "single",
        "filename": file.filename,
        "language": language
    }

    # Start extraction
    background_tasks.add_task(
        process_single_document,
        job_id,
        file,
        language
    )

    return {"job_id": job_id, "status": "processing"}

@app.post("/extract-batch")
async def extract_multiple_documents(
        files: List[UploadFile] = File(...),
        request: BatchExtractionRequest = BatchExtractionRequest(),
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Extract and optionally merge information from multiple tender documents"""

    # Validate files
    for file in files:
        if not file.content_type.startswith('application/pdf'):
            raise HTTPException(
                400,
                f"File {file.filename} is not a PDF. Only PDF files are supported"
            )

    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 documents per batch")

    job_id = str(uuid.uuid4())

    # Initialize batch job
    extraction_jobs[job_id] = {
        "status": "processing",
        "type": "batch",
        "total_documents": len(files),
        "processed_documents": 0,
        "filenames": [f.filename for f in files],
        "language": request.language,
        "merge_results": request.merge_results,
        "job_name": request.job_name or f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }

    # Start batch extraction
    background_tasks.add_task(
        process_batch_documents,
        job_id,
        files,
        request
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "total_documents": len(files)
    }

async def process_single_document(job_id: str, file: UploadFile, language: str):
    """Process a single tender document"""
    try:
        # Save file temporarily
        file_path = f"temp/{job_id}_{file.filename}"
        content = await file.read()

        with open(file_path, 'wb') as f:
            f.write(content)

        # Extract with LangExtract
        from tender_extraction import TenderExtractionPipeline

        pipeline = TenderExtractionPipeline(language=language)
        result = await asyncio.to_thread(
            pipeline.process_pdf_with_coordinates,
            file_path
        )

        # Format results
        extraction_result = format_extraction_result(result, file.filename)

        # Update job status
        extraction_jobs[job_id].update({
            "status": "completed",
            "result": extraction_result.dict()
        })

    except Exception as e:
        extraction_jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })

async def process_batch_documents(
        job_id: str,
        files: List[UploadFile],
        request: BatchExtractionRequest
):
    """Process multiple tender documents with optional merging"""
    try:
        individual_results = []

        for idx, file in enumerate(files):
            # Update progress
            extraction_jobs[job_id]["processed_documents"] = idx

            # Save file
            file_path = f"temp/{job_id}_{idx}_{file.filename}"
            content = await file.read()

            with open(file_path, 'wb') as f:
                f.write(content)

            # Determine document type based on filename/content
            doc_type = classify_document_type(file.filename, content)

            # Extract with appropriate strategy
            from tender_extraction import TenderExtractionPipeline

            pipeline = TenderExtractionPipeline(
                language=request.language,
                document_type=doc_type
            )

            result = await asyncio.to_thread(
                pipeline.process_pdf_with_coordinates,
                file_path
            )

            # Format and store individual result
            extraction_result = format_extraction_result(
                result,
                file.filename,
                doc_type
            )
            individual_results.append(extraction_result)

        # Process results based on request
        if request.merge_results:
            # Merge all documents into consolidated tender view
            merged_result = merge_tender_documents(
                individual_results,
                extract_relationships=request.extract_relationships
            )

            extraction_jobs[job_id].update({
                "status": "completed",
                "processed_documents": len(files),
                "merged_result": merged_result.dict(),
                "individual_results": [r.dict() for r in individual_results]
            })
        else:
            # Return individual results
            extraction_jobs[job_id].update({
                "status": "completed",
                "processed_documents": len(files),
                "results": [r.dict() for r in individual_results]
            })

    except Exception as e:
        extraction_jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })

def classify_document_type(filename: str, content: bytes) -> str:
    """Classify document type based on filename and content patterns"""
    filename_lower = filename.lower()

    # Filename-based classification
    if 'bestek' in filename_lower or 'specifications' in filename_lower:
        return 'technical_specifications'
    elif 'aankondiging' in filename_lower or 'announcement' in filename_lower:
        return 'tender_announcement'
    elif 'bijlage' in filename_lower or 'annex' in filename_lower:
        return 'annex'
    elif 'criteria' in filename_lower or 'gunning' in filename_lower:
        return 'evaluation_criteria'
    elif 'contract' in filename_lower:
        return 'contract_terms'
    else:
        # Content-based classification would go here
        return 'general_tender_document'

def merge_tender_documents(
        documents: List[DocumentExtractionResult],
        extract_relationships: bool = True
) -> MergedTenderResult:
    """Intelligently merge multiple tender documents into consolidated result"""

    merged = MergedTenderResult(
        tender_id=str(uuid.uuid4()),
        extraction_timestamp=datetime.utcnow(),
        source_documents=[doc.filename for doc in documents]
    )

    # Consolidate project overview (take most complete)
    project_titles = [d.project_title for d in documents if d.project_title]
    contracting_authorities = [d.contracting_authority for d in documents if d.contracting_authority]

    merged.project_overview = {
        "title": project_titles[0] if project_titles else None,
        "contracting_authority": contracting_authorities[0] if contracting_authorities else None,
        "cpv_codes": list(set(sum([d.cpv_codes for d in documents], []))),
        "sources": identify_sources(documents, ['project_title', 'contracting_authority'])
    }

    # Merge contract details (handle conflicts)
    values = [d.estimated_value for d in documents if d.estimated_value]
    deadlines = [d.submission_deadline for d in documents if d.submission_deadline]

    merged.contract_details = {
        "estimated_value": max(values) if values else None,  # Take highest value
        "submission_deadline": min(deadlines) if deadlines else None,  # Earliest deadline
        "value_discrepancies": detect_value_conflicts(documents)
    }

    # Consolidate evaluation criteria (combine and deduplicate)
    all_knockout = sum([d.knockout_criteria for d in documents], [])
    all_selection = sum([d.selection_criteria for d in documents], [])

    # Merge assessment criteria weights
    assessment_weights = {}
    for doc in documents:
        for criterion, weight in doc.assessment_criteria.items():
            if criterion in assessment_weights:
                # Average if multiple documents specify same criterion
                assessment_weights[criterion] = (assessment_weights[criterion] + weight) / 2
            else:
                assessment_weights[criterion] = weight

    merged.evaluation_criteria = {
        "knockout_criteria": deduplicate_criteria(all_knockout),
        "selection_criteria": deduplicate_criteria(all_selection),
        "assessment_criteria": assessment_weights,
        "criteria_sources": identify_criteria_sources(documents)
    }

    # Extract document relationships
    if extract_relationships:
        merged.document_relationships = extract_document_relationships(documents)

    # Calculate quality metrics
    merged.completeness_score = calculate_completeness(merged)
    merged.confidence_scores = calculate_confidence_scores(documents)

    return merged

def deduplicate_criteria(criteria_list: List[Dict]) -> List[Dict]:
    """Remove duplicate criteria while preserving source information"""
    seen = set()
    unique = []

    for criterion in criteria_list:
        # Create hashable representation
        criterion_key = json.dumps(criterion, sort_keys=True)

        if criterion_key not in seen:
            seen.add(criterion_key)
            unique.append(criterion)

    return unique

def extract_document_relationships(documents: List[DocumentExtractionResult]) -> List[Dict]:
    """Identify relationships between documents"""
    relationships = []

    for i, doc1 in enumerate(documents):
        for doc2 in documents[i+1:]:
            # Check for cross-references
            if references_document(doc1, doc2):
                relationships.append({
                    "type": "references",
                    "source": doc1.filename,
                    "target": doc2.filename
                })

            # Check for parent-child relationships
            if is_annex_of(doc2, doc1):
                relationships.append({
                    "type": "annex",
                    "parent": doc1.filename,
                    "child": doc2.filename
                })

    return relationships

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get extraction job status and results"""

    job = extraction_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return job

@app.get("/export/{job_id}")
async def export_results_jsonl(job_id: str):
    """Export extraction results in JSONL format"""

    job = extraction_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if job["status"] != "completed":
        raise HTTPException(400, "Job not completed")

    # Generate JSONL output
    jsonl_lines = []

    if job["type"] == "batch" and "merged_result" in job:
        # Export merged result
        jsonl_lines.append(json.dumps(job["merged_result"]))

        # Also include individual results
        for result in job.get("individual_results", []):
            jsonl_lines.append(json.dumps(result))
    else:
        # Export single or multiple individual results
        results = job.get("results", [job.get("result")])
        for result in results:
            if result:
                jsonl_lines.append(json.dumps(result))

    # Return as streaming response
    from fastapi.responses import StreamingResponse
    import io

    output = io.StringIO()
    for line in jsonl_lines:
        output.write(line + "\n")

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.read().encode()),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename=tender_extraction_{job_id}.jsonl"
        }
    )

# Helper functions for quality metrics
def calculate_completeness(result: MergedTenderResult) -> float:
    """Calculate how complete the extraction is"""
    required_fields = [
        result.project_overview.get("title"),
        result.project_overview.get("contracting_authority"),
        result.contract_details.get("estimated_value"),
        result.contract_details.get("submission_deadline"),
        len(result.evaluation_criteria.get("assessment_criteria", {})) > 0
    ]

    return sum(1 for f in required_fields if f) / len(required_fields)

def calculate_confidence_scores(documents: List[DocumentExtractionResult]) -> Dict[str, float]:
    """Calculate average confidence scores by category"""
    confidence_scores = {}

    for category in ["project_overview", "contract_details", "evaluation_criteria"]:
        scores = []
        for doc in documents:
            # Get confidence from source attribution
            for field, attribution in doc.source_attribution.items():
                if category in field:
                    scores.append(attribution.get("confidence", 0.0))

        if scores:
            confidence_scores[category] = sum(scores) / len(scores)

    return confidence_scores