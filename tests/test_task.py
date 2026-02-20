"""Test task management and debug task writing"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
from inbox_agent.task import TaskManager
from inbox_agent.pydantic_models import NotionTask, AIUseStatus
from inbox_agent.config import settings


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client"""
    return Mock()


@pytest.fixture
def task_manager(mock_notion_client):
    """Create TaskManager with mock client"""
    return TaskManager(mock_notion_client)


@pytest.fixture
def sample_task():
    """Create a sample NotionTask for testing"""
    return NotionTask(
        title="Test Task",
        projects=["Project A", "Project B"],
        do_now=False,
        ai_use_status=AIUseStatus.PROCESSED,
        importance=3,
        urgency=2,
        impact=75,
        confidence=0.85,
        reasoning="Test reasoning for the task",
        original_note="This is the original note content\nWith multiple lines",
        enrichment="Enriched analysis of the task"
    )


class TestWriteDebugTaskJson:
    """Test _write_debug_task_json method"""
    
    @patch('inbox_agent.task.get_workflow_id')
    @patch('inbox_agent.task.settings')
    def test_write_debug_task_creates_json_file(self, mock_settings, mock_workflow_id, task_manager, sample_task, tmp_path):
        """Test that debug task JSON file is created with correct structure"""
        mock_workflow_id.return_value = "test1234"
        mock_settings.DEBUG_TASKS_DIR = tmp_path
        mock_settings.RUNTIME_MODE = "TEST"
        
        result_path = task_manager._write_debug_task_json(sample_task)
        
        # Verify file was created
        assert result_path.exists()
        assert result_path.name == "Test_Task.json"
        
        # Verify JSON structure
        with open(result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["id"] == "test1234"
        assert data["environment"] == "TEST"
        assert "created_time" in data
        assert data["title"] == "Test Task"
        assert data["projects"] == ["Project A", "Project B"]
        assert data["importance"] == 3
        assert data["urgency"] == 2
        assert data["impact"] == 75
        assert data["confidence"] == 0.85
        assert data["reasoning"] == "Test reasoning for the task"
        assert "original note content" in data["original_note"]
    
    @patch('inbox_agent.task.get_workflow_id')
    @patch('inbox_agent.task.settings')
    def test_write_debug_task_sanitizes_filename(self, mock_settings, mock_workflow_id, task_manager, tmp_path):
        """Test that special characters in title are sanitized"""
        mock_workflow_id.return_value = "test5678"
        mock_settings.DEBUG_TASKS_DIR = tmp_path
        mock_settings.RUNTIME_MODE = "TEST"
        
        task = NotionTask(
            title="Task: With/Special*Characters?<>|",
            projects=[],
            do_now=False,
            ai_use_status=AIUseStatus.PROCESSED,
            importance=1,
            urgency=1,
            impact=25,
            original_note="Test"
        )
        
        result_path = task_manager._write_debug_task_json(task)
        
        # Filename should only contain safe characters
        assert result_path.exists()
        assert "Task_WithSpecialCharacters" in result_path.name
        assert "/" not in result_path.name
        assert "*" not in result_path.name
        assert "?" not in result_path.name
    
    @patch('inbox_agent.task.get_workflow_id')
    @patch('inbox_agent.task.settings')
    def test_write_debug_task_handles_duplicate_filename(self, mock_settings, mock_workflow_id, task_manager, sample_task, tmp_path):
        """Test that duplicate filenames get timestamp suffix"""
        mock_workflow_id.return_value = "testdup1"
        mock_settings.DEBUG_TASKS_DIR = tmp_path
        mock_settings.RUNTIME_MODE = "TEST"
        
        # Create first file
        first_path = task_manager._write_debug_task_json(sample_task)
        
        # Create second file with same title
        second_path = task_manager._write_debug_task_json(sample_task)
        
        # Both files should exist
        assert first_path.exists()
        assert second_path.exists()
        
        # Second file should have timestamp suffix
        assert first_path != second_path
        assert first_path.name == "Test_Task.json"
        assert "Test_Task_" in second_path.name
        assert second_path.name != "Test_Task.json"
    



class TestBuildContentBlocks:
    """Test content block building for Notion pages"""
    
    def test_build_content_blocks_with_all_fields(self, task_manager, sample_task):
        """Test building blocks with all optional fields present"""
        blocks = task_manager._build_content_blocks(sample_task)
        
        # Should have at least original note and enrichment toggles
        assert len(blocks) >= 2
        
        # First block should be original note toggle
        assert blocks[0]['type'] == 'toggle'
        assert '📝 Original Note' in str(blocks[0])
