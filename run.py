import logging
from pathlib import Path
from typing import Optional
import notion_client as notion_api
from inbox_agent.pydantic_models import (
    NotionTask, AppConfig, ActionType, AIUseStatus
)
from inbox_agent.config import settings
from inbox_agent.metadata import MetadataProcessor
from inbox_agent.ranking import RankingProcessor
from inbox_agent.enrichment import EnrichmentProcessor
from inbox_agent.task import TaskManager
from inbox_agent.utils import generate_default_title
from inbox_agent.pydantic_models import DEFAULT_APP_CONFIG

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/inbox_agent.log'),
        logging.StreamHandler()
    ]
)
logging.getLogger("notion_client").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def process_note(note: str, config: Optional[AppConfig] = None) -> NotionTask:
    """
    Main workflow: orchestrates all modules to process a note.
    
    Args:
        note: Raw note text
        config: Application configuration (uses defaults if None)
        
    Returns:
        NotionTask ready for Notion
    """
    config = config or DEFAULT_APP_CONFIG # Note: avoids early binding
    logger.info("="*80)
    logger.info("Starting note processing workflow")
    logger.info(f"Note: {note[:100]}...")
    
    # Initialize clients
    notion_client = notion_api.Client(auth=settings.NOTION_TOKEN)
    
    # Step 1: Metadata processing
    logger.info("\n[Step 1/5] Metadata Processing")
    logger.info("-"*80)
    metadata_processor = MetadataProcessor(
        notion_client, 
        config=config.metadata
    )
    metadata_result = metadata_processor.process(note)
    
    logger.info(f"✓ Projects: {metadata_result.classification.projects}")
    logger.info(f"✓ Action: {metadata_result.classification.action}")
    logger.info(f"✓ DO_NOW: {metadata_result.is_do_now}")
    
    # Check DO_NOW bypass
    if metadata_result.is_do_now:
        logger.info("\n🚀 DO_NOW detected - bypassing ranking and enrichment")
        return _create_do_now_task(note, metadata_result, notion_client, config)
    
    # Step 2: Ranking
    logger.info("\n[Step 2/5] Ranking")
    logger.info("-"*80)
    ranking_processor = RankingProcessor(config=config.ranking)
    ranking_result = ranking_processor.process(
        note, 
        metadata_result.project_metadata
    )
    
    logger.info(f"✓ Importance: {ranking_result.importance}/4")
    logger.info(f"✓ Urgency: {ranking_result.urgency}/4")
    logger.info(f"✓ Impact: {ranking_result.impact}/100")
    logger.info(f"✓ Confidence: {ranking_result.confidence:.2f}")
    
    # Step 3: Enrichment (conditional)
    logger.info("\n[Step 3/5] Enrichment")
    logger.info("-"*80)
    enrichment_processor = EnrichmentProcessor(config=config.enrichment)
    enrichment_result = enrichment_processor.process(note, ranking_result.impact)
    
    if enrichment_result:
        logger.info(f"✓ Enrichment generated using lenses: {enrichment_result.lenses_used}")
    else:
        logger.info("○ Enrichment skipped (impact below threshold)")
    
    # Step 4: Task creation
    logger.info("\n[Step 4/5] Task Assembly")
    logger.info("-"*80)
    task_manager = TaskManager(notion_client, config=config.task)
    
    # ai_use_status determined from ranking confidence
    ai_use_status = task_manager.determine_ai_use_status(ranking_result.confidence)
    logger.info(f"✓ AI Use Status: {ai_use_status}")
    
    task = NotionTask(
        title=ranking_result.title,
        projects=metadata_result.classification.projects,
        ai_use_status=ai_use_status,
        importance=ranking_result.importance,
        urgency=ranking_result.urgency,
        impact=ranking_result.impact,
        confidence=ranking_result.confidence,
        original_note=note,
        enrichment=enrichment_result.enriched_text if enrichment_result else None
    )
    
    logger.info(f"✓ Task assembled: {task.title}")
    
    # Step 5: Add to Notion
    logger.info("\n[Step 5/5] Adding to Notion")
    logger.info("-"*80)
    page = task_manager.create_task(task)
    logger.info(f"✓ Task created in Notion: {page['url']}")
    
    logger.info("\n" + "="*80)
    logger.info("Processing complete!")
    
    return task

def _create_do_now_task(note: str, metadata_result, notion_client, config: AppConfig) -> NotionTask:
    """Create task for DO_NOW notes (bypass ranking/enrichment)"""
    logger.info("Creating DO_NOW task with max urgency/impact")
    
    # TODO: max is hardcoded. Ok for now. 
    task = NotionTask(
        title=generate_default_title(note),
        projects=metadata_result.classification.projects,
        ai_use_status=AIUseStatus.PROCESSED,  # DO_NOW always marked as processed
        importance=4,  # Max
        urgency=4,     # Max
        impact=100,    # Max
        confidence=metadata_result.classification.confidence_scores[0],
        original_note=note,
        enrichment=None
    )
    
    task_manager = TaskManager(notion_client, config=config.task)
    page = task_manager.create_task(task)
    logger.info(f"✓ DO_NOW task created: {page['url']}")
    
    return task

if __name__ == "__main__":
    note = """
Clarifying the problem, planning when building projects: should you spend time here? How much? 
Maybe, the right way is executing, "just doing it"?
"""
    config = DEFAULT_APP_CONFIG.model_copy()
    config.metadata.model.model_name = 'gemma-3-27b-it'
    config.ranking.executor_model.model_name = 'gemma-3-27b-it'
    config.enrichment.model.model_name = 'gemma-3-27b-it'
    config.ranking.judge_model.model_name = 'gemini-2.5-flash'
    
    try:
        task = process_note(note, config=config)
        print(f"\n✅ Success! Task created: {task.title}")
    except Exception as e:
        logger.error(f"❌ Failed to process note: {e}", exc_info=True)