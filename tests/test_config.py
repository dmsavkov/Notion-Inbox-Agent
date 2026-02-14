import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from inbox_agent.config import Settings, settings
import logging

logger = logging.getLogger(__name__)


class TestSettings:
    """Tests for Settings configuration class."""
    
    def test_settings_load_from_env(self):
        """Test that settings load from environment variables."""
        with patch.dict('os.environ', {
            'NOTION_TOKEN': 'test_token_123',
            'NOTION_DATABASE_ID': 'db_123',
            'NOTION_PROJECTS_DATA_SOURCE_ID': 'ds_123',
            'NOTION_INBOX_PAGE_ID': 'page_123'
        }):
            test_settings = Settings()
            
            assert test_settings.NOTION_TOKEN == 'test_token_123'
            assert test_settings.NOTION_DATABASE_ID == 'db_123'
            assert test_settings.NOTION_PROJECTS_DATA_SOURCE_ID == 'ds_123'
            assert test_settings.NOTION_INBOX_PAGE_ID == 'page_123'
    
    def test_proj_root_path(self):
        """Test that PROJ_ROOT resolves correctly."""
        assert settings.PROJ_ROOT.exists()
        assert settings.PROJ_ROOT.is_dir()
        assert (settings.PROJ_ROOT / 'inbox_agent').exists()
    
    def test_data_dir_path(self):
        """Test that DATA_DIR property works correctly."""
        data_dir = settings.DATA_DIR
        
        assert isinstance(data_dir, Path)
        assert data_dir.name == 'data'
        assert data_dir.parent == settings.PROJ_ROOT
        assert data_dir.exists()  

class TestSettingsIntegration:
    """Integration tests for settings with actual environment."""
    
    def test_actual_settings_load(self):
        """Test loading actual settings from .env file."""
        # This assumes .env file exists in project root
        assert settings.NOTION_TOKEN
        assert settings.NOTION_DATABASE_ID
        assert settings.NOTION_PROJECTS_DATA_SOURCE_ID
        assert settings.NOTION_INBOX_PAGE_ID
    
    def test_actual_paths_exist(self):
        """Test that actual project paths exist."""
        assert settings.PROJ_ROOT.exists()
        assert (settings.PROJ_ROOT / 'inbox_agent').exists()
        assert (settings.PROJ_ROOT / 'notebooks').exists()
    
    def test_notion_ids_format(self):
        """Test that Notion IDs have expected format."""
        token = settings.NOTION_TOKEN
        assert len(token) > 0
        assert token.startswith('ntn_') or token.startswith('secret_')

        ids = [
            settings.NOTION_DATABASE_ID,
            settings.NOTION_PROJECTS_DATA_SOURCE_ID,
            settings.NOTION_TASKS_DATA_SOURCE_ID,
            settings.NOTION_INBOX_PAGE_ID
        ]
        for id_ in ids:
            assert len(id_) in [32, 36]  # UUID with or without dashes
            
    def test_client_is_working(self):
        """Test that Notion client can be instantiated with settings."""
        # Also tests that the fields are present in the config 
        from notion_client import Client
        client = Client(auth=settings.NOTION_TOKEN)
        assert isinstance(client, Client)
        
        database = client.databases.retrieve(settings.NOTION_DATABASE_ID)
        assert database['object'] == 'database'
        
        data_source = client.data_sources.retrieve(settings.NOTION_PROJECTS_DATA_SOURCE_ID)
        assert data_source['object'] == 'data_source'
        
        # Task database - skip if not accessible yet (needs to be shared with integration)
        try:
            task_database = client.databases.retrieve(settings.NOTION_TASKS_DATA_SOURCE_ID)
            assert task_database['object'] == 'database'
        except Exception as e:
            logger.warning(f"Task database not accessible (may need to share with integration): {e}")
        
        elab_page = client.pages.retrieve(settings.NOTION_INBOX_PAGE_ID)
        assert elab_page['object'] == 'page'
        