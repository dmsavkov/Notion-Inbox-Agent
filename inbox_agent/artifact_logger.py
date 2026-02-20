"""
Artifact logger for tracing LLM requests and responses.

Logs Pydantic models to a separate JSONL file for analysis and debugging.
Each log entry is wrapped in a LogEnvelope with workflow_id for traceability.
"""
import logging
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from inbox_agent.logging_context import get_workflow_id

T = TypeVar('T', bound=BaseModel)


class LogEnvelope(BaseModel, Generic[T]):
    """
    Wrapper for logged artifacts with workflow context.
    
    Attributes:
        workflow_id: Short workflow/page ID for tracing
        artifact_type: Type of artifact being logged (e.g., "metadata_classification")
        payload: The actual Pydantic model being logged
    """
    workflow_id: str
    artifact_type: str
    payload: T


def setup_artifact_logger(log_file: str = "logs/llm_traces.jsonl") -> None:
    """
    Initialize the artifact logger. Should be called once at app startup.
    
    Args:
        log_file: Path to JSONL log file for artifacts
    """
    logger = logging.getLogger("artifact_tracer")
    logger.propagate = False  # Don't spam console
    
    # Guard against duplicate handlers
    if not logger.handlers:
        handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(message)s')  # Pure JSON, no prefix
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)


def log_llm_artifact(model: BaseModel, artifact_type: str) -> None:
    """
    Log a Pydantic model as an artifact with workflow context.
    
    Args:
        model: Pydantic model to log (e.g., MetadataResult, RankingResult)
        artifact_type: Human-readable type identifier
    """
    logger = logging.getLogger("artifact_tracer")
    
    workflow_id = get_workflow_id() or "unknown"
    envelope = LogEnvelope(
        workflow_id=workflow_id,
        artifact_type=artifact_type,
        payload=model
    )
    
    logger.debug(envelope.model_dump_json())
