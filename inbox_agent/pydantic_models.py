from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
from enum import Enum
import openai

from inbox_agent.config import settings


'''class NoteClassification(BaseModel):
    """Single note classification with project, action, reasoning, and confidence."""
    note_id: int = Field(..., description="Index of the note in the batch")
    projects: list[str] = Field(..., description="Top 3 most relevant project titles in ranked order")
    action: Literal["DO_NOW", "REFINE", "EXECUTE"] = Field(
        ..., 
        description="Action property: DO_NOW (immediate task), REFINE (requires thinking), EXECUTE (reference material)"
    )
    reasoning: str = Field(..., description="Brief explanation of classification logic")
    confidence_scores: list[float] = Field(..., description="Confidence scores for top 3 projects (0-1)")


class BatchNoteClassification(BaseModel):
    """Batch classification result for multiple notes."""
    classifications: list[NoteClassification] = Field(
        ..., 
        description="List of classifications, one per input note"
    )'''

# Action types
# REFACTORING TYPE?
class ActionType(str, Enum):
    DO_NOW = "DO_NOW"
    REFINE = "REFINE"
    EXECUTE = "EXECUTE"

class AIUseStatus(str, Enum):
    PROCESSED = "processed"
    AMBIGUOUS = "ambiguous"

# ========== Configuration Models ==========

class OpenAIClientConfig(BaseModel):
    """OpenAI client connection configuration"""
    base_url: str = settings.GEMINI_API_BASE_URL
    api_key: str = settings.GOOGLE_API_KEY
    max_retries: int = 1
    timeout: float = 60.0

class ModelConfig(BaseModel):
    """LLM model configuration"""
    model_name: str = "gemma-3-27b-it"
    temperature: float = 0.5
    top_p: float = 0.9
    reasoning_effort: Optional[str] = None
    client_config: OpenAIClientConfig = Field(default_factory=lambda: OpenAIClientConfig())
    
    def get_client(self) -> openai.OpenAI:
        """Instantiate OpenAI client based on configuration"""
        return openai.OpenAI(
            base_url=self.client_config.base_url,
            api_key=self.client_config.api_key,
            max_retries=self.client_config.max_retries,
            timeout=self.client_config.timeout
        )

class MetadataConfig(BaseModel):
    """Configuration for metadata module"""
    top_n_projects: int = 3
    project_confidence_threshold: float = 0.85
    do_now_threshold: float = 0.9
    batch_size: int = 5
    model: ModelConfig = Field(default_factory=lambda: ModelConfig(
        model_name="gemma-3-27b-it",
        temperature=1,
        top_p=0.9
    ))

class RankingConfig(BaseModel):
    """Configuration for ranking module"""
    executor_model: ModelConfig = Field(default_factory=lambda: ModelConfig(
        model_name="gemma-3-27b-it",
        temperature=1.0,
        top_p=1.0
    ))
    judge_model: ModelConfig = Field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        temperature=0.5,
        top_p=0.9,
        reasoning_effort="high"
    ))
    importance_scale: tuple[int, int] = (1, 4)
    urgency_scale: tuple[int, int] = (1, 4)
    impact_scale: tuple[int, int] = (0, 100)

class EnrichmentConfig(BaseModel):
    """Configuration for enrichment module"""
    impact_threshold: int = 15
    model: ModelConfig = Field(default_factory=lambda: ModelConfig(
        model_name="gemini-2.5-flash",
        temperature=0.7,
        top_p=0.9
    ))
    max_length: int = 300  # words

class TaskConfig(BaseModel):
    """Configuration for task creation"""
    confidence_threshold: float = 0.9  # below this = ambiguous

class AppConfig(BaseModel):
    """Root configuration for the entire application"""
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    task: TaskConfig = Field(default_factory=TaskConfig)

# ========== Data Models ==========

class ProjectMetadata(BaseModel):
    """Metadata for a single project"""
    name: str
    priority: Optional[str] = None
    status: Optional[str] = None
    types: list[str] = []
    description: Optional[str] = None
    urgency: Optional[int] = None
    importance: Optional[int] = None
    # Only include non-empty fields

class NoteClassification(BaseModel):
    """Classification result from metadata module"""
    note_id: int
    projects: list[str]
    action: ActionType
    reasoning: str
    confidence_scores: list[float]

class MetadataResult(BaseModel):
    """Output from metadata.py"""
    classification: NoteClassification
    project_metadata: dict[str, ProjectMetadata]
    is_do_now: bool

class BrainstormResult(BaseModel):
    """Executor model brainstorming output"""
    assumptions: list[str]
    potential_impact: str
    related_topics: list[str]
    judgement: str

# PUT NUMBERS INTO FIELDS
class RankingResult(BaseModel):
    """Judge model ranking output"""
    title: str       # Task title (concise, representative)
    importance: int  # 1-4
    urgency: int     # 1-4
    impact: int      # 0-100
    confidence: float  # 0.0-1.0
    reasoning: str

class EnrichmentResult(BaseModel):
    """Enrichment module output"""
    enriched_text: str  # BLUF formatted text from selected lenses
    lenses_used: list[str]  # Which 2 lenses were selected

class NotionTask(BaseModel):
    """Complete task ready for Notion"""
    title: str
    projects: list[str]
    ai_use_status: AIUseStatus
    importance: int
    urgency: int
    impact: int
    confidence: Optional[float] = None  # Optional; empty by default
    original_note: str
    enrichment: Optional[str] = None
    
DEFAULT_APP_CONFIG = AppConfig()
