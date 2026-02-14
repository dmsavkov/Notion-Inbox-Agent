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
            # ELABORATION PAGE USED FOR NOW. SHOULD BE TASK DB WITH RELATION TO PROJECTS LATER
            page = self.notion_client.pages.create(
                parent={"page_id": settings.NOTION_ELABORATION_PAGE_ID},
                properties=properties,
                children=children
            )
            
            logger.info(f"Task created successfully: {page['id']}")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}", exc_info=True)
            raise
    
    def _build_properties(self, task: NotionTask) -> dict:
        """Build Notion properties dict"""
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
            "AI Use": {
                "select": {
                    "name": task.ai_use_status.value
                }
            },
            "Importance": {
                "number": task.importance
            },
            "Urgency": {
                "number": task.urgency
            },
            "Impact": {
                "number": task.impact
            },
            "Confidence": {
                "number": task.confidence
            }
        }
        
        # Add projects as relation (if field exists)
        if task.projects:
            # Query project IDs
            project_ids = []
            for project_name in task.projects:
                try:
                    results = self.notion_client.databases.query(
                        database_id=settings.NOTION_DATA_SOURCE_ID,
                        filter={
                            "property": "Name",
                            "title": {"equals": project_name}
                        }
                    )
                    if results["results"]:
                        project_ids.append({"id": results["results"][0]["id"]})
                except Exception as e:
                    logger.warning(f"Could not find project {project_name}: {e}")
            
            if project_ids:
                properties["Projects"] = {
                    "relation": project_ids
                }
        
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
        
        # Metadata callout
        metadata_text = f"""
**Confidence**: {task.confidence:.2f}"""
        
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