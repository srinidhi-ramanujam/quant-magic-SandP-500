# S&P 500 Financial Analysis Platform

Natural language queries → SQL → Answers. Built incrementally with Azure OpenAI integration.

## Quick Start

```bash
cd /Users/Srinidhi/my_projects/quant-magic-SandP-500
source .venv/bin/activate

# Interactive CLI
python -m src.cli --interactive

# Single question
python -m src.cli "How many companies are in Technology?"

# Run tests (118 passing / 2 skipped / 2 xfailed)
python -m pytest tests/ -v
```

---

## Current Status - November 4, 2025

### ✅ Phase 0: Foundation (COMPLETE)
- **10/10 PoC questions** correct (<1.1s response time)
- **Data layer**: 15.5M+ financial facts, 589 S&P 500 companies
- **CLI**: Interactive REPL + single-shot modes
- **Test suite**: 55 tests passing (100%)

### ✅ Phase 1: AI Integration (COMPLETE)
- **LLM-first pipeline**: GPT-5 drives entity extraction and template selection when credentials are present; the system auto-falls back to deterministic mode with clear telemetry when Azure is unavailable.
- **Azure OpenAI**: GPT-5 integration with retry logic and dynamic circuit-breaker fallback
- **LLM Entity Extraction**: 13/13 tests passing (integration tests skipped unless `ENABLE_AZURE_INTEGRATION_TESTS=true`)
- **Hybrid Template Selection**: Deterministic fast path + LLM confirmation/fallback
- **27 SQL Templates**: 7 categories (company, sector, financial metrics, ratios, time series) with automated schema validation
- **Test suite**: 118 tests passing, 2 skipped (integration gated), 2 xpassed

### 🚀 Next: Phase 2 - SQL Generation & Coverage
- Custom SQL generation for non-template questions
- Two-pass validation (syntax + semantic)
- Target: 86+/171 simple questions (50%+)

---

## Architecture

Simple 4-layer pipeline with hybrid AI:

```
User Question
     ↓
[1. Entity Extraction] ← LLM-enhanced
     ↓
[2. Template Selection] ← Hybrid: Fast path + LLM
     ↓
[3. SQL Generation] → Execute on DuckDB
     ↓
[4. Response Formatting]
     ↓
Natural Language Answer
```

**Hybrid Approach**:
- **Fast Path** (confidence ≥0.8): Template → SQL (sub-second)
- **LLM Confirmation** (0.5-0.8): LLM validates template
- **LLM Fallback** (<0.5): Full LLM-powered generation

---

## Technology Stack

**Core**:
- Python 3.11+, DuckDB, Pydantic v2, pandas, pyarrow

**AI**:
- Azure OpenAI (GPT-5 deployment)
- LLM-assisted entity extraction & template selection
- Retry logic, circuit breaker, token tracking

**Testing**:
- pytest (100/104 passing)
- 410 evaluation questions (simple, medium, complex, time series)

---

## Data Layer

### Available Data
- **Companies**: 589 S&P 500 companies with sectors
- **Financial Facts**: 15.5M+ records (2014-2026)
- **XBRL Tags**: 481K definitions
- **Templates**: 27 SQL patterns across 7 categories

### Intelligence Layer
- `query_intelligence.parquet`: 27 NL→SQL templates
- `financial_concepts.parquet`: Metric→XBRL mappings
- `financial_ratios_definitions.parquet`: Ratio formulas
- `company_aliases.csv`: 161 company name variations

### Query Engine

```python
from src.query_engine import QueryEngine

qe = QueryEngine()
count = qe.count_companies()  # 589
sectors = qe.list_sectors()    # 11 GICS sectors
qe.close()
```

---

## Usage Examples

### Interactive Mode

```bash
python -m src.cli --interactive
```

```
💬 Ask: How many companies are in Technology?
💡 Answer: There are 143 companies in the Information Technology sector.

💬 Ask: What is Apple's CIK?
💡 Answer: APPLE INC's CIK is 0000320193.
```

### Single-Shot Mode

```bash
# Basic query
python -m src.cli "What sector is Microsoft in?"

# With debug info
python -m src.cli "How many companies in Healthcare?" --debug

# Test LLM entity extraction
python -m src.cli --test-entity-extraction --use-llm
```

### Currently Supported Queries

**Company Lookups**:
- CIK numbers, sectors, headquarters, incorporation

**Sector Analysis**:
- Company counts, lists, comparisons

**Financial Metrics** (27 templates total):
- Latest revenue, assets, equity, net income
- ROE, current ratio, debt-to-equity
- Revenue trends (YoY, multi-year, quarterly)
- Margin analysis (net, operating)

---

## Project Structure

```
quant-magic-SandP-500/
├── data/parquet/              # 253MB financial data
│   ├── num.parquet            # 15.5M financial facts
│   ├── companies_with_sectors.parquet  # 589 companies
│   ├── query_intelligence.parquet      # 27 templates
│   └── ...
├── evaluation/questions/      # 410 test questions
├── src/                       # Application code (~2,500 lines)
│   ├── azure_client.py        # Azure OpenAI wrapper
│   ├── entity_extractor.py    # LLM + deterministic extraction
│   ├── sql_generator.py       # Hybrid template selection
│   ├── prompts.py             # LLM prompt templates
│   ├── models.py              # 14 Pydantic models
│   ├── cli.py                 # Interactive CLI
│   └── ...
└── tests/                     # 104 tests (100 passing)
    ├── test_entity_extractor_llm.py    # 13 tests
    ├── test_sql_generator_hybrid.py    # 16 tests
    ├── test_eval_poc.py                # 11 tests
    └── ...
```

---

## Development

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_entity_extractor_llm.py -v

# Integration tests (require Azure OpenAI)
ENABLE_AZURE_INTEGRATION_TESTS=true python -m pytest -m integration
```

### Test Status
- **Total**: 104 tests
- **Passing**: 100 (96.2%)
- **Skipped**: 2 (integration tests)
- **XPassed**: 2 (expected failures now passing)

### Code Quality
- Black formatted (line length: 88)
- Type hints on all functions
- Pydantic v2 for all data contracts
- ~2,500 lines of application code

---

## Performance

**Current** (Phase 1):
- Simple queries: <1s (deterministic fast path)
- LLM-assisted: ~8s (GPT-5 API call)
- PoC validation: 10/10 correct, <1.1s average

**Targets** (Phase 2+):
- 86+/171 simple questions passing (50%+)
- Sub-second for 70%+ of queries (template fast path)
- 90%+ evaluation pass rate overall (long term)

---

## Phase 1 Achievements

### LLM Entity Extraction
- **Implemented**: `src/entity_extractor.py` with LLM-first approach
- **Prompt Engineering**: 400-line prompt with 10 few-shot examples
- **Models**: `LLMEntityRequest` and `LLMEntityResponse`
- **Tests**: 13/13 passing (11 unit + 2 integration)
- **Features**: Retry logic, JSON parsing, deterministic fallback
- **CLI**: `--test-entity-extraction --use-llm` command

### Hybrid Template Selection
- **Implemented**: `src/sql_generator.py` enhanced with 3-tier routing
- **Fast Path**: High confidence (≥0.8) skips LLM
- **LLM Confirmation**: Medium confidence (0.5-0.8) for validation
- **LLM Fallback**: Low confidence (<0.5) full LLM selection
- **Tests**: 16 tests (11 unit + 2 integration + 3 edge cases)
- **Telemetry**: Tracks selection method, tokens, latency

### Template Expansion
- **Templates**: 3 → 27 (900% increase)
- **Categories**: 7 (company, sector, geographic, metrics, ratios, time series)
- **Patterns**: Flexible regex for natural language matching
- **Validation**: All templates tested against real questions

---

## What's Next

See [PLAN.md](PLAN.md) for detailed roadmap.

**Immediate (Phase 2)**:
1. Custom SQL generation for non-template questions
2. Two-pass validation (syntax + semantic)
3. Iterative coverage expansion (50%+ target)

**Future (Phase 3+)**:
- Medium question support (multi-step analysis)
- Time series analysis
- Complex strategic queries
- Web UI integration

---

## Parallel UI & Codespaces Roadmap

| Track | Scope |
| --- | --- |
| Codespaces Enablement | Build `.devcontainer/devcontainer.json` on `mcr.microsoft.com/devcontainers/python:3.11` with Node 20 feature, preinstall Python deps, prep future `npm install`, forward ports 8000 (FastAPI) + 5173 (Vite), document DuckDB parquet availability and Codespaces secrets for Azure credentials. |
| FastAPI Service Layer | Extract CLI orchestration into a reusable query service, expose `POST /query` via FastAPI (`src/api/app.py`), return structured answer/SQL/metadata, and mirror CLI fallbacks when Azure creds are absent; cover with pytest `TestClient`. |
| React + HTMX Frontend | Scaffold `frontend/` with Vite (React + TypeScript), configure Tailwind/PostCSS and load HTMX for progressive enhancement, deliver a no-auth query form + results shell hitting the FastAPI endpoint while leaving extension points for charts. |
| Tooling & Docs | Add shared run scripts/tasks for API (`uvicorn src.api.app:app --reload`), tests (`pytest -m "not integration"`), and UI (`npm run dev`); update onboarding docs with Codespaces instructions and open questions (parquet distribution, streaming updates) before implementation. |

---

## Contributing

### Working Agreements
- Do not add persistent Markdown or throwaway scripts; clean up exploration artifacts before finishing a task.
- Ask for clarification before starting work that feels ambiguous and stay within the agreed design or plan.
- Avoid new dependencies unless the team grants explicit approval.
- Ship in small, meaningful iterations with a clear exit criterion (e.g., targeted pytest run, CLI demo, evaluation harness).

### Code Standards
- Follow test-driven development, keep functions under ~50 lines, and keep all suites green.
- Use Python 3.11+, four-space indentation, and Black (line length 88) across touched modules.
- Maintain type hints and Pydantic models; prefer `snake_case` for modules/functions, `PascalCase` for classes, and upper snake for constants.

### Project Layout
- `src/`: pipeline core (`azure_client.py`, `entity_extractor.py`, `sql_generator.py`, `cli.py`, etc.).
- `tests/`: mirrors application modules with unit suites and marked integration tests.
- `data/`: DuckDB inputs under `data/parquet/`; evaluation prompts in `evaluation/questions/`.
- `pipeline/` & `scripts/`: automation helpers and ETL jobs; additional docs in `docs/` and `PLAN.md`.

### Key Commands
- Environment setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- Interactive CLI: `python -m src.cli --interactive`.
- Single-shot debug query: `python -m src.cli "How many companies are in Technology?" --debug`.
- Full test suite: `python -m pytest tests/ -v`; target modules via `python -m pytest tests/test_sql_generator_hybrid.py -v`.
- Formatting pass: `python -m black src/ tests/`.

### Testing Guidelines
- Keep pytest as the single source of truth; mirror module structure and name tests `test_*`.
- Mark slow/external coverage with `@pytest.mark.integration`; use `python -m pytest -m "not integration"` for fast verification.
- Preserve or raise the current 100/104 baseline and store shared DuckDB fixtures in `tests/fixtures/`.

### Commit & PR Expectations
- Use Conventional Commit prefixes (`feat:`, `fix:`, `chore:`) with concise present-tense summaries under 72 characters.
- Document scope, verification commands (`pytest ...`, CLI demos), and link roadmap items or issues.
- Include screenshots or CLI transcripts when behavior changes, and ensure no secrets land in git.

### Security & Configuration
- Required environment variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME` (plus optional embeddings deployment).
- Store secrets in local env files or shell profiles and validate setup with `python -m src.cli --test-entity-extraction --use-llm`.
- When Azure credentials are present, entity extraction and template selection use GPT-5 automatically; if credentials or network access are missing, the system logs a warning and falls back to deterministic templates without failing requests.

---

## FAQ

**Q: What's the difference between Phase 0 and Phase 1?**  
A: Phase 0 was pure deterministic (3 templates). Phase 1 added AI integration (27 templates + LLM).

**Q: Do I need Azure OpenAI for basic queries?**  
A: No. Template fast path works without LLM. LLM is optional for complex queries.

**Q: How do I add new templates?**  
A: Update `data/parquet/query_intelligence.parquet` with new template patterns and SQL.

**Q: What's the test pass rate?**  
A: 100/104 (96.2%). 2 skipped (integration), 2 xpassed (expected failures now work).

---

## License

MIT License

## Support

- **Documentation**: See PLAN.md for detailed roadmap
- **Tests**: 104 tests with examples
- **Code**: Well-commented with type hints

---

**Status**: Phase 1 Complete (100/104 tests) | **Next**: Phase 2 SQL Generation & Coverage  
**Goal**: 50%+ simple question coverage (86+/171) | **Ultimate**: 90%+ on all 410 questions
