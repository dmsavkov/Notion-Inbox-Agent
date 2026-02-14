"""
Test Notion API integration with real endpoints.
These tests verify actual Notion API functionality.
"""
import pytest
from notion_client import Client
from inbox_agent.config import settings
from inbox_agent.notion import create_toggle_blocks, get_block_plain_text
from inbox_agent.task import TaskManager
from inbox_agent.pydantic_models import NotionTask, AIUseStatus


@pytest.fixture
def notion_client():
    """Real Notion client for integration tests"""
    return Client(auth=settings.NOTION_TOKEN)


@pytest.fixture
def cleanup_pages(notion_client):
    """Track and cleanup test pages"""
    pages = []
    yield pages
    for page_id in pages:
        try:
            notion_client.pages.update(page_id=page_id, archived=True)
        except:
            pass


@pytest.mark.integration
class TestNotionAPI:
    """Test real Notion API endpoints"""
    
    def test_create_task_in_database(self, notion_client, cleanup_pages):
        """Test creating a task with toggle blocks and properties"""
        task_manager = TaskManager(notion_client)
        
        task = NotionTask(
            title="API Test Task - Delete Me",
            projects=[],
            ai_use_status=AIUseStatus.PROCESSED,
            importance=2,
            urgency=1,
            impact=50,
            original_note="Test note content\n\nMultiple paragraphs work.",
            enrichment="Test enrichment content"
        )
        
        result = task_manager.create_task(task)
        cleanup_pages.append(result['id'])
        
        # Verify response structure
        assert 'id' in result
        assert 'properties' in result
        assert result['properties']['Name']['title'][0]['text']['content'] == task.title
        
        # Verify blocks were created
        blocks = notion_client.blocks.children.list(block_id=result['id'])
        assert len(blocks['results']) >= 2  # At least note toggle and enrichment toggle
        
        # Verify first block is a toggle
        first_block = blocks['results'][0]
        assert first_block['type'] == 'toggle'
        assert '📝 Original Note' in get_block_plain_text(first_block)
    
    def test_retrieve_projects_data_source(self, notion_client):
        """Test querying projects data source"""
        results = notion_client.data_sources.query(
            settings.NOTION_PROJECTS_DATA_SOURCE_ID,
            page_size=5
        )
        
        assert 'results' in results
        assert isinstance(results['results'], list)
        if results['results']:
            assert 'id' in results['results'][0]
            assert 'properties' in results['results'][0]
    
    def test_toggle_blocks_creation(self):
        """Test toggle block structure"""
        text = "Line 1\nLine 2\n\n# Heading\nMore text"
        blocks = create_toggle_blocks(text, "Test Toggle")
        
        assert len(blocks) > 0
        assert blocks[0]['type'] == 'toggle'
        assert blocks[0]['toggle']['rich_text'][0]['text']['content'] == "Test Toggle"


@pytest.mark.unit
class TestBlockTextExtraction:
    """Unit tests for block text extraction"""
    
    @pytest.mark.parametrize("block_type", ['paragraph', 'heading_1', 'bulleted_list_item', 'toggle'])
    def test_extract_from_text_blocks(self, block_type):
        block = {
            'type': block_type,
            block_type: {'rich_text': [{'plain_text': 'Test'}]}
        }
        assert get_block_plain_text(block) == 'Test'
    
    def test_extract_from_empty_block(self):
        assert get_block_plain_text(None) == ''
        assert get_block_plain_text({'type': 'divider'}) == ''