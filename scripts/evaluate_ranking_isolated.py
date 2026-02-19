"""
Isolated Ranking Evaluation Script

Evaluates ranking performance in isolation from metadata by:
1. Loading ground truth notes from debug tasks
2. Using real projects from Notion tasks (no LLM classification)
3. Running ranking with ground-truth metadata
4. Saving only ranking outputs for comparison

Usage:
    python scripts/evaluate_ranking_isolated.py
"""
import json
import logging
from pathlib import Path
import sys

import notion_client as notion_api

from inbox_agent.config import settings
from inbox_agent.ranking import RankingProcessor
from inbox_agent.metadata import MetadataProcessor
from inbox_agent.pydantic_models import DEFAULT_APP_CONFIG
from inbox_agent.utils import load_tasks_from_json
from inbox_agent.setup import build_root_logger

build_root_logger()
logger = logging.getLogger(__name__)

# Global variable for evaluation directory
EVAL_DIR_PATH = settings.PROJ_ROOT / "logs" / "eval_2"


def evaluate_ranking_isolated(eval_dir: Path, config=None) -> list[dict]:
    """
    Evaluate ranking in isolation using real projects from Notion tasks.
    
    This bypasses metadata classification and uses ground-truth projects
    to isolate ranking performance from metadata performance.
    
    Args:
        eval_dir: Path to evaluation directory containing debug_tasks.json and notion_tasks.json
        config: Optional AppConfig (uses defaults if None)
    
    Returns:
        List of ranking results (title, importance, urgency, impact, confidence, reasoning)
    """
    config = config or DEFAULT_APP_CONFIG
    
    # Load ground truth data
    logger.info(f"Loading data from {eval_dir}")
    debug_file = eval_dir / "debug_tasks.json"
    notion_file = eval_dir / "notion_tasks.json"
    
    if not debug_file.exists():
        raise FileNotFoundError(f"Debug tasks file not found: {debug_file}")
    if not notion_file.exists():
        raise FileNotFoundError(f"Notion tasks file not found: {notion_file}")
    
    debug_tasks = load_tasks_from_json(debug_file)
    notion_tasks = load_tasks_from_json(notion_file)
    
    # Create mapping of title -> notion task
    notion_by_title = {task['title']: task for task in notion_tasks if task.get('title')}
    
    # Initialize Notion client and processors
    notion_client = notion_api.Client(auth=settings.NOTION_TOKEN)
    metadata_processor = MetadataProcessor(notion_client, config=config.metadata)
    ranking_processor = RankingProcessor(config=config.ranking)
    
    results = []
    matched_count = 0
    
    for debug_task in debug_tasks:
        title = debug_task.get('title')
        original_note = debug_task.get('original_note')
        
        if not title or not original_note:
            logger.warning(f"Skipping task with missing title or note")
            continue
        
        # Find corresponding notion task to get real projects
        notion_task = notion_by_title.get(title)
        if not notion_task:
            logger.warning(f"No matching Notion task for: {title}")
            continue
        
        real_projects = notion_task.get('projects', [])
        if not real_projects:
            logger.debug(f"No projects found for: {title}")

        matched_count += 1
        
        # Fetch metadata for real projects (isolated: no LLM classification)
        project_metadata = metadata_processor._fetch_project_metadata(real_projects)
        
        # Run ranking with ground-truth projects
        logger.info(f"Ranking [{matched_count}]: {title}")
        ranking_result = ranking_processor.process(original_note, project_metadata)
        
        # Save only ranking outputs (not ground truth or projects)
        results.append({
            'id': debug_task.get('id'),  # Use debug task ID for traceability
            'title': title, # Have to reuse debug task title since I use titles to match notes
            'importance': ranking_result.importance,
            'urgency': ranking_result.urgency,
            'impact': ranking_result.impact,
            'confidence': ranking_result.confidence,
            'reasoning': ranking_result.reasoning
        })
    
    logger.info(f"Completed ranking for {matched_count}/{len(debug_tasks)} tasks")
    return results


def save_ranking_results(results: list[dict], eval_dir: Path):
    """Save ranking results to JSON file in eval directory."""
    output_file = eval_dir / "ranking_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(results)} ranking results to {output_file}")


if __name__ == "__main__":
    # Run isolated ranking evaluation
    eval_dir = EVAL_DIR_PATH
    
    config = DEFAULT_APP_CONFIG.model_copy()
    config.ranking.executor_model.model_name = 'gemma-3-12b-it'
    config.ranking.judge_model.model_name = 'gemma-3-27b-it'
    
    logger.info("="*60)
    logger.info("ISOLATED RANKING EVALUATION")
    logger.info("="*60)
    logger.info(f"Evaluation directory: {eval_dir}")
    
    results = evaluate_ranking_isolated(eval_dir, config=config)
    save_ranking_results(results, eval_dir)
    
    logger.info("="*60)
    logger.info("EVALUATION COMPLETE")
    logger.info("="*60)
