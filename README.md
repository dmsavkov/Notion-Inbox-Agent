# Notion Inbox Agent

> **Status: Aggressive Building & Beta** — Executive Function Prosthetic for processing raw notes into ranked, structured tasks.

## The Problem

You capture ideas fast, but processing them is slow. The "Capture-Process Gap" creates a graveyard of unread notes. You need a **Ruthless Funnel**, not another content factory.

## The Solution

An AI pipeline that decouples **capture** from **decision**:

1. **Route** → Classify notes into projects (metadata.py)
2. **Rank** → Score importance/urgency/impact (ranking.py)
3. **Filter** → Skip low-value notes (confidence threshold)
4. **Enrich** → Analyze high-impact ideas (enrichment.py)
5. **Store** → Create structured Notion tasks (task.py)

**Core Philosophy:** Every input is noise until proven otherwise. Expensive compute only for high-leverage ideas.

## Quick Start

```bash
# Setup with uv
uv venv
.venv\Scripts\Activate.ps1

# Install with dev dependencies
uv pip install -e ".[dev]"

# Configure .env (see .env.example)
NOTION_TOKEN=secret_xxx
GOOGLE_API_KEY=xxx

# Run
python run.py

# Run tests
pytest
```

## Architecture

```
Note → MetadataProcessor → RankingProcessor → EnrichmentProcessor → TaskManager → Notion
         (classify)          (score)            (analyze)           (create)
```

**Key Design:**

- **Separation of concerns:** Ranking (classification) is decoupled from Enrichment (generation)
- **Configurable models:** Support for Gemini/Gemma with automatic format handling
- **Confidence scoring:** Flags ambiguous notes for human review

## Testing

```bash
pytest                  # All tests
pytest -m integration   # Slow integration tests (requires API keys)
```

## Current Focus

- Tuning ranking prompts to match user mental models
- Confidence score calibration
- Field testing on live inbox

## Dependencies

See [pyproject.toml](pyproject.toml) for the list.
