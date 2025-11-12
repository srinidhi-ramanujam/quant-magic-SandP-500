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

> ℹ️ The CLI and API require Azure OpenAI credentials by default. If you see
> `API not available...`, re-run commands with `--allow-offline` to use the
> deterministic fallback mode.

---

## GitHub Codespaces

1. Create a Codespace from this repo (`Code → Codespaces → Create codespace on master`) or open the shared link.<br>Make sure the repository-level Codespaces setting is enabled.
2. On first boot the devcontainer provisions Python 3.11 and Node 20, creates `.venv`, and installs `requirements.txt`. When the terminal is ready, activate the environment: `source .venv/bin/activate`.
3. Fill in Secrets under `Codespaces → Codespaces secrets` (or add a `.env` file) using the keys in `.env.example` so Azure OpenAI calls work inside the container.
4. Run backend routines as usual (e.g., `python -m pytest -m "not integration"` or `python -m src.cli "How many companies are in Technology?"`).
5. Launch the FastAPI layer with `uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000` (task shortcut: "run api").
6. Start the React chat interface from `frontend/` with `npm run dev -- --host 0.0.0.0 --port 5173` (task shortcut: "run ui"). Codespaces will expose a public link you can share.

### Local Dev Stack

Run both FastAPI and the Vite UI on localhost:

```bash
./scripts/run_local_ui.sh
```

Prerequisites:
- `.venv` created and `pip install -r requirements.txt` completed
- Frontend dependencies installed (`frontend/node_modules/`); the script will run `npm install` automatically if missing

The script binds FastAPI to `http://localhost:8000` and Vite to `http://localhost:5173`, streams logs, and stops both services when you hit `Ctrl+C`.

Per run, the script creates `.logs/session-<timestamp>/` (deleted when you stop the stack) containing:
- `api.log` / `ui.log`: live server output (cleared on next start)
- `requests.jsonl`: structured question/answer records with request IDs, SQL, and entities  
Once you stop the script, restart it to clear old logs and begin a fresh session.

### Chat Interface & Formatter
- **Chat UI**: React + Tailwind interface with ASCENDION branding, sidebar session list, auto-resizing input, and live API health indicator.
- **Formatted answers**: API/UI requests include `history` + `include_formatted_answer=true` so the LLM formatter can produce narratives, highlights, tables, and warnings; toggle off via CLI flag.
- **Reasoning panel**: Assistant messages expose a collapsible “Reasoning & SQL” section summarising template/method/row counts with the full query for copy-to-clipboard.

---

## Status Snapshot

- **Phase 0/1**: Foundation + LLM integration complete (Azure OpenAI, hybrid template routing, 27 templates, 100+ tests). No further action required.
- **Phase 2 (Active)**: Custom SQL generation + validation + coverage push (goal: 86+/171 simple questions). See `PLAN.md` for live roadmap.

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

### Frontend Commands

```bash
cd frontend

# Install dependencies (happens automatically inside Codespaces)
npm install

# Start the chat interface (Vite dev server with port forwarding)
npm run dev -- --host 0.0.0.0 --port 5173

# Build & type-check the UI
npm run build

# Preview production build
npm run preview
```

The chat interface connects to the FastAPI backend at `/api/query` and displays:
- Conversation history with timestamps
- User questions in indigo gradient bubbles
- AI responses with SQL queries and metadata
- Real-time API connection status

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

| Track | Status | Scope |
| --- | --- | --- |
| Codespaces Enablement | ✅ Complete | Build `.devcontainer/devcontainer.json` on `mcr.microsoft.com/devcontainers/python:3.11` with Node 20 feature, preinstall Python deps, prep future `npm install`, forward ports 8000 (FastAPI) + 5173 (Vite), document DuckDB parquet availability and Codespaces secrets for Azure credentials. |
| FastAPI Service Layer | 🚧 In Progress | Extract CLI orchestration into a reusable query service, expose `POST /query` via FastAPI (`src/api/app.py`), return structured answer/SQL/metadata, and mirror CLI fallbacks when Azure creds are absent; cover with pytest `TestClient`. |
| React Chat Interface | ✅ Complete | Modern chat UI with ASCENDION branding, fixed sidebar with chat history/quick access, scrollable conversation area, professional indigo/blue color scheme, real-time API status indicator, auto-resizing textarea, chat session management. Built with React + TypeScript + Tailwind CSS. |
| Tooling & Docs | ✅ Complete | Add shared run scripts/tasks for API (`uvicorn src.api.app:app --reload`), tests (`pytest -m "not integration"`), and UI (`npm run dev`); update onboarding docs with Codespaces instructions and open questions (parquet distribution, streaming updates) before implementation. |

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
- Regenerate template intents JSON: `python scripts/export_template_intents.py`.
- Build FAISS vector stores: `python scripts/build_vector_store.py`.

### Testing Guidelines
- Keep pytest as the single source of truth; mirror module structure and name tests `test_*`.
- Mark slow/external coverage with `@pytest.mark.integration`; use `python -m pytest -m "not integration"` for fast verification.
- Preserve or raise the current 100/104 baseline and store shared DuckDB fixtures in `tests/fixtures/`.

### Upcoming Hybrid Retrieval Metrics
- Phase 2D will introduce keyword + embedding retrieval for entity extraction and template selection (FAISS/Chroma + `sentence-transformers`).
- We’ll compare baseline RUN_020 metrics against the hybrid path:
  - Entity extraction accuracy (slot match rate on evaluation suite).
  - Template hit rate (questions resolved without fallback).
  - LLM reliance (calls per question) and median latency.
  - Validator pass rate for true custom SQL calls.
- See `PLAN.md` for detailed deliverables and thresholds; embedding refresh instructions will land once the feature is implemented.

### Catalog-Driven Retrieval (Phase 2D)
- Editable catalogs live under `data/entities.json` and `data/template_intents.json`. Update these files to add new entity synonyms or template intents.
- After editing, regenerate the FAISS indexes:
  1. `python scripts/export_template_intents.py` (populates `data/template_intents.json` from `query_intelligence.parquet`)
  2. `python scripts/build_vector_store.py` (writes embeddings + metadata into `artifacts/vector_store/`)
- Runtime flow:
  1. **User query** enters via CLI/API.
  2. **EntityExtractor** runs deterministic heuristics, then asks `HybridEntityRetriever` (FAISS index + MiniLM) to fill missing slots (sectors, metrics, question type). LLM fallback is only used if both paths fail.
  3. **SQLGenerator** does deterministic regex/template matching; if no template is found it consults `TemplateIntentRetriever` (same FAISS store) to pick the best template intent. LLM template-selection is now reserved for genuinely novel intents.
  4. **Template SQL** is populated with extracted parameters, validated by `SQLValidator` (static + semantic passes).
  5. **Query execution** happens in DuckDB via `QueryEngine`, returning a pandas DataFrame.
  6. **ResponseFormatter** formats the result (count, lookup, table) and attaches telemetry (latency, validator result). The CLI or API returns the final answer.

### Time-Series Asset Turnover Template
- `sql_templates/asset_turnover_trend.sql` powers TS_011 and any future asset-efficiency cohorts. It accepts:
  - `sector` (default `Information Technology`) to scope by GICS sector, set to `ALL` for cross-sector runs.
  - `sic_filter_enabled`, `sic_min`, `sic_max` to optionally gate results to a SIC range (defaults 3570–3699 for hardware).
  - `start_year`, `year_2`, `year_3`, `end_year`, `min_years` to define the fiscal window and minimum coverage.
  - `min_revenue` (default $10B) to exclude subscale names and `limit` (default 6) to control ranking length.
- After editing the template or its metadata, rerun `python scripts/build_vector_store.py` so hybrid retrieval learns the new intent.
- Validation commands:
  ```bash
  python -m src.cli "Compare the asset turnover efficiency trends for major Technology hardware companies from FY2020 through FY2023." --debug
  python scripts/run_eval_suite.py --question "Compare the asset turnover efficiency trends for major Technology hardware companies from FY2020 through FY2023." --no-json
  ```
- Expected FY2020–FY2023 output with the default SIC and revenue filters: NVIDIA (+0.35x), Dell/Denali (+0.31x), Apple (+0.24x), Otis (+0.21x), Broadcom (+0.18x).
- `sql_templates/cfo_to_net_income_trend.sql` powers TS_012 and ranks Healthcare cohorts by CFO/Net income ratios. Parameters mirror the sector template above (`sector`, fiscal-year window, minimum coverage, limit, `min_net_income`, `max_ratio`). The query dedupes company names, caps outlier ratios at 3× to avoid distortion, and defaults to FY2019–FY2023. To validate:
  ```bash
  python -m src.cli "Show the cash flow from operations to net income ratio trends for Healthcare companies from FY2019 through FY2023, identifying quality of earnings patterns." --debug
  python scripts/run_eval_suite.py --question "Show the cash flow from operations to net income ratio trends for Healthcare companies from FY2019 through FY2023, identifying quality of earnings patterns." --no-json
  ```
  Expected output: DaVita (~2.6x), AbbVie (~2.3x), Becton (~2.3x), Bristol (~2.1x), HCA (~1.8x) with richer bullets explaining cash conversion.

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

**Status**: Phase 1 Complete + Chat UI Live | **Next**: Phase 2 SQL Generation & Coverage  
**Goal**: 50%+ simple question coverage (86+/171) | **Ultimate**: 90%+ on all 410 questions  
**Last Updated**: November 6, 2025
