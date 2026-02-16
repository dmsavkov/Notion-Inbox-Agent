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
    """Handles project classification and metadata fetching for batches of notes."""
    
    def __init__(
        self, 
        notion_client,
        config: Optional[MetadataConfig] = None
    ):
        self.notion_client = notion_client
        self.config = config or MetadataConfig()
    
    def process(self, notes: list[str]) -> list[MetadataResult]:
        """
        Classify a list of notes in batches, fetch project metadata, return results.
        
        Args:
            notes: List of raw note texts
            
        Returns:
            List of MetadataResult, one per note (same order as input)
        """
        logger.info(f"Starting metadata processing for {len(notes)} notes")
        
        # Fetch projects once for all batches
        projects_info = self._get_projects_information()
        
        # Classify all notes in batches
        all_classifications = self._classify_notes_batched(notes, projects_info)
        
        # Collect unique project names across all classifications
        unique_projects = set()
        for classification in all_classifications:
            unique_projects.update(classification.projects)
        
        # Fetch metadata once for all referenced projects
        project_metadata = self._fetch_project_metadata(list(unique_projects))
        logger.debug(f"Fetched metadata for {len(project_metadata)} unique projects")
        
        # Build per-note MetadataResult
        results = []
        for classification in all_classifications:
            # Filter project metadata to only this note's projects
            note_metadata = {
                name: project_metadata[name] 
                for name in classification.projects 
                if name in project_metadata
            }
            
            is_do_now = self._is_do_now(classification)
            if is_do_now:
                logger.info(f"Note {classification.note_id} classified as DO_NOW")
            
            results.append(MetadataResult(
                classification=classification,
                project_metadata=note_metadata,
                is_do_now=is_do_now
            ))
        
        return results
    
    def _classify_notes_batched(self, notes: list[str], projects_info: str) -> list[NoteClassification]:
        """Classify notes in batches of config.batch_size via single LLM calls."""
        batch_size = self.config.batch_size
        all_classifications = []
        
        for batch_start in range(0, len(notes), batch_size):
            batch = notes[batch_start:batch_start + batch_size]
            batch_indices = list(range(batch_start, batch_start + len(batch)))
            
            logger.info(f"Classifying batch of {len(batch)} notes (indices {batch_indices[0]}-{batch_indices[-1]})")
            
            classifications = self._classify_batch(batch, batch_indices, projects_info)
            all_classifications.extend(classifications)
        
        return all_classifications
    
    def _classify_batch(self, batch: list[str], indices: list[int], projects_info: str) -> list[NoteClassification]:
        """Classify a single batch of notes in one LLM call."""
        
        system_prompt = """You are an AI Classification Engine.
        
Task:
1. Semantic analysis: Extract core topic, keywords, entities for EACH note
2. Project mapping: Match each note to top-3 relevant project titles
3. Action classification: Determine cognitive state (DO_NOW/REFINE/EXECUTE)
4. Confidence scoring: Assign calibrated scores [0.0-1.0]

You will classify multiple notes in a single request. Process each independently.
Output strict JSON format."""

        # Build notes section
        notes_section = ""
        for idx, note_text in zip(indices, batch):
            notes_section += f"Note {idx}: {note_text}\n\n"

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

<notes_to_classify>
{notes_section}</notes_to_classify>

Return ONLY valid JSON. You MUST return exactly {len(batch)} classifications, one per note, in the same order.
{{
    "classifications": [
        {{
            "note_id": <index>,
            "projects": ["project1", "project2", "project3"],
            "action": "DO_NOW|REFINE|EXECUTE",
            "reasoning": "brief explanation",
            "confidence_scores": [0.95, 0.85, 0.70]
        }}
    ]
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
            
            logger.debug(f"LLM batch classification response: {data}")
            
            # Handle both formats: {"classifications": [...]} or direct list
            raw_classifications = data.get("classifications", data) if isinstance(data, dict) else data
            
            results = []
            for item in raw_classifications:
                results.append(NoteClassification(
                    note_id=item.get("note_id", 0),
                    projects=item["projects"][:self.config.top_n_projects],
                    action=ActionType(item["action"]),
                    reasoning=item["reasoning"],
                    confidence_scores=item["confidence_scores"][:self.config.top_n_projects]
                ))
            
            # Ensure we got the right number of classifications
            if len(results) != len(batch):
                logger.warning(
                    f"Expected {len(batch)} classifications, got {len(results)}. "
                    f"Padding missing entries."
                )
                raise ValueError("LLM did not return expected number of classifications.")
                while len(results) < len(batch):
                    results.append(NoteClassification(
                        note_id=indices[len(results)],
                        projects=["Inbox"],
                        action=ActionType.REFINE,
                        reasoning="Fallback: LLM did not return classification for this note.",
                        confidence_scores=[0.5]
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Batch classification failed: {e}", exc_info=True)
            raise
    
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
        return classification.action == ActionType.DO_NOW