# GEMINI.md - Context & Instructions for Quant Magic S&P 500

## Project Overview
**Quant Magic S&P 500** is a financial analysis platform that converts natural language queries into SQL to retrieve answers from a DuckDB database containing S&P 500 financial data. It uses a hybrid architecture combining deterministic templates with Azure OpenAI (GPT-5) for entity extraction and complex query fallback.

**Status:** Phase 2 (Active) - Focusing on custom SQL generation, coverage expansion, and time-series analysis.

## Architecture
The system follows a 4-layer pipeline:
1.  **Entity Extraction**: Identifies companies, sectors, and metrics (Hybrid: Deterministic + LLM).
2.  **Template Selection**: Matches queries to pre-defined SQL templates (Hybrid: Fast Path > LLM Confirmation > LLM Fallback).
3.  **SQL Generation**: Populates templates or generates custom SQL for DuckDB execution.
4.  **Response Formatting**: Formats the raw data into natural language answers with optional visualizations.

**Stack:**
*   **Backend**: Python 3.11+, FastAPI, Pydantic v2.
*   **Data**: DuckDB, Parquet, FAISS (Vector Store).
*   **Frontend**: React, TypeScript, Tailwind CSS, Vite.
*   **AI**: Azure OpenAI (GPT-5), Sentence Transformers (Embeddings).

## Key Directories & Files
*   `src/`: Core application logic (CLI, API, Pipeline).
    *   `src/api/app.py`: FastAPI backend entry point.
    *   `src/cli.py`: Interactive CLI entry point.
*   `frontend/`: React-based chat interface.
*   `data/parquet/`: DuckDB data files (Financial facts, Companies, Intelligence).
    *   *Note: Treat data files as read-only unless explicitly instructed otherwise.*
*   `sql_templates/`: SQL patterns for various financial metrics.
*   `tests/`: Comprehensive test suite (mirroring `src/`).
*   `.beads/`: Issue tracking data (do not edit manually, use `bd` CLI).

## Operational Guide

### 1. Environment Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Running the System
**Interactive CLI (Primary Interface):**
```bash
python -m src.cli --interactive
```

**Single Query:**
```bash
python -m src.cli "How many companies are in Technology?"
```

**Full Stack (API + Frontend):**
```bash
./scripts/run_local_ui.sh
```
*   API: `http://localhost:8000`
*   UI: `http://localhost:5173`

**Tests:**
```bash
python -m pytest tests/ -v
# Fast tests only (skip integration)
python -m pytest -m "not integration"
```

## Development Conventions

### Task Management (Critical)
*   **Tool:** Use `bd` (beads) for ALL issue tracking.
*   **Workflow:**
    1.  Check work: `bd ready --json`
    2.  Claim task: `bd update <id> --status in_progress --json`
    3.  Complete task: `bd close <id> --reason "Done" --json`
*   **Rule:** Commit `.beads/issues.jsonl` along with code changes.

### Coding Standards
*   **Style:** `black` formatting (line length 88).
*   **Typing:** Full type hints on all functions.
*   **Models:** Pydantic v2 for all data contracts.
*   **Testing:** Test-Driven Development (TDD). Maintain high coverage.

### Agent Guidelines
*   **No Persistent Scratchpads:** Do not create markdown files like `TODO.md` in the root. Use `history/` for ephemeral planning docs if absolutely necessary.
*   **Dependencies:** strictly adhere to `requirements.txt`.
*   **Secrets:** Never hardcode credentials. Use environment variables.
*   **Output:** When modifying code, always verify with `pytest`.
