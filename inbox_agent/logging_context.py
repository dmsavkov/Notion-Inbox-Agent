"""
Logging context for workflow/page ID tracking.

Uses contextvars for thread-safe storage of workflow IDs that are attached
to all log records via a logging filter.
"""
import logging
from contextvars import ContextVar
from typing import Optional

# Context variable to store workflow/page ID
_workflow_id: ContextVar[Optional[str]] = ContextVar('workflow_id', default=None)


def set_workflow_id(workflow_id: str) -> None:
    """
    Set the workflow/page ID for the current context.
    
    Args:
        workflow_id: Unique identifier for this workflow/page
    """
    _workflow_id.set(workflow_id)


def get_workflow_id() -> Optional[str]:
    """
    Get the current workflow/page ID.
    
    Returns:
        Current workflow ID or None if not set
    """
    return _workflow_id.get()


def clear_workflow_id() -> None:
    """Clear the workflow/page ID from the current context."""
    _workflow_id.set(None)


class WorkflowIdFilter(logging.Filter):
    """
    Logging filter that adds workflow_id to all log records.
    
    The workflow_id is retrieved from the context variable and added
    as an attribute to each LogRecord, making it available for formatting.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add workflow_id to the log record.
        
        Args:
            record: LogRecord to modify
            
        Returns:
            True (always allow the record through)
        """
        workflow_id = get_workflow_id()
        record.workflow_id = workflow_id if workflow_id else '-'
        return True
