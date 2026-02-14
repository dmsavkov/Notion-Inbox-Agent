"""Test task property building for Notion API"""
import pytest
from unittest.mock import Mock
from inbox_agent.task import TaskManager
from inbox_agent.pydantic_models import NotionTask, AIUseStatus


class TestTaskProperties:
    """Test that task properties match Notion schema"""
    
    def test_build_properties_basic_fields(self):
        """Test that all basic properties are correctly built"""
        # Create mock client
        mock_client = Mock()
        task_manager = TaskManager(mock_client)
        
        # Create test task
        task = NotionTask(
            title="Test Task",
            projects=["Test Project"],
            ai_use_status=AIUseStatus.PROCESSED,
            importance=3,
            urgency=2,
            impact=75,
            original_note="Original test note"
        )
        
        # Build properties
        properties = task_manager._build_properties(task)
        
        # Verify structure
        assert "Name" in properties
        assert properties["Name"]["title"][0]["text"]["content"] == "Test Task"
        
        assert "Importance" in properties
        assert properties["Importance"]["select"]["name"] == "3"
        
        assert "Urgency" in properties
        assert properties["Urgency"]["select"]["name"] == "2"
        
        assert "Impact Score" in properties
        assert properties["Impact Score"]["number"] == 75
        
        assert "UseAIStatus" in properties
        assert properties["UseAIStatus"]["select"]["name"] == "processed"
        
        assert "Status" in properties
        assert properties["Status"]["status"]["name"] == "Not started"
    
    def test_build_properties_ambiguous_status(self):
        """Test UseAIStatus field with ambiguous value"""
        mock_client = Mock()
        task_manager = TaskManager(mock_client)
        
        task = NotionTask(
            title="Ambiguous Task",
            projects=[],
            ai_use_status=AIUseStatus.AMBIGUOUS,
            importance=2,
            urgency=1,
            impact=50,
            original_note="Test note"
        )
        
        properties = task_manager._build_properties(task)
        
        assert properties["UseAIStatus"]["select"]["name"] == "ambiguous"
    
    def test_build_properties_without_project(self):
        """Test that properties work when no project is specified"""
        mock_client = Mock()
        task_manager = TaskManager(mock_client)
        
        task = NotionTask(
            title="No Project Task",
            projects=[],
            ai_use_status=AIUseStatus.PROCESSED,
            importance=1,
            urgency=1,
            impact=25,
            original_note="Test note"
        )
        
        properties = task_manager._build_properties(task)
        
        # Should not have Project property
        assert "Project" not in properties
        
        # But should have all other properties
        assert "Name" in properties
        assert "Importance" in properties
        assert "Urgency" in properties
        assert "Impact Score" in properties
        assert "UseAIStatus" in properties
        assert "Status" in properties
