"""JSONL export service for extraction results."""
import json
import io
import gzip
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from ..models.extraction import DocumentExtractionResult, MergedTenderResult
from ..models.jobs import SingleExtractionJob, BatchExtractionJob
from ..core.logging import get_contextual_logger

logger = get_contextual_logger("jsonl_export")


class JSONLExportService:
    """Service for exporting extraction results in JSONL format."""
    
    def __init__(self):
        self.logger = get_contextual_logger("jsonl_export")
    
    def export_single_result(
        self, 
        result: DocumentExtractionResult,
        include_metadata: bool = True,
        compress: bool = False
    ) -> Union[str, bytes]:
        """
        Export a single extraction result as JSONL.
        
        Args:
            result: Document extraction result
            include_metadata: Whether to include export metadata
            compress: Whether to compress the output
            
        Returns:
            JSONL string or compressed bytes
        """
        jsonl_lines = []
        
        # Add metadata if requested
        if include_metadata:
            metadata = self._create_export_metadata([result])
            jsonl_lines.append(json.dumps(metadata))
        
        # Add the result
        result_dict = self._prepare_result_for_export(result)
        jsonl_lines.append(json.dumps(result_dict, ensure_ascii=False))
        
        jsonl_content = '\n'.join(jsonl_lines) + '\n'
        
        if compress:
            return gzip.compress(jsonl_content.encode('utf-8'))
        
        return jsonl_content
    
    def export_batch_results(
        self,
        individual_results: List[DocumentExtractionResult],
        merged_result: Optional[MergedTenderResult] = None,
        include_metadata: bool = True,
        compress: bool = False
    ) -> Union[str, bytes]:
        """
        Export batch extraction results as JSONL.
        
        Args:
            individual_results: List of individual extraction results
            merged_result: Optional merged result
            include_metadata: Whether to include export metadata
            compress: Whether to compress the output
            
        Returns:
            JSONL string or compressed bytes
        """
        jsonl_lines = []
        
        # Add metadata if requested
        if include_metadata:
            all_results = individual_results + ([merged_result] if merged_result else [])
            metadata = self._create_export_metadata(all_results)
            jsonl_lines.append(json.dumps(metadata))
        
        # Add merged result first if available
        if merged_result:
            merged_dict = self._prepare_result_for_export(merged_result)
            jsonl_lines.append(json.dumps(merged_dict, ensure_ascii=False))
        
        # Add individual results
        for result in individual_results:
            result_dict = self._prepare_result_for_export(result)
            jsonl_lines.append(json.dumps(result_dict, ensure_ascii=False))
        
        jsonl_content = '\n'.join(jsonl_lines) + '\n'
        
        if compress:
            return gzip.compress(jsonl_content.encode('utf-8'))
        
        return jsonl_content
    
    def export_job_results(
        self,
        job: Union[SingleExtractionJob, BatchExtractionJob],
        include_metadata: bool = True,
        compress: bool = False
    ) -> Union[str, bytes]:
        """
        Export job results as JSONL.
        
        Args:
            job: Extraction job with results
            include_metadata: Whether to include export metadata
            compress: Whether to compress the output
            
        Returns:
            JSONL string or compressed bytes
        """
        jsonl_lines = []
        
        # Create job metadata
        if include_metadata:
            job_metadata = {
                "export_type": "job_results",
                "export_timestamp": datetime.utcnow().isoformat(),
                "job_id": job.job_id,
                "job_type": job.job_type.value,
                "job_name": getattr(job, 'job_name', None),
                "total_documents": getattr(job, 'total_documents', 1),
                "language": job.language,
                "extraction_completed_at": job.updated_at.isoformat() if job.updated_at else None
            }
            jsonl_lines.append(json.dumps(job_metadata))
        
        if isinstance(job, SingleExtractionJob):
            # Single job result
            if job.result:
                result_dict = self._prepare_job_result_for_export(job.result, job)
                jsonl_lines.append(json.dumps(result_dict, ensure_ascii=False))
        
        elif isinstance(job, BatchExtractionJob):
            # Batch job results
            if job.merged_result:
                # Export merged result
                merged_dict = self._prepare_job_result_for_export(job.merged_result, job)
                jsonl_lines.append(json.dumps(merged_dict, ensure_ascii=False))
            
            # Export individual results
            if job.individual_results:
                for result in job.individual_results:
                    result_dict = self._prepare_job_result_for_export(result, job)
                    jsonl_lines.append(json.dumps(result_dict, ensure_ascii=False))
            elif job.results:
                for result in job.results:
                    result_dict = self._prepare_job_result_for_export(result, job)
                    jsonl_lines.append(json.dumps(result_dict, ensure_ascii=False))
        
        jsonl_content = '\n'.join(jsonl_lines) + '\n'
        
        if compress:
            return gzip.compress(jsonl_content.encode('utf-8'))
        
        return jsonl_content
    
    def _create_export_metadata(self, results: List[Any]) -> Dict[str, Any]:
        """Create metadata for the export."""
        return {
            "export_type": "tender_extraction_results",
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_documents": len([r for r in results if hasattr(r, 'document_id')]),
            "api_version": "1.0.0",
            "format_version": "1.0",
            "description": "Tender document extraction results in JSONL format"
        }
    
    def _prepare_result_for_export(
        self, 
        result: Union[DocumentExtractionResult, MergedTenderResult]
    ) -> Dict[str, Any]:
        """Prepare extraction result for JSONL export."""
        if isinstance(result, DocumentExtractionResult):
            return self._prepare_document_result(result)
        elif isinstance(result, MergedTenderResult):
            return self._prepare_merged_result(result)
        else:
            # Handle dictionary results
            return result
    
    def _prepare_document_result(self, result: DocumentExtractionResult) -> Dict[str, Any]:
        """Prepare document extraction result for export."""
        # Convert to dict and format properly
        result_dict = result.model_dump(exclude_none=False)
        
        # Ensure ISO format for dates
        for field_name, field_value in result_dict.items():
            if isinstance(field_value, datetime):
                result_dict[field_name] = field_value.isoformat()
        
        # Add result type
        result_dict["result_type"] = "document_extraction"
        
        # Ensure source attribution is properly formatted
        if result_dict.get("source_attribution"):
            formatted_attribution = {}
            for field, attr in result_dict["source_attribution"].items():
                if isinstance(attr, dict):
                    formatted_attr = dict(attr)
                    if "extraction_timestamp" in formatted_attr:
                        if isinstance(formatted_attr["extraction_timestamp"], datetime):
                            formatted_attr["extraction_timestamp"] = formatted_attr["extraction_timestamp"].isoformat()
                    formatted_attribution[field] = formatted_attr
                else:
                    formatted_attribution[field] = attr
            result_dict["source_attribution"] = formatted_attribution
        
        return result_dict
    
    def _prepare_merged_result(self, result: MergedTenderResult) -> Dict[str, Any]:
        """Prepare merged result for export."""
        result_dict = result.model_dump(exclude_none=False)
        
        # Ensure ISO format for dates
        for field_name, field_value in result_dict.items():
            if isinstance(field_value, datetime):
                result_dict[field_name] = field_value.isoformat()
        
        # Add result type
        result_dict["result_type"] = "merged_extraction"
        
        return result_dict
    
    def _prepare_job_result_for_export(
        self, 
        result: Dict[str, Any], 
        job: Union[SingleExtractionJob, BatchExtractionJob]
    ) -> Dict[str, Any]:
        """Prepare job result for export with additional context."""
        # Ensure result is a dictionary
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump(exclude_none=False)
        else:
            result_dict = dict(result)
        
        # Add job context
        result_dict["job_context"] = {
            "job_id": job.job_id,
            "job_type": job.job_type.value,
            "processing_language": job.language,
            "processed_at": job.updated_at.isoformat() if job.updated_at else None
        }
        
        # Format dates to ISO strings
        self._format_dates_in_dict(result_dict)
        
        return result_dict
    
    def _format_dates_in_dict(self, data: Dict[str, Any]) -> None:
        """Recursively format datetime objects to ISO strings."""
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                self._format_dates_in_dict(value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, datetime):
                        value[i] = item.isoformat()
                    elif isinstance(item, dict):
                        self._format_dates_in_dict(item)
    
    def create_streaming_response(
        self,
        content: Union[str, bytes],
        filename: str,
        compress: bool = False
    ) -> io.BytesIO:
        """Create streaming response for JSONL export."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        return io.BytesIO(content)
    
    def get_content_type(self, compress: bool = False) -> str:
        """Get appropriate content type for the export."""
        if compress:
            return "application/gzip"
        return "application/x-ndjson"
    
    def get_filename(
        self, 
        job_id: str, 
        compress: bool = False, 
        timestamp: bool = True
    ) -> str:
        """Generate filename for export."""
        base_name = f"tender_extraction_{job_id}"
        
        if timestamp:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base_name += f"_{ts}"
        
        extension = ".jsonl.gz" if compress else ".jsonl"
        return base_name + extension


# Global export service instance
jsonl_export_service = JSONLExportService()