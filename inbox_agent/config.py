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
    
    # AI
    GOOGLE_API_KEY: str = Field(..., env="GOOGLE_API_KEY")
    
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
    
    # Load .env file
    model_config = ConfigDict(
        env_file=PROJ_ROOT / ".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()


