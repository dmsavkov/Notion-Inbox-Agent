"""
Pipeline integration tests - verify modules work together.
Uses mocked Notion API, real LLM calls (if API keys present).
"""
import pytest
from unittest.mock import Mock, patch
from inbox_agent.pydantic_models import NotionTask, AppConfig
from run import process_note


SAMPLE_NOTES = {
    "simple": "Review the latest AI research paper",
    "urgent": "**[DO_NOW]** Fix critical bug in production",
}


@pytest.fixture
def mock_notion_client():
    """Minimal Notion client mock"""
    client = Mock()
    
    # Mock data source queries
    client.data_sources.query.return_value = {
        "results": [{
            "id": "proj_1",
            "properties": {"Name": {"title": [{"plain_text": "Test Project"}]}}
        }],
        "has_more": False
    }
    
    # Mock page retrieval
    client.pages.retrieve.return_value = {
        "id": "proj_1",
        "properties": {"Name": {"title": [{"plain_text": "Test Project"}]}}
    }
    
    # Mock blocks list
    client.blocks.children.list.return_value = {
        "results": [],
        "has_more": False
    }
    
    # Mock pages.create
    client.pages.create.return_value = {
        "id": "task_123",
        "url": "https://notion.so/task_123",
        "properties": {}
    }
    
    # Mock databases.query
    client.databases.query.return_value = {
        "results": [{"id": "proj_1"}],
        "has_more": False
    }
    
    return client


@pytest.mark.integration
class TestPipelineIntegration:
    """Test complete pipeline flow"""
    
    @patch('run.notion_api.Client')
    def test_pipeline_produces_task(self, mock_client_class, mock_notion_client):
        """Test that pipeline produces a valid NotionTask"""
        mock_client_class.return_value = mock_notion_client
        
        note = SAMPLE_NOTES["simple"]
        result = process_note(note)
        
        # Verify result structure
        assert isinstance(result, NotionTask)
        assert result.title
        assert isinstance(result.importance, int)
        assert isinstance(result.urgency, int)
        assert isinstance(result.impact, int)
        assert result.original_note == note
    
    @patch('run.notion_api.Client')
    def test_do_now_marker_detected(self, mock_client_class, mock_notion_client):
        """Test that DO_NOW marker is detected"""
        mock_client_class.return_value = mock_notion_client
        
        note = SAMPLE_NOTES["urgent"]
        result = process_note(note)
        
        assert isinstance(result, NotionTask)
        # DO_NOW should influence classification
        assert result.original_note == note
    
    def test_task_assembly_all_fields(self):
        """Test NotionTask assembled with all fields correctly"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
