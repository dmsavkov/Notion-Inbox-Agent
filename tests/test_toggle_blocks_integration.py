"""
Integration tests for create_toggle_blocks() using actual Notion API.

These tests create real pages in Notion to verify block structure.
Requires NOTION_TOKEN and NOTION_PROJECTS_DATABASE_ID environment variables.
"""
import pytest
import os
from notion_client import Client
from inbox_agent.notion import create_toggle_blocks
from inbox_agent.config import settings


@pytest.fixture
def notion_client():
    """Create actual Notion client"""
    if not settings.NOTION_TOKEN:
        pytest.skip("NOTION_TOKEN not configured")
    return Client(auth=settings.NOTION_TOKEN)


@pytest.fixture
def test_database_id():
    """Get test database ID from settings"""
    if not settings.NOTION_PROJECTS_DATABASE_ID:
        pytest.skip("NOTION_PROJECTS_DATABASE_ID not configured")
    return settings.NOTION_PROJECTS_DATABASE_ID


@pytest.fixture
def cleanup_pages(notion_client):
    """Fixture to track and cleanup test pages"""
    created_pages = []
    
    yield created_pages
    
    # Cleanup: archive all created pages
    for page_id in created_pages:
        try:
            notion_client.pages.update(page_id=page_id, archived=True)
        except Exception as e:
            print(f"Warning: Failed to cleanup page {page_id}: {e}")


class TestToggleBlocksIntegration:
    """Integration tests with actual Notion API"""
    
    def test_basic_toggle_block_creation(self, notion_client, test_database_id, cleanup_pages):
        """Test creating a basic toggle block with simple text"""
        text = "This is a test note.\n\nWith multiple paragraphs."
        blocks = create_toggle_blocks(text, title="Test Toggle")
        
        # Create test page
        page = notion_client.pages.create(
            parent={"database_id": test_database_id},
            properties={
                "Name": {"title": [{"text": {"content": "Test: Basic Toggle"}}]}
            },
            children=blocks
        )
        cleanup_pages.append(page["id"])
        
        # Verify page created successfully
        assert page["id"] is not None
        
        # Retrieve and verify block structure
        blocks_response = notion_client.blocks.children.list(block_id=page["id"])
        retrieved_blocks = blocks_response["results"]
        
        # Should have one toggle block
        assert len(retrieved_blocks) == 1
        assert retrieved_blocks[0]["type"] == "toggle"
        assert retrieved_blocks[0]["toggle"]["rich_text"][0]["text"]["content"] == "Test Toggle"
        
        # Verify toggle has children
        assert retrieved_blocks[0]["has_children"] is True
    
    def test_toggle_with_markdown_headings(self, notion_client, test_database_id, cleanup_pages):
        """Test toggle blocks with markdown headings (bold syntax)"""
        text = """**First Heading**
This is content under the first heading.

**Second Heading**
This is content under the second heading.

Regular paragraph without heading."""
        
        blocks = create_toggle_blocks(text, title="Markdown Test")
        
        # Create test page
        page = notion_client.pages.create(
            parent={"database_id": test_database_id},
            properties={
                "Name": {"title": [{"text": {"content": "Test: Markdown Headings"}}]}
            },
            children=blocks
        )
        cleanup_pages.append(page["id"])
        
        # Retrieve toggle block
        blocks_response = notion_client.blocks.children.list(block_id=page["id"])
        toggle_block = blocks_response["results"][0]
        
        # Verify it's a toggle
        assert toggle_block["type"] == "toggle"
        assert toggle_block["has_children"] is True
        
        # Retrieve children of toggle
        children_response = notion_client.blocks.children.list(block_id=toggle_block["id"])
        children = children_response["results"]
        
        # Should have multiple blocks: heading, paragraph, heading, paragraph, paragraph
        assert len(children) >= 3
        
        # First should be heading_3
        assert children[0]["type"] == "heading_3"
        assert "First Heading" in children[0]["heading_3"]["rich_text"][0]["text"]["content"]
    
    def test_toggle_with_complex_content(self, notion_client, test_database_id, cleanup_pages):
        """Test toggle with complex multi-paragraph content"""
        text = """**Analysis:** The project requires careful consideration of multiple factors.

First, we need to understand the core problem. This involves breaking down assumptions.

**Recommendation:** Based on the analysis, proceed with a phased approach.

Start with a small prototype to validate key assumptions."""
        
        blocks = create_toggle_blocks(text, title="💡 AI Enrichment")
        
        # Create test page
        page = notion_client.pages.create(
            parent={"database_id": test_database_id},
            properties={
                "Name": {"title": [{"text": {"content": "Test: Complex Content"}}]}
            },
            children=blocks
        )
        cleanup_pages.append(page["id"])
        
        # Retrieve and verify structure
        blocks_response = notion_client.blocks.children.list(block_id=page["id"])
        toggle_block = blocks_response["results"][0]
        
        assert toggle_block["type"] == "toggle"
        assert toggle_block["toggle"]["rich_text"][0]["text"]["content"] == "💡 AI Enrichment"
        
        # Verify children exist
        children_response = notion_client.blocks.children.list(block_id=toggle_block["id"])
        assert len(children_response["results"]) > 0
    
    def test_toggle_with_special_characters(self, notion_client, test_database_id, cleanup_pages):
        """Test toggle with special characters and emojis"""
        text = """🚀 Project Launch Strategy

**Key Points:**
• First point with bullet
• Second point with special chars: @#$%
• Third point with emoji: 🎯

Final thoughts: "Quotes" and 'apostrophes' should work."""
        
        blocks = create_toggle_blocks(text, title="📝 Original Note")
        
        # Create test page
        page = notion_client.pages.create(
            parent={"database_id": test_database_id},
            properties={
                "Name": {"title": [{"text": {"content": "Test: Special Characters"}}]}
            },
            children=blocks
        )
        cleanup_pages.append(page["id"])
        
        # Verify page created successfully
        assert page["id"] is not None
        
        # Retrieve and verify
        blocks_response = notion_client.blocks.children.list(block_id=page["id"])
        assert len(blocks_response["results"]) == 1
        assert blocks_response["results"][0]["type"] == "toggle"
    
    def test_empty_toggle_block(self, notion_client, test_database_id, cleanup_pages):
        """Test behavior with empty or whitespace-only text"""
        text = "   \n\n   \n   "
        blocks = create_toggle_blocks(text, title="Empty Test")
        
        # Empty text should still create a toggle, just with no children
        # or minimal structure
        assert isinstance(blocks, list)
        assert len(blocks) >= 1
        assert blocks[0]["type"] == "toggle"
    
    def test_multiple_toggle_blocks(self, notion_client, test_database_id, cleanup_pages):
        """Test creating multiple toggle blocks in sequence"""
        note_text = "This is the original note.\n\nWith some context."
        enrichment_text = "**Analysis:** Deep dive into the problem."
        
        note_blocks = create_toggle_blocks(note_text, title="📝 Original Note")
        enrichment_blocks = create_toggle_blocks(enrichment_text, title="💡 AI Enrichment")
        
        all_blocks = note_blocks + enrichment_blocks
        
        # Create test page with both
        page = notion_client.pages.create(
            parent={"database_id": test_database_id},
            properties={
                "Name": {"title": [{"text": {"content": "Test: Multiple Toggles"}}]}
            },
            children=all_blocks
        )
        cleanup_pages.append(page["id"])
        
        # Retrieve and verify
        blocks_response = notion_client.blocks.children.list(block_id=page["id"])
        retrieved_blocks = blocks_response["results"]
        
        # Should have two toggle blocks
        assert len(retrieved_blocks) == 2
        assert all(block["type"] == "toggle" for block in retrieved_blocks)
        assert retrieved_blocks[0]["toggle"]["rich_text"][0]["text"]["content"] == "📝 Original Note"
        assert retrieved_blocks[1]["toggle"]["rich_text"][0]["text"]["content"] == "💡 AI Enrichment"


class TestToggleBlocksStructure:
    """Test the block structure without creating pages"""
    
    def test_block_structure_validation(self):
        """Test that generated blocks have correct Notion API structure"""
        text = "Test content"
        blocks = create_toggle_blocks(text, title="Test")
        
        # Validate structure
        assert isinstance(blocks, list)
        assert len(blocks) == 1
        
        toggle = blocks[0]
        assert toggle["object"] == "block"
        assert toggle["type"] == "toggle"
        assert "toggle" in toggle
        assert "rich_text" in toggle["toggle"]
        assert "children" in toggle["toggle"]
    
    def test_heading_extraction_logic(self):
        """Test heading extraction from markdown bold syntax"""
        text = "**Heading Text** Additional content"
        blocks = create_toggle_blocks(text)
        
        toggle = blocks[0]
        children = toggle["toggle"]["children"]
        
        # Should create heading and paragraph
        assert len(children) >= 1
        assert children[0]["type"] == "heading_3"
        assert "Heading Text" in children[0]["heading_3"]["rich_text"][0]["text"]["content"]
    
    def test_paragraph_creation(self):
        """Test regular paragraph creation"""
        text = "First paragraph\n\nSecond paragraph\n\nThird paragraph"
        blocks = create_toggle_blocks(text)
        
        children = blocks[0]["toggle"]["children"]
        
        # Should create 3 paragraph blocks
        assert len(children) == 3
        assert all(child["type"] == "paragraph" for child in children)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
