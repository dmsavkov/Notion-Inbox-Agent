"""
Test Notion API integration with real endpoints.
These tests verify actual Notion API functionality.
"""
import pytest
from notion_client import Client
from unittest.mock import Mock, patch
from inbox_agent.config import settings
from inbox_agent.notion import create_toggle_blocks, get_block_plain_text, get_inner_page_blocks, query_pages_filtered, _notion_cache, extract_property_value
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
            do_now=False,
            ai_use_status=AIUseStatus.PROCESSED,
            importance=2,
            urgency=1,
            impact=50,
            original_note="Test note content\n\nMultiple paragraphs work.",
            enrichment="Test enrichment content"
        )
        
        result = task_manager.create_task(task)
        
        # Skip actual Notion API calls if in DEBUG/TEST mode (which returns debug objects)
        if result['object'] == 'debug_task':
            pytest.skip("Test skipped: running in DEBUG/TEST mode (no real Notion API calls)")
        
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
    
    @pytest.mark.parametrize("block_input,expected", [
        # None and empty cases
        (None, ''),
        ({}, ''),
        ({'type': 'divider'}, ''),
        
        # Text block
        ({'type': 'text', 'plain_text': 'Direct text'}, 'Direct text'),
        
        # Comment
        ({'type': 'comment', 'rich_text': [{'plain_text': 'Comment text'}]}, 'Comment text'),
        ({'object': 'comment', 'rich_text': [{'plain_text': 'Another comment'}]}, 'Another comment'),
        
        # Page with title
        ({
            'type': 'page',
            'object': 'page',
            'properties': {'Name': {'title': [{'plain_text': 'Page Title'}]}}
        }, 'Page Title'),
        
        # Emoji icon
        ({'type': 'emoji', 'emoji': '🎉'}, '🎉'),
        
        # File
        ({'type': 'file', 'file': {'url': 'https://example.com/file.pdf'}}, 'https://example.com/file.pdf'),
        
        # External
        ({'type': 'external', 'external': {'url': 'https://example.com/image.jpg'}}, 'https://example.com/image.jpg'),
        
        # Child page
        ({'type': 'child_page', 'child_page': {'title': 'Subpage Title'}}, 'Subpage Title'),
        
        # Child database
        ({'type': 'child_database', 'child_database': {'title': 'Database Title'}}, 'Database Title'),
        
        # Multiple rich text items
        ({
            'type': 'paragraph',
            'paragraph': {
                'rich_text': [
                    {'plain_text': 'First '},
                    {'plain_text': 'Second '},
                    {'plain_text': 'Third'}
                ]
            }
        }, 'First Second Third'),
    ])
    def test_get_block_plain_text_various_types(self, block_input, expected):
        """Test get_block_plain_text with various block types"""
        assert get_block_plain_text(block_input) == expected


@pytest.mark.unit
class TestPropertyValueExtraction:
    """Unit tests for property value extraction"""
    
    @pytest.mark.parametrize("prop_input,expected", [
        # None and invalid cases
        (None, None),
        ({}, None),
        ({'type': 'unknown_type'}, None),
        ("not a dict", None),
        
        # Title property
        ({'type': 'title', 'title': [{'plain_text': 'Task Title'}]}, 'Task Title'),
        ({'type': 'title', 'title': [{'plain_text': 'Part 1'}, {'plain_text': ' Part 2'}]}, 'Part 1 Part 2'),
        ({'type': 'title', 'title': []}, ''),
        
        # Rich text property
        ({'type': 'rich_text', 'rich_text': [{'plain_text': 'Rich content'}]}, 'Rich content'),
        ({'type': 'rich_text', 'rich_text': []}, ''),
        
        # Number property
        ({'type': 'number', 'number': 42}, 42),
        ({'type': 'number', 'number': 3.14}, 3.14),
        ({'type': 'number', 'number': 0}, 0),
        ({'type': 'number', 'number': None}, None),
        
        # Select property
        ({'type': 'select', 'select': {'name': 'Option A'}}, 'Option A'),
        ({'type': 'select', 'select': None}, None),
        
        # Multi-select property
        ({'type': 'multi_select', 'multi_select': [{'name': 'Tag1'}, {'name': 'Tag2'}]}, ['Tag1', 'Tag2']),
        ({'type': 'multi_select', 'multi_select': []}, []),
        
        # Checkbox property
        ({'type': 'checkbox', 'checkbox': True}, True),
        ({'type': 'checkbox', 'checkbox': False}, False),
        
        # URL property
        ({'type': 'url', 'url': 'https://example.com'}, 'https://example.com'),
        ({'type': 'url', 'url': None}, None),
        
        # Email property
        ({'type': 'email', 'email': 'test@example.com'}, 'test@example.com'),
        
        # Phone property
        ({'type': 'phone_number', 'phone_number': '+1234567890'}, '+1234567890'),
        
        # Date property with start only
        ({'type': 'date', 'date': {'start': '2026-02-20'}}, '2026-02-20'),
        
        # Date property with start and end
        ({'type': 'date', 'date': {'start': '2026-02-20', 'end': '2026-02-25'}}, {'start': '2026-02-20', 'end': '2026-02-25'}),
        
        # Date property empty
        ({'type': 'date', 'date': None}, None),
        
        # People property
        ({'type': 'people', 'people': [{'name': 'Alice'}, {'name': 'Bob'}]}, ['Alice', 'Bob']),
        ({'type': 'people', 'people': [{'id': 'user-123'}]}, ['user-123']),
        
        # Files property
        ({'type': 'files', 'files': [{'name': 'doc.pdf'}]}, ['doc.pdf']),
        
        # Formula property
        ({'type': 'formula', 'formula': {'type': 'string', 'string': 'Result'}}, 'Result'),
        ({'type': 'formula', 'formula': {'type': 'number', 'number': 100}}, 100),
        
        # Relation property
        ({'type': 'relation', 'relation': [{'id': 'page-1'}, {'id': 'page-2'}]}, ['page-1', 'page-2']),
        
        # Rollup property
        ({'type': 'rollup', 'rollup': {'type': 'number', 'number': 5}}, 5),
        ({'type': 'rollup', 'rollup': {'type': 'array', 'array': [1, 2, 3]}}, [1, 2, 3]),
    ])
    def test_extract_property_value_various_types(self, prop_input, expected):
        """Test extract_property_value with various property types"""
        assert extract_property_value(prop_input) == expected


@pytest.mark.unit
class TestNotionCaching:
    """Unit tests for Notion API caching"""
    
    def setup_method(self):
        """Clear cache before each test"""
        _notion_cache.clear()
    
    def test_query_all_pages_caches_results(self):
        """Verify query_pages_filtered caches and reuses results with no filter"""
        mock_client = Mock()
        mock_client.data_sources.query.return_value = {
            'results': [{'id': '1', 'name': 'page1'}],
            'has_more': False
        }
        
        # First call - API call
        result1 = query_pages_filtered(mock_client, 'ds-123')['results']
        assert mock_client.data_sources.query.call_count == 1
        
        # Second call - should use cache, no new API call
        result2 = query_pages_filtered(mock_client, 'ds-123')['results']
        assert mock_client.data_sources.query.call_count == 1  # Still 1, no new call
        assert result1 == result2

    def test_get_inner_page_blocks_caches_results(self):
        """Verify get_inner_page_blocks caches and reuses results"""
        mock_notion = Mock()
        mock_notion.blocks.children.list.return_value = {
            'results': [{'id': 'b1', 'type': 'paragraph'}],
            'has_more': False
        }
        
        # First call - API call
        result1 = get_inner_page_blocks(mock_notion, 'page-456')
        assert mock_notion.blocks.children.list.call_count == 1
        
        # Second call - should use cache
        result2 = get_inner_page_blocks(mock_notion, 'page-456')
        assert mock_notion.blocks.children.list.call_count == 1  # Still 1
        assert result1 == result2
    
    def test_query_pages_filtered_caches_results(self):
        """Verify query_pages_filtered caches filtered queries"""
        mock_client = Mock()
        mock_client.data_sources.query.return_value = {
            'results': [{'id': 'p1', 'name': 'Project A'}],
            'has_more': False
        }
        
        filter_dict = {'property': 'Name', 'title': {'equals': 'Project A'}}
        
        # First call - API call
        result1 = query_pages_filtered(mock_client, 'ds-789', filter_dict)
        assert mock_client.data_sources.query.call_count == 1
        
        # Second call - should use cache
        result2 = query_pages_filtered(mock_client, 'ds-789', filter_dict)
        assert mock_client.data_sources.query.call_count == 1  # Still 1
        assert result1 == result2
    
    def test_different_datasources_not_cached_together(self):
        """Verify different data sources don't share cache"""
        mock_client = Mock()
        mock_client.data_sources.query.return_value = {
            'results': [{'id': '1'}],
            'has_more': False
        }
        
        query_pages_filtered(mock_client, 'ds-111')
        query_pages_filtered(mock_client, 'ds-222')
        
        # Two different data sources = two API calls
        assert mock_client.data_sources.query.call_count == 2