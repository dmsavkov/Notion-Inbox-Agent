import logging
from typing import Optional
from inbox_agent.pydantic_models import EnrichmentResult, EnrichmentConfig
from inbox_agent.utils import call_llm_with_json_response

logger = logging.getLogger(__name__)

class EnrichmentProcessor:
    """Enriches high-impact notes using analytical lenses"""
    
    LENSES = {
        "A": "First Principles: Strip this idea down to its fundamental truths. What are the physics, not the opinions?",
        "B": "Inversion (Pre-Mortem): Assume this project failed. Why did it fail?",
        "C": "The 80/20 Rule: What is the single sub-task here that delivers 80% of the value? Delete the rest.",
        "D": "The Devil's Advocate: Give me one brutal reason why this is a waste of time."
    }
    
    def __init__(self, config: Optional[EnrichmentConfig] = None):
        self.config = config or EnrichmentConfig()
    
    def process(self, note: str, impact_score: int) -> Optional[EnrichmentResult]:
        """
        Main function: receives note and impact, returns enrichment or None.
        
        Args:
            note: Raw note text
            impact_score: Impact score from ranking
            
        Returns:
            EnrichmentResult or None if impact < threshold
        """
        if impact_score < self.config.impact_threshold:
            logger.info(f"Impact {impact_score} < {self.config.impact_threshold}, skipping enrichment")
            return None
        
        logger.info(f"Starting enrichment (impact={impact_score})")
        
        # LLM selects and applies 2 lenses
        result = self._enrich_note(note)
        logger.info(f"Enrichment complete, used lenses: {result.lenses_used}")
        
        return result
    
    def _enrich_note(self, note: str) -> EnrichmentResult:
        """Apply 4 lenses, select 2 best (impactful + counterintuitive)"""
        
        lenses_desc = "\n".join([f"Lens {k}: {v}" for k, v in self.LENSES.items()])
        
        prompt = f"""You are an analytical thinking engine. Examine this note through 4 orthogonal lenses:

{lenses_desc}

Note: "{note}"

Your task:
1. Apply ALL 4 lenses mentally
2. Select ONLY 2 lenses: the most IMPACTFUL and the most COUNTER-INTUITIVE/SURPRISING
3. For each selected lens, provide BLUF (Bottom Line Up Front) analysis
4. Maximum {self.config.max_length} words total
5. NO fluffy words, strictly on point, concise

Format:
**[LENS X]**: [BLUF analysis in 2-3 sentences]
**[LENS Y]**: [BLUF analysis in 2-3 sentences]

Return ONLY valid JSON:
{{
    "lenses_used": ["A", "C"],
    "enriched_text": "**[LENS A]**: Core truth is... **[LENS C]**: The 20% task that delivers 80% value is..."
}}"""

        try:
            client = self.config.model.get_client()
            
            data = call_llm_with_json_response(
                client=client,
                model_config=self.config.model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            logger.debug(f"Enrichment response: {str(data)[:200]}...")
            
            return EnrichmentResult(
                lenses_used=data["lenses_used"],
                enriched_text=data["enriched_text"]
            )
            
        except Exception as e:
            logger.error(f"Enrichment failed: {e}", exc_info=True)
            return EnrichmentResult(
                lenses_used=[],
                enriched_text=""
            )