from typing import Optional
from pathlib import Path
import logging
import sys
from inbox_agent.config import settings
from inbox_agent.logging_context import WorkflowIdFilter
from inbox_agent.artifact_logger import setup_artifact_logger

def build_root_logger(log_file_path: Optional[str | Path] = None) -> None:
    if log_file_path is None:
        log_file_path = settings.PROJ_ROOT / 'logs' / 'inbox_agent.log'
    
    # Create handlers
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # Add workflow ID filter to all handlers
    workflow_filter = WorkflowIdFilter()
    file_handler.addFilter(workflow_filter)
    stream_handler.addFilter(workflow_filter)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - [%(workflow_id)s] - %(name)s - %(levelname)s - %(message)s',
        handlers=[file_handler, stream_handler]
    )
    
    # Setup artifact logger for LLM traces
    setup_artifact_logger()
    
    logging.getLogger("notion_client").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
