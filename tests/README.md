# Test Suite

## Overview

Minimal, focused tests that verify core functionality.

## Test Structure

### Unit Tests (Fast, No API Access Required)

Run with: `pytest -v -m "not integration"`

- **test_config.py** - Configuration loading and validation
- **test_task_properties.py** - Task property building for Notion API
- **test_notion.py::TestBlockTextExtraction** - Block text parsing utilities

### Integration Tests (Slow, Requires API Access)

Run with: `pytest -v -m integration`

- **test_notion.py::TestNotionAPI** - Real Notion API integration
  - Task creation with properties
  - Data source querying
  - Toggle block creation
- **test_pipeline_integration.py** - Complete pipeline flow (simplified)
  - Basic pipeline execution
  - DO_NOW marker detection

## Running Tests

```bash
# All unit tests (fast)
pytest -v -m "not integration"

# All tests including integration (requires API keys)
pytest -v

# Specific test file
pytest tests/test_task_properties.py -v

# Specific test
pytest tests/test_notion.py::TestNotionAPI::test_create_task_in_database -v
```

## Test Philosophy

1. **Minimal** - Only test what matters
2. **Focused** - One clear purpose per test
3. **Signal** - Tests should reveal real problems
4. **Real** - Integration tests use actual APIs (no mocks for endpoints)

## Notes

- Integration tests require `.env` configuration with valid API keys
- Pipeline integration tests use mocked Notion but may make real LLM calls
- Task database must be shared with your Notion integration
