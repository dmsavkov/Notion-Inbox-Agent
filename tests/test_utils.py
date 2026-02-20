"""Test utility functions in inbox_agent/utils.py"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
from inbox_agent.utils import extract_json_from_response, _build_dummy_llm_response, load_tasks_from_json


class TestExtractJsonFromResponse:
    """Test JSON extraction from LLM responses"""
    
    def test_direct_json_parsing(self):
        """Test parsing valid JSON string directly"""
        response = '{"key": "value", "number": 42}'
        result = extract_json_from_response(response)
        assert result == {"key": "value", "number": 42}
    
    def test_json_in_markdown_code_block_with_json_tag(self):
        """Test extracting JSON from ```json ... ``` blocks"""
        response = """Some text before
```json
{"title": "Test", "score": 95}
```
Some text after"""
        result = extract_json_from_response(response)
        assert result == {"title": "Test", "score": 95}
    
    def test_json_in_markdown_code_block_no_tag(self):
        """Test extracting JSON from ``` ... ``` blocks (no json tag)"""
        response = """Here's the response:
```
{"projects": ["A", "B"], "confidence": 0.85}
```"""
        result = extract_json_from_response(response)
        assert result == {"projects": ["A", "B"], "confidence": 0.85}
    
    def test_none_response_raises_error(self):
        """Test that None input raises ValueError"""
        with pytest.raises(ValueError, match="Response content is None"):
            extract_json_from_response(None)
    
    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError"""
        with pytest.raises(ValueError):
            extract_json_from_response("This is not JSON at all")


class TestBuildDummyLlmResponse:
    """Test dummy LLM response builder for TEST mode"""
    
    def test_metadata_classification_single_note(self):
        """Test building dummy response for metadata classification"""
        messages = [
            {"role": "system", "content": "You are a classifier"},
            {"role": "user", "content": "Note 0: Test note\nprojects: []\naction: classify\nconfidence_scores: [0.8]"}
        ]
        result = _build_dummy_llm_response(messages)
        
        assert "classifications" in result
        assert len(result["classifications"]) >= 1
        assert result["classifications"][0]["projects"] == ["Test Project"]
        assert result["classifications"][0]["reasoning"]
        assert "confidence_scores" in result["classifications"][0]
    
    def test_ranking_judge_response(self):
        """Test building dummy response for ranking judge"""
        messages = [
            {"role": "system", "content": "Judge"},
            {"role": "user", "content": "Rank this task\nimportance: 3\nurgency: 2\nimpact: 50\nconfidence: 0.8"}
        ]
        result = _build_dummy_llm_response(messages)
        
        assert "title" in result
        assert "importance" in result
        assert "urgency" in result
        assert "impact" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert result["title"] == "Debug Task - TEST Mode"


class TestLoadTasksFromJson:
    """Test loading tasks from JSON files"""
    
    def test_load_existing_file(self, tmp_path):
        """Test loading tasks from existing JSON file"""
        tasks = [
            {"id": "1", "title": "Task 1"},
            {"id": "2", "title": "Task 2"}
        ]
        test_file = tmp_path / "tasks.json"
        test_file.write_text(json.dumps(tasks), encoding="utf-8")
        
        result = load_tasks_from_json(test_file)
        
        assert len(result) == 2
        assert result[0]["title"] == "Task 1"
        assert result[1]["id"] == "2"
    
    def test_load_nonexistent_file(self, tmp_path):
        """Test that loading non-existent file returns empty list"""
        test_file = tmp_path / "nonexistent.json"
        result = load_tasks_from_json(test_file)
        
        assert result == []
