import logging
from typing import Optional
from inbox_agent.pydantic_models import (
    MetadataResult, NoteClassification, ProjectMetadata, 
    MetadataConfig, ModelConfig, ActionType
)
from inbox_agent.config import settings
from inbox_agent.notion import get_all_pages, get_block_plain_text, extract_property_value
from inbox_agent.utils import call_llm_with_json_response
import json

logger = logging.getLogger(__name__)

class MetadataProcessor:
    """Handles project classification and metadata fetching"""
    
    def __init__(
        self, 
        notion_client,
        config: Optional[MetadataConfig] = None
    ):
        self.notion_client = notion_client
        self.config = config or MetadataConfig()
    
    def process(self, note: str) -> MetadataResult:
        """
        Main function: receives note, outputs projects metadata + urgency classification.
        
        Args:
            note: Raw note text
            
        Returns:
            MetadataResult with classification and project metadata
        """
        logger.info("Starting metadata processing for note")
        logger.debug(f"Note: {note[:100]}...")
        
        projects_info = self._get_projects_information()
        
        # Step 1: Classify note
        classification = self._classify_note(note, projects_info)
        logger.info(f"Classification: {classification.action}, Projects: {classification.projects}")
        
        # Step 2: Fetch metadata for top N projects
        project_metadata = self._fetch_project_metadata(classification.projects)
        logger.debug(f"Fetched metadata for {len(project_metadata)} projects")
        
        # Step 3: Determine if DO_NOW
        is_do_now = self._is_do_now(classification)
        if is_do_now:
            logger.info("Note classified as DO_NOW - will skip ranking/enrichment")
        
        return MetadataResult(
            classification=classification,
            project_metadata=project_metadata,
            is_do_now=is_do_now
        )
    
    def _get_projects_information(self) -> str:
        """
        Query Notion Projects database and return all project titles as JSON.
        
        Returns:
            JSON string of project titles
        """
        try:
            projects_pages = get_all_pages(self.notion_client, settings.NOTION_PROJECTS_DATA_SOURCE_ID)
            logger.debug(f"Retrieved {len(projects_pages)} project pages from Notion")
            
            all_titles = [
                get_block_plain_text(p) for p in projects_pages
            ]
            
            logger.debug(f"Extracted {len(all_titles)} project titles")
            return json.dumps(all_titles)
            
        except Exception as e:
            logger.error(f"Failed to fetch projects information: {e}", exc_info=True)
            raise
    
    def _classify_note(self, note: str, projects_info: str) -> NoteClassification:
        """Classify note using LLM - determines top N projects and action property"""
        
        system_prompt = """You are an AI Classification Engine.
        
Task:
1. Semantic analysis: Extract core topic, keywords, entities
2. Project mapping: Match to top-3 relevant project titles
3. Action classification: Determine cognitive state (DO_NOW/REFINE/EXECUTE)
4. Confidence scoring: Assign calibrated scores [0.0-1.0]

Output strict JSON format."""

        user_prompt = f"""<projects>
{projects_info}
</projects>

<action_definitions>
DO_NOW: Atomic execution tasks (2-10 min). Physical verbs, clear deliverable, binary completion.
  Examples: "Create list", "Fix bug", "Update docs"

REFINE: Semi-processed insights requiring synthesis. Lessons, principles, habits to internalize.
  Examples: "Practice ego detachment", "Build habit of code review"

EXECUTE: Fully processed reference material. Curated resources for later consumption.
  Examples: "Article on microservices", "Video series on Kubernetes"
</action_definitions>

<note>
{note}
</note>

Return ONLY valid JSON:
{{
    "note_id": 0,
    "projects": ["project1", "project2", "project3"],
    "action": "DO_NOW|REFINE|EXECUTE",
    "reasoning": "brief explanation",
    "confidence_scores": [0.95, 0.85, 0.70]
}}"""

        try:
            client = self.config.model.get_client()
            
            data = call_llm_with_json_response(
                client=client,
                model_config=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            logger.debug(f"LLM classification response: {data}")
            
            return NoteClassification(
                note_id=data.get("note_id", 0),
                projects=data["projects"][:self.config.top_n_projects],
                action=ActionType(data["action"]),
                reasoning=data["reasoning"],
                confidence_scores=data["confidence_scores"][:self.config.top_n_projects]
            )
            
        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            raise
    
    def _fetch_project_metadata(self, project_names: list[str]) -> dict[str, ProjectMetadata]:
        """Fetch and preprocess metadata for projects"""
        metadata = {}
        
        # Get all project pages from data source
        try:
            # Putting try except pollutes the implementation code, so it may be better to ues it here
            all_project_pages = get_all_pages(self.notion_client, settings.NOTION_PROJECTS_DATA_SOURCE_ID)
        except Exception as e:
            logger.error(f"Failed to fetch projects from data source: {e}", exc_info=True)
            return metadata
        
        # Build a map of project titles to pages for quick lookup
        project_map = {}
        for page in all_project_pages:
            page_title = get_block_plain_text(page)
            if page_title:
                project_map[page_title] = page
        
        # Extract metadata for requested projects
        for project_name in project_names:
            try:
                if project_name not in project_map:
                    logger.warning(f"Project not found: {project_name}")
                    continue
                
                page = project_map[project_name]
                props = page.get("properties", {})
                
                # Extract properties using unified function from notion.py
                # extract_property_value handles all property type conversions
                types_val = extract_property_value(props.get("Type"))
                if not isinstance(types_val, list):
                    types_val = []
                
                project_meta = ProjectMetadata(
                    name=project_name,
                    priority=extract_property_value(props.get("Priority")),  # type: ignore
                    status=extract_property_value(props.get("Status")),  # type: ignore
                    types=types_val,  # type: ignore
                )
                
                # Remove None and empty fields to minimize context
                metadata[project_name] = ProjectMetadata(
                    **{k: v for k, v in project_meta.dict().items() if v is not None and v != [] and v != ""}
                )
                
                logger.debug(f"Fetched metadata for {project_name}: {list(metadata[project_name].dict().keys())}")
                
            except Exception as e:
                logger.error(f"Failed to extract metadata for {project_name}: {e}")
        
        return metadata
    
    def _is_do_now(self, classification: NoteClassification) -> bool:
        """Determine if note is DO_NOW based on action"""
        return (
            classification.action == ActionType.DO_NOW 
        )