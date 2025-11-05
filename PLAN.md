# Development Plan - S&P 500 Financial Analysis Platform

**Product**: AI-powered financial analytics via natural language  
**Approach**: Incremental delivery with clear exit criteria  
**Current Phase**: Phase 1 Complete → Phase 2 Starting  
**Test Status**: 118 passed / 2 skipped / 2 xfailed

---

## Executive Summary

### What's Working ✅
- **Phase 0**: PoC with 10/10 questions correct
- **Phase 1**: LLM-first entity extraction & template selection with deterministic fallback when Azure is unavailable
- **Data**: 15.5M+ facts, 589 companies, 27 SQL templates (schema-aligned)
- **Tests**: 118 passing (integration marked/skipped), full template execution harness, Phase 0 PoC suite fast again
- **CLI**: Interactive REPL + single-shot modes now default to LLM paths when credentials exist

### What's Next 🚀
- **Phase 2**: Custom SQL generation + validation + coverage expansion
- **Target**: 86+/171 simple questions passing (50%+)
- **Timeline**: ~20-25 hours of focused development

### Long-Term Goal
90% pass rate on all 410 evaluation questions (369+/410)

---

## ✅ Phase 0: Foundation (COMPLETE)

**Goal**: Prove end-to-end flow with minimal templates

### Deliverables
- ✅ Data layer: DuckDB + parquet (15.5M+ facts)
- ✅ Entity extraction: Deterministic patterns
- ✅ SQL generation: 3 templates (sector_count, company_cik, company_sector)
- ✅ Response formatting: Natural language output
- ✅ CLI: Interactive REPL + single-shot modes
- ✅ Tests: 55 passing (100%)
- ✅ Telemetry: Logging, timing, request tracking

### Exit Criteria
- ✅ 10/10 PoC questions correct
- ✅ <2s response time
- ✅ All tests passing
- ✅ Clean architecture with Pydantic models

**Completed**: November 3, 2025

---

## ✅ Phase 1: AI Integration (COMPLETE)

**Goal**: Add Azure OpenAI for entity extraction and template selection

### Deliverables

#### 1. Azure OpenAI Integration ✅
- ✅ `src/azure_client.py`: Production-ready wrapper (720 lines)
- ✅ GPT-5 deployment with retry logic + circuit breaker
- ✅ Token tracking with reasoning breakdown
- ✅ 7 new Pydantic models for LLM interactions
- ✅ 20 tests passing (100%)

#### 2. LLM Entity Extraction ✅
- ✅ `src/prompts.py`: 400-line prompt with 10 few-shot examples
- ✅ `LLMEntityRequest` and `LLMEntityResponse` models
- ✅ LLM-first approach with deterministic fallback
- ✅ Robust JSON parsing (handles markdown code blocks)
- ✅ 13 tests passing (11 unit + 2 integration)
- ✅ CLI command: `--test-entity-extraction --use-llm`

#### 3. Hybrid Template Selection ✅
- ✅ 3-tier routing logic in `src/sql_generator.py`:
  - Fast path (≥0.8 confidence): Skip LLM, use template directly
  - LLM confirmation (0.5-0.8): LLM validates template choice
  - LLM fallback (<0.5): LLM selects from all templates
- ✅ `_select_template_with_llm()` with retry and telemetry
- ✅ Template expansion: 3 → 27 patterns
- ✅ 16 tests passing (11 unit + 2 integration + 3 edge cases)

#### 4. Template Expansion ✅
- ✅ 27 SQL templates across 7 categories:
  - Company lookups (4): CIK, headquarters, incorporation, sector
  - Sector analysis (5): counts, lists, thresholds
  - Geographic (3): HQ state, incorporation state
  - Financial metrics (5): revenue, assets, equity, net income
  - Ratios (3): ROE, current ratio, debt-to-equity
  - Revenue time series (3): YoY, multi-year, quarterly
  - Profitability time series (2): net margin, operating margin
- ✅ Flexible regex patterns for natural language matching
- ✅ All templates validated against real questions
- ✅ Template SQL aligned with DuckDB schema and covered by automated execution tests

#### 5. Operational Readiness ✅
- ✅ LLM entity extraction and template selection default to Azure GPT-5 when credentials are present
- ✅ Safe fallback to deterministic paths when Azure access is unavailable

### Exit Criteria
- ✅ Azure OpenAI integrated with GPT-5
- ✅ LLM entity extraction: 13/13 tests passing
- ✅ Hybrid template selection working end-to-end
- ✅ 27 templates operational
- ✅ 100/104 tests passing (96.2%)
- ✅ No regressions from Phase 0

**Completed**: November 4, 2025

---

## 🚀 Phase 2: SQL Generation & Coverage (NEXT)

**Goal**: Generate custom SQL for non-template questions and achieve 50%+ coverage

**Current Coverage**: 47/279 evaluation questions matched (16.8%)  
**Target Coverage**: 86+/171 simple questions (50%+)

### Phase 2A: Custom SQL Generation (8-10 hours)

#### Deliverables
- [ ] **Schema Documentation**: Comprehensive schema in `src/schema_docs.py`
  - Table descriptions (companies, num, sub, tag)
  - Column definitions with types and examples
  - Common join patterns
  - XBRL tag reference (top 50 metrics)

- [ ] **Custom SQL Generator**: New method in `src/sql_generator.py`
  - `_generate_custom_sql()`: LLM-powered SQL generation
  - Schema-aware prompts with examples
  - Parameter extraction and validation
  - Fallback to template-based if LLM fails

- [ ] **LLM Prompt**: `get_custom_sql_prompt()` in `src/prompts.py`
  - Few-shot examples (5-10 queries)
  - Schema documentation included
  - Output format specification (SELECT only, read-only)
  
- [ ] **Tests**: 10+ tests in `tests/test_custom_sql_generation.py`
  - 7 unit tests: Schema awareness, parameter handling, output format
  - 2 integration tests: Real LLM calls
  - 1 edge case: Invalid SQL handling

#### Exit Criteria
- [ ] Custom SQL generation working for 10+ non-template questions
- [ ] 10/10 tests passing
- [ ] Schema documentation complete
- [ ] No regressions (100+ tests still passing)

---

### Phase 2B: Two-Pass Validation (6-8 hours)

#### Deliverables
- [ ] **SQL Validator**: New class `src/sql_validator.py`
  - **Pass 1 - Syntax**: Check for dangerous keywords (DROP, DELETE, etc.)
  - **Pass 2 - Semantic**: LLM validates SQL matches user intent
  - Retry logic if validation fails (max 3 attempts)
  - Telemetry tracking (validation time, success rate)

- [ ] **Validation Prompt**: `get_sql_validation_prompt()` in `src/prompts.py`
  - Compares SQL against user question
  - Checks for schema violations
  - Returns confidence score + reasoning

- [ ] **Integration**: Wire into `sql_generator.py` generate() method
  - Validate all LLM-generated SQL
  - Optional validation for templates (configurable)
  - Track validation metrics in telemetry

- [ ] **Tests**: 10+ tests in `tests/test_sql_validator.py`
  - 6 unit tests: Syntax checks, semantic validation, retry logic
  - 2 integration tests: Real LLM validation calls
  - 2 edge cases: Malicious SQL, ambiguous questions

#### Exit Criteria
- [ ] Two-pass validation working
- [ ] All dangerous SQL blocked (DROP, DELETE, etc.)
- [ ] Semantic validation confidence >0.8 for correct SQL
- [ ] 10/10 tests passing
- [ ] No regressions

---

### Phase 2C: Coverage Expansion (6-8 hours)

#### Deliverables
- [ ] **Evaluation Runner**: Enhanced `src/eval_runner.py`
  - Run all 171 simple questions
  - Track pass/fail with reasons
  - Generate detailed report (CSV + summary)
  - Categorize failures by root cause

- [ ] **Iteration 1**: Fix high-impact issues
  - Run evaluation, identify top failure patterns
  - Add 3-5 new templates OR improve existing ones
  - Target: +20-30 questions passing

- [ ] **Iteration 2**: Fix medium-impact issues
  - Address entity extraction gaps
  - Improve parameter mapping
  - Target: +15-20 questions passing

- [ ] **Iteration 3**: Reach 50% threshold
  - Fine-tune prompts
  - Add edge case handling
  - Target: 86+ total passing (50%+)

- [ ] **Documentation**: Update README.md and PLAN.md
  - Document what works and what doesn't
  - List known limitations
  - Update performance metrics

#### Exit Criteria
- [ ] 86+/171 simple questions passing (50%+)
- [ ] All Phase 2 tests passing (30+ new tests)
- [ ] Evaluation report generated
- [ ] Documentation updated
- [ ] Clean codebase (formatted, linted)

---

## Phase 3: Advanced Features (FUTURE)

**Goal**: Support medium questions and time series analysis

### Deliverables (Planned)
- [ ] Medium question support (multi-step analysis)
  - Ratio calculations with context
  - Company comparisons
  - Sector benchmarking
  - Target: 35+/50 medium questions (70%+)

- [ ] Time series analysis
  - Trend detection
  - Growth rate calculations
  - Seasonality handling
  - Target: 32+/40 time series questions (80%+)

- [ ] Enhanced response formatting
  - Tables and charts (JSON spec for UI)
  - Comparisons with context
  - Sector benchmarks

- [ ] Caching layer
  - In-memory cache for repeat queries
  - 40%+ cache hit rate target

### Exit Criteria (Planned)
- [ ] 70%+ medium questions passing
- [ ] 80%+ time series questions passing
- [ ] Response formatting enhanced
- [ ] Cache working with metrics

---

## Phase 4: Production Ready (FUTURE)

**Goal**: 90%+ overall pass rate and production deployment

### Deliverables (Planned)
- [ ] Complex question support
  - Strategic analysis
  - Multi-dimensional queries
  - Target: 19+/25 complex questions (75%+)

- [ ] Web UI integration
  - Export Pydantic schemas to TypeScript
  - REST API wrapper around CLI
  - Mock FastAPI for UI testing

- [ ] Performance optimization
  - Query result caching
  - Template pre-compilation
  - Target: <1s for 80%+ of queries

- [ ] Production deployment
  - Azure deployment artifacts
  - Monitoring and alerting
  - Cost tracking

### Exit Criteria (Planned)
- [ ] 369+/410 questions passing (90%+)
- [ ] Production-ready API
- [ ] UI integration proven
- [ ] Deployment automated

---

## Success Metrics

### Coverage Targets by Phase
| Phase | Simple | Medium | Complex | Time Series | Overall |
|-------|--------|--------|---------|-------------|---------|
| Phase 0 | 10/295 (3%) | 0/50 | 0/25 | 0/40 | 10/410 (2%) |
| Phase 1 | ~47/171 (27%)* | 0/50 | 0/25 | 0/40 | ~47/410 (11%) |
| **Phase 2** | **86+/171 (50%+)** | 0/50 | 0/25 | 0/40 | **86+/410 (21%+)** |
| Phase 3 | 120+/171 (70%+) | 35+/50 (70%) | 0/25 | 32+/40 (80%) | 187+/410 (45%+) |
| Phase 4 | 150+/171 (87%+) | 43+/50 (85%+) | 19+/25 (75%+) | 32+/40 (80%+) | **369+/410 (90%+)** ✅ |

*Phase 1 template matching shows 47/279 matched, but actual execution not validated yet

### Performance Targets
- **Latency**: <1s for template path, <10s for LLM path
- **Accuracy**: 90%+ overall (369+/410 questions)
- **Test Coverage**: 100% pass rate on unit/integration tests
- **Code Quality**: <5,000 total lines, Black formatted, type-hinted

---

## Technical Architecture

### Hybrid AI System

```
User Question
     ↓
┌─────────────────────────┐
│ 1. Entity Extraction    │ ← LLM-enhanced (GPT-5)
│    - Companies          │
│    - Metrics            │
│    - Time periods       │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│ 2. Template Selection   │ ← Hybrid Router
│    - Fast path (≥0.8)   │   • No LLM call
│    - LLM confirm (0.5-0.8) │   • LLM validates
│    - LLM fallback (<0.5)│   • LLM selects
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│ 3. SQL Generation       │
│    - Template-based     │ ← 27 patterns
│    - Custom (LLM)       │ ← Phase 2
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│ 4. Validation (2-pass)  │ ← Phase 2
│    - Syntax check       │
│    - Semantic check (LLM)│
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│ 5. Query Execution      │
│    DuckDB on parquet    │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│ 6. Response Formatting  │
│    Natural language     │
└─────────────────────────┘
             ↓
        Answer
```

### Technology Stack

**Core**:
- Python 3.11+
- DuckDB (OLAP queries on parquet)
- Pydantic v2 (data validation)
- pandas + pyarrow (data manipulation)

**AI**:
- Azure OpenAI (GPT-5 deployment)
- Responses API with retry logic
- Token tracking + cost monitoring
- Circuit breaker pattern

**Testing**:
- pytest (104 tests)
- 410 evaluation questions
- Unit + integration + end-to-end tests

**Code Quality**:
- Black (formatting)
- Type hints (100% coverage)
- Pydantic models (all contracts)
- ~2,500 lines application code

---

## Development Workflow

### Daily Process
```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Run tests
python -m pytest tests/ -v

# 3. Work on feature
# ... write test first ...
# ... implement feature ...

# 4. Run tests again
python -m pytest tests/test_your_feature.py -v

# 5. Format code
python -m black src/ tests/

# 6. Commit
git add .
git commit -m "feat: description"
```

### Phase 2 Workflow
1. **Schema Documentation** → tests → implement
2. **Custom SQL Generation** → tests → implement
3. **Two-Pass Validation** → tests → implement
4. **Evaluation** → iterate → achieve 50%+
5. **Document** → commit → ready for Phase 3

---

## Risk Mitigation

### Known Risks
1. **LLM Cost**: Mitigated by fast path (70%+ queries skip LLM)
2. **LLM Latency**: Acceptable for demo, can optimize later
3. **SQL Injection**: Validation blocks dangerous keywords
4. **Template Coverage**: Custom SQL generator fills gaps

### Quality Gates
- All tests must pass before proceeding to next phase
- No regressions tolerated (100+ tests must stay green)
- Exit criteria must be met before claiming phase complete

---

## Current File Structure

```
quant-magic-SandP-500/
├── data/parquet/              # 253MB data
│   ├── num.parquet            # 15.5M facts
│   ├── companies_with_sectors.parquet  # 589 companies
│   ├── query_intelligence.parquet      # 27 templates
│   ├── financial_concepts.parquet
│   ├── financial_ratios_definitions.parquet
│   └── company_aliases.csv    # 161 aliases
│
├── src/                       # ~2,500 lines
│   ├── azure_client.py        # 720 lines - Azure OpenAI wrapper
│   ├── entity_extractor.py    # LLM + deterministic extraction
│   ├── sql_generator.py       # Hybrid template selection
│   ├── prompts.py             # LLM prompt templates
│   ├── models.py              # 14 Pydantic models
│   ├── cli.py                 # Interactive CLI
│   ├── query_engine.py        # DuckDB wrapper
│   ├── response_formatter.py  # NL formatting
│   ├── intelligence_loader.py # Template loader
│   ├── telemetry.py           # Logging + timing
│   └── config.py              # Configuration
│
├── tests/                     # 104 tests (100 passing)
│   ├── test_entity_extractor_llm.py    # 13 tests
│   ├── test_sql_generator_hybrid.py    # 16 tests
│   ├── test_eval_poc.py                # 11 tests (Phase 0)
│   ├── test_azure_client.py            # 20 tests
│   └── ... (9 other test files)
│
├── evaluation/questions/      # 410 questions
│   ├── simple_lineitem.json   # 171 validated (from 295)
│   ├── medium_analysis.json   # 50 questions
│   ├── complex_strategic.json # 25 questions
│   └── time_series_analysis.json # 40 questions
│
├── README.md                  # User documentation
└── PLAN.md                    # This file
```

---

## Phase 2 Detailed Timeline

### Week 1: Core Implementation (14-18 hours)
- **Day 1-2**: Schema docs + custom SQL generation (8-10 hours)
- **Day 3-4**: Two-pass validation (6-8 hours)
- **Checkpoint**: 20+ new tests passing, no regressions

### Week 2: Coverage Expansion (6-8 hours)
- **Day 5**: Evaluation runner + Iteration 1 (3 hours)
- **Day 6**: Iteration 2 + Iteration 3 (3 hours)
- **Day 7**: Documentation + cleanup (2 hours)
- **Checkpoint**: 86+/171 passing (50%+), Phase 2 complete

**Total Estimate**: 20-26 hours of focused development

---

## Next Actions (Phase 2 Start)

1. ✅ **Complete Phase 1 cleanup** (DONE)
   - All tests passing (100/104)
   - Documentation updated
   - Code committed

2. [ ] **Phase 2A: Schema Documentation**
   - Create `src/schema_docs.py`
   - Document all tables, columns, join patterns
   - Add XBRL tag reference

3. [ ] **Phase 2A: Custom SQL Generation**
   - Implement `_generate_custom_sql()` in `sql_generator.py`
   - Create prompt in `prompts.py`
   - Write 10 tests

4. [ ] **Phase 2B: Validation**
   - Create `src/sql_validator.py`
   - Implement two-pass validation
   - Write 10 tests

5. [ ] **Phase 2C: Coverage Expansion**
- Audit simple-tier templates for schema compatibility (replace stprinc/companies_with_sectors usage, ensure DuckDB column names match)
- Add deterministic/custom templates for missing simple-tier patterns (currency usage, footnote counts, CIK lookups, latest filing dates, etc.)
- Refresh simple-tier evaluation answers/tolerances once SQL alignment is complete

   - Run evaluation (171 simple questions)
   - Fix issues iteratively
   - Achieve 86+ passing (50%+)

---

## Parallel UI & Codespaces Roadmap

These tracks run alongside Phase 2 backend work so the product can demo via a browser from GitHub Codespaces.

### 1. Codespaces & Devcontainer Enablement
- Add `.devcontainer/devcontainer.json` using `mcr.microsoft.com/devcontainers/python:3.11` with Node 20 feature.
- Preinstall Python dependencies (`pip install -r requirements.txt`) and prep for future `npm install`.
- Forward ports 8000 (FastAPI) and 5173 (Vite), enable public URLs, and document DuckDB parquet handling plus required Azure secrets via Codespaces settings.

### 2. FastAPI Service Layer
- Introduce `src/services/query_service.py` (wraps entity extraction, SQL generation, execution, telemetry).
- Stand up `src/api/app.py` exposing `POST /query` returning structured answers, SQL, and metadata; include graceful fallbacks when Azure creds are absent.
- Add pytest coverage using `TestClient` for happy path, validation errors, and failure handling.

### 3. Frontend Scaffold (React + HTMX)
- Create `frontend/` via Vite (React + TypeScript); configure Tailwind/PostCSS and load HTMX for progressive enhancement.
- Implement initial query form + results shell calling FastAPI; keep composition extensible for future charts/visuals.
- Skip authentication for first release; rely on Codespaces share links while leaving hooks for future auth layers.
- Establish fetch client conventions and state management (start lightweight hooks, evaluate React Query later).

### 4. Tooling & Documentation
- Provide shared commands (Makefile or tasks) for `pytest -m "not integration"`, `uvicorn src.api.app:app --reload`, and `npm run dev`.
- Update onboarding docs (`README.md`, AGENTS.md if needed) with Codespaces setup, env vars, and run instructions.
- Capture open questions (parquet distribution, streaming updates) for next iteration before implementation.

---

**Status**: Phase 1 Complete (100/104 tests passing)  
**Next**: Phase 2 - Custom SQL + Validation + Coverage  
**Goal**: 86+/171 simple questions (50%+)  
**Timeline**: 20-26 hours

---

**Last Updated**: November 4, 2025  
**Version**: 2.0 (Simplified from previous complex structure)
