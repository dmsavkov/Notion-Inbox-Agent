import pytest
from unittest.mock import Mock
from inbox_agent.notion import (
    get_all_pages,
    get_inner_page_blocks,
    get_block_plain_text,
    get_page_report
)

DEFAULT_MOCK_ITEMS = 3


# Fixtures for creating dummy Notion data
@pytest.fixture
def mock_pages():
    """Factory fixture to create mock pages."""
    def _create_pages(num_items=DEFAULT_MOCK_ITEMS):
        return [
            {
                'id': f'page_{i}',
                'properties': {
                    'Name': {
                        'title': [{'plain_text': f'Project {i}'}]
                    }
                }
            }
            for i in range(1, num_items + 1)
        ]
    return _create_pages


@pytest.fixture
def mock_blocks():
    """Factory fixture to create mock blocks."""
    def _create_blocks(num_items=DEFAULT_MOCK_ITEMS):
        block_types = ['paragraph', 'toggle', 'bulleted_list_item']
        return [
            {
                'id': f'block_{i}',
                'type': block_types[i % len(block_types)],
                block_types[i % len(block_types)]: {
                    'rich_text': [{'plain_text': f'Block {i} content'}]
                },
                'has_children': False
            }
            for i in range(num_items)
        ]
    return _create_blocks


@pytest.fixture
def mock_notion_client(mock_pages, mock_blocks):
    """Create a mock Notion client with common methods."""
    client = Mock()
    
    # Default responses
    client.data_sources.query.return_value = {
        'results': mock_pages(DEFAULT_MOCK_ITEMS),
        'has_more': False,
        'next_cursor': None
    }
    
    client.blocks.children.list.return_value = {
        'results': mock_blocks(DEFAULT_MOCK_ITEMS),
        'has_more': False,
        'next_cursor': None
    }
    
    client.pages.retrieve.return_value = {
        'id': 'page_123',
        'object': 'page',
        'created_time': '2024-01-01T00:00:00.000Z',
        'last_edited_time': '2024-01-01T00:00:00.000Z',
        'parent': {'type': 'workspace', 'workspace': True},
        'properties': {
            'Name': {'title': [{'type': 'text', 'plain_text': 'Test Page'}]}
        },
        'cover': None,
        'icon': {'type': 'emoji', 'emoji': '🧠'}
    }
    
    client.comments.list.return_value = {
        'results': []
    }
    
    return client


# Tests for get_all_pages
class TestRetrieveAllPages:
    def test_retrieve_single_page(self, mock_notion_client):
        """Test retrieving pages without pagination."""
        pages = get_all_pages(mock_notion_client, 'data_source_123')
        
        assert len(pages) == DEFAULT_MOCK_ITEMS
        assert pages[0]['id'] == 'page_1'
        assert pages[0]['properties']['Name']['title'][0]['plain_text'] == 'Project 1'
        mock_notion_client.data_sources.query.assert_called_once()
    
    def test_retrieve_with_pagination(self, mock_pages):
        """Test retrieving pages with pagination."""
        mock_client = Mock()
        mock_client.data_sources.query.side_effect = [
            {
                'results': mock_pages(2),
                'has_more': True,
                'next_cursor': 'cursor_1'
            },
            {
                'results': mock_pages(1),
                'has_more': False,
                'next_cursor': None
            }
        ]
        
        pages = get_all_pages(mock_client, 'data_source_123')
        
        assert len(pages) == DEFAULT_MOCK_ITEMS
        assert mock_client.data_sources.query.call_count == 2


# Tests for get_inner_page_blocks
class TestGetInnerPageBlocks:
    def test_get_blocks_no_pagination(self, mock_notion_client):
        """Test getting blocks without pagination."""
        blocks = get_inner_page_blocks(mock_notion_client, 'page_123')
        
        assert len(blocks) == DEFAULT_MOCK_ITEMS
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[1]['type'] == 'toggle'
        assert blocks[2]['type'] == 'bulleted_list_item'
    
    def test_get_blocks_with_pagination(self, mock_blocks):
        """Test getting blocks with pagination."""
        mock_client = Mock()
        mock_client.blocks.children.list.side_effect = [
            {
                'results': mock_blocks(2),
                'has_more': True,
                'next_cursor': 'cursor_1'
            },
            {
                'results': mock_blocks(1),
                'has_more': False,
                'next_cursor': None
            }
        ]
        
        blocks = get_inner_page_blocks(mock_client, 'page_123')
        assert len(blocks) == DEFAULT_MOCK_ITEMS


# Tests for get_block_plain_text
class TestGetBlockPlainText:
    @pytest.mark.parametrize("block_type,content", [
        ('paragraph', 'Test paragraph'),
        ('heading_1', 'Main heading'),
        ('bulleted_list_item', 'List item'),
        ('numbered_list_item', 'Numbered item'),
        ('toggle', 'Toggle content'),
        ('quote', 'Quoted text'),
        ('to_do', 'To-do item')
    ])
    def test_text_blocks(self, block_type, content):
        """Test extracting text from various text-based blocks."""
        block = {
            'type': block_type,
            block_type: {
                'rich_text': [{'plain_text': content}]
            }
        }
        result = get_block_plain_text(block)
        assert result == content
    
    def test_code_block(self):
        """Test extracting text from code block."""
        block = {
            'type': 'code',
            'code': {
                'rich_text': [{'plain_text': 'print("Hello")'}],
                'language': 'python'
            }
        }
        result = get_block_plain_text(block)
        assert result == 'print("Hello")'
    
    def test_callout_with_icon(self):
        """Test extracting text from callout with icon."""
        block = {
            'type': 'callout',
            'callout': {
                'rich_text': [{'plain_text': 'Important'}],
                'icon': {'type': 'emoji', 'emoji': '💡'}
            }
        }
        result = get_block_plain_text(block)
        assert '💡' in result
        assert 'Important' in result
    
    def test_table_row(self):
        """Test extracting table row data."""
        block = {
            'type': 'table_row',
            'table_row': {
                'cells': [
                    [{'plain_text': 'A'}],
                    [{'plain_text': 'B'}],
                    [{'plain_text': 'C'}]
                ]
            }
        }
        result = get_block_plain_text(block)
        assert result == 'A | B | C'
    
    def test_page_object(self):
        """Test extracting title from page object."""
        block = {
            'object': 'page',
            'properties': {
                'Name': {
                    'title': [{'plain_text': 'Page Title'}]
                }
            }
        }
        result = get_block_plain_text(block)
        assert result == 'Page Title'
    
    def test_empty_and_edge_cases(self):
        """Test edge cases."""
        assert get_block_plain_text(None) == ''
        assert get_block_plain_text({'type': 'paragraph', 'paragraph': {'rich_text': []}}) == ''
        assert get_block_plain_text({'type': 'divider', 'divider': {}}) == ''


# Tests for get_page_report
class TestGetPageReport:
    def test_get_complete_page_report(self, mock_notion_client):
        """Test getting complete page report with all components."""
        # Add some comments
        mock_notion_client.comments.list.return_value = {
            'results': [
                {
                    'object': 'comment',
                    'type': 'comment',
                    'rich_text': [{'plain_text': 'Test comment'}]
                }
            ]
        }
        
        # Add blocks
        mock_notion_client.blocks.children.list.return_value = {
            'results': [
                {
                    'id': 'block1',
                    'type': 'paragraph',
                    'paragraph': {'rich_text': [{'plain_text': 'Content'}]},
                    'has_children': False
                }
            ],
            'has_more': False,
            'next_cursor': None
        }
        
        report = get_page_report(mock_notion_client, 'page_123')
        
        assert 'page_info' in report
        assert 'metadata' in report
        assert 'comments' in report
        assert 'children' in report
        
        assert report['page_info']['title'] == 'Test Page'
        assert report['page_info']['icon'] == '🧠'
        assert len(report['comments']) == 1
        assert report['comments'][0] == 'Test comment'
        assert len(report['children']) == 1
        assert report['children'][0]['text'] == 'Content'
        assert report['children'][0]['type'] == 'paragraph'
        assert report['children'][0]['has_children'] is False
    
    def test_get_page_report_empty(self, mock_notion_client):
        """Test getting page report with no comments or children."""
        mock_notion_client.blocks.children.list.return_value = {
            'results': [],
            'has_more': False,
            'next_cursor': None
        }
        
        report = get_page_report(mock_notion_client, 'page_123')
        
        assert len(report['comments']) == 0
        assert len(report['children']) == 0
        assert 'page_info' in report
        assert 'metadata' in report


# Integration tests
class TestIntegration:
    def test_full_workflow(self, mock_notion_client):
        """Test complete workflow from pages to report."""
        # Retrieve pages
        pages = get_all_pages(mock_notion_client, 'data_source_123')
        assert len(pages) == DEFAULT_MOCK_ITEMS
        
        # Extract title from first page (page object, not block)
        title_from_properties = pages[0]['properties']['Name']['title'][0]['plain_text']
        assert title_from_properties == 'Project 1'
        
        # Get detailed report
        report = get_page_report(mock_notion_client, pages[0]['id'])
        assert 'page_info' in report
        assert report['metadata']['id'] == 'page_123'
        assert report['page_info']['title'] == 'Test Page'