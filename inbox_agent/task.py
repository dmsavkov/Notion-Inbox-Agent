import logging
from typing import Optional
from inbox_agent.pydantic_models import NotionTask, AIUseStatus, TaskConfig
from inbox_agent.notion import create_toggle_blocks
from inbox_agent.config import settings

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages Notion task creation"""
    
    def __init__(self, notion_client, config: Optional[TaskConfig] = None):
        self.notion_client = notion_client
        self.config = config or TaskConfig()
    
    def create_task(self, task: NotionTask) -> dict:
        """
        Create task in Notion database.
        
        Args:
            task: NotionTask with all fields populated
            
        Returns:
            Created Notion page object
        """
        logger.info(f"Creating task: {task.title}")
        logger.debug(f"Task data: {task.dict()}")
        
        # Build properties
        properties = self._build_properties(task)
        
        # Build content blocks
        children = self._build_content_blocks(task)
        
        # Create page
        try:
            # Create task in task database
            page = self.notion_client.pages.create(
                parent={"type": "data_source_id", "data_source_id": settings.NOTION_TASKS_DATA_SOURCE_ID},
                properties=properties,
                children=children
            )
            
            logger.info(f"Task created successfully: {page['id']}")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}", exc_info=True)
            raise
    
    def _build_properties(self, task: NotionTask) -> dict:
        """Build Notion properties dict matching the actual Notion database schema"""
        properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": task.title
                        }
                    }
                ]
            },
            "Importance": {
                "select": {
                    "name": str(task.importance)
                }
            },
            "Urgency": {
                "select": {
                    "name": str(task.urgency)
                }
            },
            "Impact Score": {
                "number": task.impact
            },
            "UseAIStatus": {
                "select": {
                    "name": task.ai_use_status.value.lower()
                }
            },
            "Status": {
                "status": {
                    "name": "Not started" # Default status for new tasks
                }
            }
        }
        
        # Add project relation (singular, use first project if available)
        if task.projects:
            # Query project ID for the first project
            project_name = task.projects[0]
            try:
                results = self.notion_client.data_sources.query(
                    settings.NOTION_PROJECTS_DATA_SOURCE_ID,
                    filter={
                        "property": "Name",
                        "title": {"equals": project_name}
                    }
                )
                if results["results"]:
                    properties["Project"] = {
                        "relation": [{"id": results["results"][0]["id"]}]
                    }
                    logger.debug(f"Linked task to project: {project_name}")
            except Exception as e:
                logger.warning(f"Could not find project {project_name}: {e}")
        
        return properties
    
    def _build_content_blocks(self, task: NotionTask) -> list[dict]:
        """Build page content blocks"""
        blocks = []
        
        # Original note toggle
        note_blocks = create_toggle_blocks(
            task.original_note,
            title="📝 Original Note"
        )
        blocks.extend(note_blocks)
        
        # Enrichment toggle (if exists)
        if task.enrichment:
            enrichment_blocks = create_toggle_blocks(
                task.enrichment,
                title="💡 AI Enrichment"
            )
            blocks.extend(enrichment_blocks)
        
        # Metadata callout (only if confidence exists)
        if task.confidence is not None:
            metadata_text = f"**Confidence**: {task.confidence:.2f}"
            
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": metadata_text}}],
                    "icon": {"emoji": "🤖"}
                }
            })
        
        return blocks
    
    def determine_ai_use_status(self, confidence: float) -> AIUseStatus:
        """Determine AI use status based on confidence"""
        if confidence < self.config.confidence_threshold:
            logger.debug(f"Confidence {confidence:.2f} < {self.config.confidence_threshold}, marking as ambiguous")
            return AIUseStatus.AMBIGUOUS
        return AIUseStatus.PROCESSED