import logging
from typing import Optional
import notion_client as notion_api
from inbox_agent.pydantic_models import (
    NotionTask, AppConfig, AIUseStatus, MetadataResult
)
from inbox_agent.config import settings
from inbox_agent.metadata import MetadataProcessor
from inbox_agent.ranking import RankingProcessor
from inbox_agent.enrichment import EnrichmentProcessor
from inbox_agent.task import TaskManager
from inbox_agent.utils import generate_default_title
from inbox_agent.pydantic_models import DEFAULT_APP_CONFIG
from inbox_agent.setup import build_root_logger

build_root_logger()
logger = logging.getLogger(__name__)

def process_note(note: str, metadata_result: MetadataResult, config: Optional[AppConfig] = None) -> NotionTask:
    """
    Process a single note given its pre-computed metadata.
    Steps 2-5: Ranking, Enrichment, Task Assembly, Notion creation.
    
    Args:
        note: Raw note text
        metadata_result: Pre-computed metadata (classification + project metadata)
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
    
    # Metadata already computed
    logger.info("\n[Step 1/5] Metadata (pre-computed)")
    logger.info("-"*80)
    logger.info(f"Projects: {metadata_result.classification.projects}")
    logger.info(f"Do Now: {metadata_result.classification.do_now}")
    
    # Check DO_NOW bypass
    if metadata_result.classification.do_now:
        logger.info("\nDO_NOW detected - bypassing ranking and enrichment")
        return _create_do_now_task(note, metadata_result, notion_client, config)
    
    # Step 2: Ranking
    logger.info("\n[Step 2/5] Ranking")
    logger.info("-"*80)
    ranking_processor = RankingProcessor(config=config.ranking)
    ranking_result = ranking_processor.process(
        note, 
        metadata_result.project_metadata
    )
    
    logger.info(f"Importance: {ranking_result.importance}/4")
    logger.info(f"Urgency: {ranking_result.urgency}/4")
    logger.info(f"Impact: {ranking_result.impact}/100")
    logger.info(f"Confidence: {ranking_result.confidence:.2f}")
    
    # Step 3: Enrichment (conditional)
    logger.info("\n[Step 3/5] Enrichment")
    logger.info("-"*80)
    enrichment_processor = EnrichmentProcessor(config=config.enrichment)
    enrichment_result = enrichment_processor.process(note, ranking_result.impact)
    
    if enrichment_result:
        logger.info(f"Enrichment generated using lenses: {enrichment_result.lenses_used}")
    else:
        logger.info("Enrichment skipped (impact below threshold)")
    
    # Step 4: Task creation
    logger.info("\n[Step 4/5] Task Assembly")
    logger.info("-"*80)
    task_manager = TaskManager(notion_client, config=config.task)
    
    # ai_use_status determined from ranking confidence
    ai_use_status = task_manager.determine_ai_use_status(ranking_result.confidence)
    logger.info(f"AI Use Status: {ai_use_status}")
    
    task = NotionTask(
        title=ranking_result.title,
        projects=metadata_result.classification.projects,
        do_now=metadata_result.classification.do_now,
        ai_use_status=ai_use_status,
        importance=ranking_result.importance,
        urgency=ranking_result.urgency,
        impact=ranking_result.impact,
        confidence=ranking_result.confidence,
        original_note=note,
        enrichment=enrichment_result.enriched_text if enrichment_result else None
    )
    
    logger.info(f"Task assembled: {task.title}")
    
    # Step 5: Add to Notion
    logger.info("\n[Step 5/5] Adding to Notion")
    logger.info("-"*80)
    page = task_manager.create_task(task)
    if settings.IS_TEST_ENV:
        logger.info(f"TEST mode (dummy LLM): task payload logged to {page['url']}")
    elif settings.IS_DEBUG_ENV:
        logger.info(f"DEBUG mode (real LLM): task payload logged to {page['url']}")
    else:
        logger.info(f"Task created in Notion: {page['url']}")
    
    logger.info("\n" + "="*80)
    logger.info("Processing complete!")
    
    return task

def _create_do_now_task(note: str, metadata_result, notion_client, config: AppConfig) -> NotionTask:
    """Create task for DO_NOW notes (bypass ranking/enrichment)"""
    logger.info("Creating DO_NOW task with max urgency/impact")
    
    # TODO: max is hardcoded. Ok for now. 
    task = NotionTask(
        title=generate_default_title(note),
        do_now=True,  # DO_NOW tasks always have do_now=True
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
    logger.info(f"DO_NOW task created: {page['url']}")
    
    return task

def process_notes(notes: list[str], config: Optional[AppConfig] = None) -> list[tuple[str, Optional[NotionTask], Optional[Exception]]]:
    """
    Process multiple notes: batch metadata classification first, then process each note.
    
    Args:
        notes: List of note texts to process
        config: Application configuration (uses defaults if None)
        
    Returns:
        List of tuples (note_text, task_or_none, exception_or_none) for each note
    """
    config = config or DEFAULT_APP_CONFIG
    
    # Step 1: Batch metadata for all notes
    logger.info(f"\n{'='*80}")
    logger.info(f"[Step 0] Batch metadata classification for {len(notes)} notes")
    logger.info(f"{'='*80}")
    
    notion_client = notion_api.Client(auth=settings.NOTION_TOKEN)
    metadata_processor = MetadataProcessor(notion_client, config=config.metadata)
    metadata_results = metadata_processor.process(notes)
    
    logger.info(f"Metadata classification complete: {len(metadata_results)} results")
    for i, mr in enumerate(metadata_results):
        logger.info(f"  Note {i}: do_now={mr.classification.do_now} -> {mr.classification.projects}")
    
    # Step 2: Process each note with its pre-computed metadata
    results = []
    for i, (note, metadata_result) in enumerate(zip(notes, metadata_results), 1):
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"[{i}/{len(notes)}] Processing note")
            logger.info(f"{'='*80}")
            task = process_note(note, metadata_result, config=config)
            results.append((note, task, None))
            logger.info(f"[{i}/{len(notes)}] Success: {task.title}")
        except Exception as e:
            logger.error(f"[{i}/{len(notes)}] Error: {e}", exc_info=True)
            results.append((note, None, e))
    
    return results

if __name__ == "__main__":
    notes = [
        "Review the latest AI research paper and summarize key findings",
        "Drawing is the way to input more details and more relevant into your explanation. Words are limited to one dimension.",
        "**[DO_NOW]** Fix critical bug in production database",
    ]
    
    config = DEFAULT_APP_CONFIG.model_copy()
    config.metadata.model.model_name = 'gemma-3-27b-it'
    config.ranking.executor_model.model_name = 'gemma-3-27b-it'
    config.enrichment.model.model_name = 'gemma-3-27b-it'
    config.ranking.judge_model.model_name = 'gemini-2.5-flash'
    
    results = process_notes(notes, config=config)
    
    # Summary report
    successful = [r for r in results if r[1] is not None]
    failed = [r for r in results if r[2] is not None]
    
    print(f"\n{'='*80}")
    print(f"Processing Summary")
    print(f"{'='*80}")
    print(f"Total: {len(notes)} notes")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        print(f"\nCreated tasks:")
        for note, task, _ in successful:
            print(f"  • {task.title}")
    
    if failed:
        print(f"\nFailed notes:")
        for note, _, error in failed:
            print(f"  • {note[:50]}... - {str(error)[:50]}")