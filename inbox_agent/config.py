from pathlib import Path
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Paths
    PROJ_ROOT: Path = Path(__file__).resolve().parents[1]
    
    # Notion API Configuration
    NOTION_TOKEN: str
    NOTION_PROJECTS_DATABASE_ID: str
    NOTION_PROJECTS_DATA_SOURCE_ID: str
    NOTION_TASKS_DATABASE_ID: str
    NOTION_TASKS_DATA_SOURCE_ID: str
    NOTION_INBOX_PAGE_ID: str

    # Runtime mode
    RUNTIME_MODE: str = "PROD"
    
    # AI
    GOOGLE_API_KEY: str = Field(..., env="GOOGLE_API_KEY")
    GEMINI_API_BASE_URL: str = Field(..., default_factory=lambda: "https://generativelanguage.googleapis.com/v1beta/openai/", env="GEMINI_API_BASE_URL")
    
    @property
    def DATA_DIR(self) -> Path:
        return self.PROJ_ROOT / "data"
    
    @property
    def RAW_DATA_DIR(self) -> Path:
        return self.DATA_DIR / "raw"
    
    @property
    def PROCESSED_DATA_DIR(self) -> Path:
        return self.DATA_DIR / "processed"
    
    @property
    def NOTEBOOKS_DIR(self) -> Path:
        return self.PROJ_ROOT / "notebooks"
    
    @property
    def MODELS_DIR(self) -> Path:
        return self.PROJ_ROOT / "models"

    @property
    def LOGS_DIR(self) -> Path:
        return self.PROJ_ROOT / "logs"
    
    @property
    def RESULTS_DIR(self) -> Path:
        return self.PROJ_ROOT / "output" / "results"

    @property
    def DEBUG_TASKS_DIR(self) -> Path:
        return self.LOGS_DIR / "debug_tasks"

    @property
    def IS_TEST_ENV(self) -> bool:
        return self.RUNTIME_MODE.upper() == "TEST"
    
    @property
    def IS_DEBUG_ENV(self) -> bool:
        return self.RUNTIME_MODE.upper() == "DEBUG"
    
    @property
    def IS_EVAL_ENV(self) -> bool:
        return self.RUNTIME_MODE.upper() == "EVAL"
    
    # Load .env file
    model_config = ConfigDict(
        env_file=PROJ_ROOT / ".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()


