import logging
import json
import re
from datetime import datetime
from pathlib import Path
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
        properties = self._build_properties(task, include_relations=not settings.IS_TEST_ENV)
        
        # Build content blocks
        children = self._build_content_blocks(task)

        if settings.IS_TEST_ENV:
            self._validate_task_payload(properties, children)
            debug_file = self._write_debug_task_markdown(task, properties, children)
            logger.info(f"TEST mode: task inspected and written to {debug_file}")
            return {
                "id": f"debug-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "url": str(debug_file),
                "properties": properties,
                "children": children,
                "object": "debug_task"
            }
        
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
    
    def _build_properties(self, task: NotionTask, include_relations: bool = True) -> dict:
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
        if include_relations and task.projects:
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

    def _validate_task_payload(self, properties: dict, children: list[dict]) -> None:
        """Basic payload validation for TEST mode inspection."""
        required_properties = ["Name", "Importance", "Urgency", "Impact Score", "UseAIStatus", "Status"]
        missing = [prop for prop in required_properties if prop not in properties]
        if missing:
            raise ValueError(f"Missing required properties: {missing}")

        if not children:
            raise ValueError("Task content blocks are empty")

        if properties["Name"].get("title") is None:
            raise ValueError("Name.title is missing")

    def _write_debug_task_markdown(self, task: NotionTask, properties: dict, children: list[dict]) -> Path:
        """Write TEST-mode task payload to logs/debug_tasks/<title>.md."""
        settings.DEBUG_TASKS_DIR.mkdir(parents=True, exist_ok=True)

        safe_title = re.sub(r"[^a-zA-Z0-9 _-]", "", task.title).strip().replace(" ", "_")
        if not safe_title:
            safe_title = "untitled_task"

        file_path = settings.DEBUG_TASKS_DIR / f"{safe_title}.md"
        if file_path.exists():
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = settings.DEBUG_TASKS_DIR / f"{safe_title}_{suffix}.md"

        content = [
            f"# {task.title}",
            "",
            f"- Created (debug): {datetime.now().isoformat()}",
            f"- Environment: {settings.RUNTIME_MODE}",
            "",
            "## Task Model",
            "```json",
            json.dumps(task.model_dump(), indent=2, ensure_ascii=False),
            "```",
            "",
            "## Notion Properties Payload",
            "```json",
            json.dumps(properties, indent=2, ensure_ascii=False),
            "```",
            "",
            "## Notion Children Payload",
            "```json",
            json.dumps(children, indent=2, ensure_ascii=False),
            "```",
        ]

        file_path.write_text("\n".join(content), encoding="utf-8")
        return file_path
    
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