import logging
import json
from typing import Optional
import openai
from inbox_agent.pydantic_models import (
    RankingResult, BrainstormResult, RankingConfig, ProjectMetadata
)
from inbox_agent.config import settings

logger = logging.getLogger(__name__)

class RankingProcessor:
    """Two-stage ranking: executor brainstorms, judge scores"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.GOOGLE_API_KEY
        )
    
    def process(
        self, 
        note: str, 
        project_metadata: dict[str, ProjectMetadata]
    ) -> RankingResult:
        """
        Main function: receives note and metadata, outputs ranking scores.
        
        Args:
            note: Raw note text
            project_metadata: Metadata for relevant projects
            
        Returns:
            RankingResult with importance, urgency, impact, confidence
        """
        logger.info("Starting ranking process")
        
        # Step 1: Executor brainstorms
        brainstorm = self._brainstorm(note)
        logger.debug(f"Brainstorm: {brainstorm.judgement}, {len(brainstorm.assumptions)} assumptions")
        
        # Step 2: Judge evaluates with full context
        ranking = self._judge_rank(note, project_metadata, brainstorm)
        logger.info(f"Ranking: I={ranking.importance}/4, U={ranking.urgency}/4, Impact={ranking.impact}/100, Conf={ranking.confidence:.2f}")
        
        return ranking
    
    def _brainstorm(self, note: str) -> BrainstormResult:
        """Executor model: roast the note, brainstorm hypotheses"""
        
        prompt = f"""You are a critical thinking assistant. Analyze this note deeply.

Note: "{note}"

Consider:
- What assumptions is the user making?
- What could be the potential impact on progress, productivity, well-being?
- What related important topics should be considered?
- How important is this really?

Think step by step. Validate your reasoning.

Return ONLY valid JSON:
{{
    "assumptions": ["assumption1", "assumption2", "assumption3"],
    "potential_impact": "1-3 sentence assessment",
    "related_topics": ["topic1", "topic2"],
    "judgement": "1 sentence overall judgement of importance (low, medium, high)"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.config.executor_model.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.executor_model.temperature,
                top_p=self.config.executor_model.top_p,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            logger.debug(f"Executor response: {result[:200]}...")
            
            data = json.loads(result)
            return BrainstormResult(**data)
            
        except Exception as e:
            logger.error(f"Brainstorming failed: {e}", exc_info=True)
            # Return default
            return BrainstormResult(
                assumptions=[],
                potential_impact="Unknown",
                related_topics=[],
                judgement="medium"
            )
    
    def _judge_rank(
        self, 
        note: str, 
        project_metadata: dict[str, ProjectMetadata],
        brainstorm: BrainstormResult
    ) -> RankingResult:
        """Judge model: evaluate with full context"""
        
        # Format project metadata
        meta_context = json.dumps(
            {name: meta.dict() for name, meta in project_metadata.items()},
            indent=2
        )
        
        # Format brainstorm
        brainstorm_context = f"""Assumptions: {', '.join(brainstorm.assumptions)}
Potential Impact: {brainstorm.potential_impact}
Related Topics: {', '.join(brainstorm.related_topics)}
Preliminary Judgment: {brainstorm.judgement}"""
        
        prompt = f"""You are a priority assessment expert. Evaluate this note's priority.

Note: "{note}"

Brainstorm Analysis:
{brainstorm_context}

Project Context:
{meta_context}

Evaluate on scales:
- importance (1-4): How critical is this to user's goals?
  1=trivial, 2=moderate, 3=important, 4=critical
- urgency (1-4): How time-sensitive is this?
  1=no deadline, 2=this month, 3=this week, 4=today
- impact (0-100): Estimated % contribution to goals if acted upon. Most notes score 10-30.
- confidence (0.0-1.0): How certain are you of this assessment?

Rules:
- Default to LOW scores unless evidence strongly supports higher
- Urgency is independent of importance
- Most notes are importance=2, urgency=1-2, impact=10-30

Return ONLY valid JSON:
{{
    "importance": 2,
    "urgency": 2,
    "impact": 15,
    "confidence": 0.75,
    "reasoning": "This note addresses X, which is moderately important..."
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.config.judge_model.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.judge_model.temperature,
                top_p=self.config.judge_model.top_p,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            logger.debug(f"Judge response: {result}")
            
            data = json.loads(result)
            return RankingResult(**data)
            
        except Exception as e:
            logger.error(f"Ranking failed: {e}", exc_info=True)
            # Return conservative defaults
            return RankingResult(
                importance=2,
                urgency=1,
                impact=20,
                confidence=0.5,
                reasoning="Error during ranking, using defaults"
            )