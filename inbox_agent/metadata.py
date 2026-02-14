import logging
from typing import Optional
import json
from inbox_agent.pydantic_models import (
    MetadataResult, NoteClassification, ProjectMetadata, 
    MetadataConfig, ModelConfig, ActionType
)
from inbox_agent.config import settings
from inbox_agent.notion import get_all_pages, get_block_plain_text

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
            projects_pages = get_all_pages(self.notion_client, settings.NOTION_DATA_SOURCE_ID)
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
            response = client.chat.completions.create(
                model=self.config.model.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.model.temperature,
                top_p=self.config.model.top_p,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            logger.debug(f"LLM classification response: {result}")
            
            data = json.loads(result)
            
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
        
        for project_name in project_names:
            try:
                # Query Notion for project page
                results = self.notion_client.databases.query(
                    database_id=settings.NOTION_DATA_SOURCE_ID,
                    filter={
                        "property": "Name",
                        "title": {
                            "equals": project_name
                        }
                    }
                )
                
                if not results["results"]:
                    logger.warning(f"Project not found: {project_name}")
                    continue
                
                page = results["results"][0]
                props = page["properties"]
                
                # Extract only non-empty fields
                project_meta = ProjectMetadata(
                    name=project_name,
                    priority=self._extract_select(props.get("Priority")),
                    status=self._extract_status(props.get("Status")),
                    types=self._extract_multi_select(props.get("Type")),
                    urgency=self._extract_number(props.get("Urgency")),
                    importance=self._extract_number(props.get("Importance"))
                )
                
                # Remove None fields to minimize context
                metadata[project_name] = ProjectMetadata(
                    **{k: v for k, v in project_meta.dict().items() if v is not None and v != [] and v != ""}
                )
                
                logger.debug(f"Fetched metadata for {project_name}: {list(metadata[project_name].dict().keys())}")
                
            except Exception as e:
                logger.error(f"Failed to fetch metadata for {project_name}: {e}")
        
        return metadata
    
    def _extract_select(self, prop) -> Optional[str]:
        """Extract select property value"""
        if prop and prop.get("select"):
            return prop["select"].get("name")
        return None
    
    def _extract_status(self, prop) -> Optional[str]:
        """Extract status property value"""
        if prop and prop.get("status"):
            return prop["status"].get("name")
        return None
    
    def _extract_multi_select(self, prop) -> list[str]:
        """Extract multi-select property values"""
        if prop and prop.get("multi_select"):
            return [item["name"] for item in prop["multi_select"]]
        return []
    
    def _extract_number(self, prop) -> Optional[int]:
        """Extract number property value"""
        if prop and prop.get("number") is not None:
            return int(prop["number"])
        return None
    
    def _is_do_now(self, classification: NoteClassification) -> bool:
        """Determine if note is DO_NOW based on action and confidence"""
        return (
            classification.action == ActionType.DO_NOW 
            and classification.confidence_scores[0] >= self.config.do_now_threshold
        )