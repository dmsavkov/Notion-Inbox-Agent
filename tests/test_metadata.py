"""Test metadata classification and project metadata fetching"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from inbox_agent.metadata import MetadataProcessor
from inbox_agent.pydantic_models import (
    NoteClassification, ProjectMetadata, MetadataConfig, 
    ModelConfig, MetadataResult
)


@pytest.fixture
def mock_notion_client():
    """Create a mock Notion client"""
    client = Mock()
    return client


@pytest.fixture
def metadata_processor(mock_notion_client):
    """Create MetadataProcessor with mock client"""
    config = MetadataConfig(batch_size=2, project_confidence_threshold=0.6)
    return MetadataProcessor(mock_notion_client, config)


class TestMetadataProcessor:
    """Test MetadataProcessor main interface"""
    
    @patch('inbox_agent.metadata.MetadataProcessor._fetch_project_metadata')
    @patch('inbox_agent.metadata.MetadataProcessor._classify_notes_batched')
    def test_process_single_note(self, mock_classify, mock_fetch, metadata_processor):
        """Test processing a single note"""
        # Setup mocks
        mock_fetch.return_value = {
            "Test Project": ProjectMetadata(
                name="Test Project",
                priority="High",
                status="Active",
                types=["Development"]
            )
        }
        
        mock_classify.return_value = [
            NoteClassification(
                note_id=0,
                projects=["Test Project"],
                do_now=False,
                reasoning="Test reasoning",
                confidence_scores=[0.9]
            )
        ]
        
        # Process note
        results = metadata_processor.process(["Test note content"])
        
        # Verify
        assert len(results) == 1
        assert isinstance(results[0], MetadataResult)
        assert results[0].classification.note_id == 0
        assert "Test Project" in results[0].classification.projects
        assert "Test Project" in results[0].project_metadata
        assert results[0].project_metadata["Test Project"].priority == "High"
    



class TestClassifyNotesBatched:
    """Test batch classification logic"""
    
    @patch('inbox_agent.metadata.MetadataProcessor._classify_batch')
    def test_classify_notes_batched_single_batch(self, mock_classify_batch, metadata_processor):
        """Test classifying notes that fit in one batch"""
        mock_classify_batch.return_value = [
            NoteClassification(note_id=0, projects=["P1"], do_now=False, 
                             reasoning="R1", confidence_scores=[0.8]),
            NoteClassification(note_id=1, projects=["P2"], do_now=False, 
                             reasoning="R2", confidence_scores=[0.7])
        ]
        
        notes = ["Note 1", "Note 2"]
        results = metadata_processor._classify_notes_batched(notes, '["P1", "P2"]')
        
        assert len(results) == 2
        assert mock_classify_batch.call_count == 1
    



class TestClassifyBatch:
    """Test single batch classification with LLM"""
    
    @patch('inbox_agent.metadata.call_llm_with_json_response')
    def test_classify_batch_success(self, mock_llm, metadata_processor):
        """Test successful batch classification"""
        mock_llm.return_value = {
            "classifications": [
                {
                    "note_id": 0,
                    "projects": ["Project A", "Project B"],
                    "do_now": False,
                    "reasoning": "Test reasoning",
                    "confidence_scores": [0.9, 0.8]
                }
            ]
        }
        
        batch = ["Test note"]
        indices = [0]
        projects_info = '["Project A", "Project B"]'
        
        results = metadata_processor._classify_batch(batch, indices, projects_info)
        
        assert len(results) == 1
        assert results[0].note_id == 0
        assert results[0].projects == ["Project A", "Project B"]
        assert results[0].confidence_scores == [0.9, 0.8]
    
    @patch('inbox_agent.metadata.call_llm_with_json_response')
    def test_classify_batch_filters_by_confidence_threshold(self, mock_llm, metadata_processor):
        """Test that low-confidence projects are filtered out"""
        mock_llm.return_value = {
            "classifications": [
                {
                    "note_id": 0,
                    "projects": ["High", "Medium", "Low"],
                    "do_now": False,
                    "reasoning": "Test",
                    "confidence_scores": [0.9, 0.65, 0.3]  # threshold is 0.6
                }
            ]
        }
        
        results = metadata_processor._classify_batch(["Note"], [0], '["High", "Medium", "Low"]')
        
        # Should only include High and Medium (above 0.6 threshold)
        assert len(results[0].projects) == 2
        assert "High" in results[0].projects
        assert "Medium" in results[0].projects
        assert "Low" not in results[0].projects
    



class TestFetchProjectMetadata:
    """Test fetching project metadata from Notion"""
    
    @patch('inbox_agent.metadata.query_pages_filtered')
    @patch('inbox_agent.metadata.get_block_plain_text')
    @patch('inbox_agent.metadata.extract_property_value')
    def test_fetch_all_projects(self, mock_extract, mock_get_text, mock_query, metadata_processor):
        """Test fetching metadata for all projects"""
        mock_query.return_value = {
            'results': [
                {
                    'properties': {
                        'Name': {},
                        'Priority': {},
                        'Status': {},
                        'Type': {}
                    }
                },
                {
                    'properties': {
                        'Name': {},
                        'Priority': {},
                        'Status': {},
                        'Type': {}
                    }
                }
            ]
        }
        
        mock_get_text.side_effect = ["Project Alpha", "Project Beta"]
        # Extraction order: Type (first), Priority, Status for each project
        mock_extract.side_effect = [
            ["Development"], "High", "Active",  # Project Alpha
            ["Research"], "Medium", "Planning"   # Project Beta
        ]
        
        results = metadata_processor._fetch_project_metadata()
        
        assert len(results) == 2
        assert "Project Alpha" in results
        assert "Project Beta" in results
        assert results["Project Alpha"].priority == "High"
        assert results["Project Beta"].status == "Planning"
    

