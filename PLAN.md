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

Current status: schema docs + wiring landed, prompt/test scaffolding pending.

#### Deliverables
- [x] **Schema Documentation** (`src/schema_docs.py`)
  - Table/column catalog with join hints
  - Metric taxonomy for top 50 tags
  - Helper accessors surfaced to prompts
- [x] **Custom SQL Generator stub** (`SQLGenerator._generate_custom_sql`)
  - Uses schema docs + LLM fallback when templates miss
  - Deterministic guardrails around empty/invalid SQL
- [x] **Prompt Refinement** (`get_sql_custom_generation_prompt`)
  - Added curated few-shot set covering joins, aggregations, ranking
  - Embedded failure-mode guidance and domain hints (currency, thresholds, ordering)
  - Centralized prompt wiring through Azure client
- [x] **Validation Hooks**
  - Enforce read-only (`SELECT`) queries with multi-statement rejection
  - Require `NUM` joins to pass through `SUB`, block unknown tables
  - Emit telemetry for every custom SQL attempt with pass/fail reason
- [x] **Test Suite** (`tests/test_sql_generator.py`)
  - Unit coverage for prompt assembly, guardrails, telemetry logging
  - Mocked LLM success/failure paths for custom SQL generation
  - Integration smoke behind `ENABLE_AZURE_INTEGRATION_TESTS` (pending credentials toggle)

#### Exit Criteria
- [ ] 10+ non-template evaluation questions answered via custom SQL
- [ ] Prompt/test coverage prevents regressions on schema drift
- [ ] Telemetry shows success rate & latency for custom SQL path
- [ ] No drop in existing deterministic/template coverage

---

### Phase 2B: Two-Pass Validation (6-8 hours)

#### Deliverables
- [x] **SQL Validator** (`src/sql_validator.py`)
  - Pass 1: Static scan for DDL/DML + unbounded deletes/updates
  - Pass 2: LLM intent alignment with structured verdict (`valid`, `reason`, `confidence`)
  - Configurable retry budget surfaced via config
  - Emits telemetry (`sql_validation` + `llm_calls` entries for every attempt)
- [x] **Validation Prompts** (`get_sql_semantic_validation_prompt`)
  - Include schema snippets + natural-language question
  - Require JSON verdict with normalized rationale bullets
  - Provide examples for allow/deny cases via curated instructions
- [x] **Pipeline Integration**
  - Invoke validator for all custom SQL paths (templates remain configurable next)
  - Short-circuit response if validation fails; return actionable error
  - Persist validation metadata on the request context for downstream logging
- [x] **Tests** (`tests/test_sql_validator.py`, `tests/test_sql_generator.py`)
  - Static checks (dangerous SQL, CTE handling)
  - Mocked LLM semantic checks (match/mismatch)
  - Telemetry assertions for success/failure paths

#### Exit Criteria
- [ ] 100% of generated SQL passes static scan before execution
- [ ] Semantic validation confidence ≥0.8 on green paths
- [ ] Workbook entries capture validation outcome & confidence
- [ ] No increase in execution failures during eval sweeps

---

### Phase 2C: Coverage Expansion (6-8 hours)

#### Deliverables
- [x] **Evaluation Runner Enhancements** (`scripts/run_eval_suite.py`)
  - CLI flags for tiers/custom questions
  - Telemetry logging into `evaluation/EVAL_WORKBOOK.csv`
  - Auto-scoring (5/3/1) with tolerance awareness
- [ ] **Workbook Analytics**
  - Add summarizer script for pass-rate by tag/category
  - Reverse chronological ordering (done) + filters for regressions
  - Derive top failure taxonomies (template miss, entity miss, SQL error)
- [ ] **Iteration 1 – High-Impact Fixes**
  - Close remaining simple-tier numeric deltas (gross margin, other income)
  - Add EBITDA / acquisition threshold templates and align expected answers
  - Target ≥150/171 simple-tier scores at 5
- [ ] **Iteration 2 – Medium Tier Prep**
  - Refresh medium/time-series expected answers to match current parquet data
  - Ensure entity extractor & template loader cover fiscal period questions
  - Stand up regression templates for multi-year KPIs (inc. top-10 by sector)
- [ ] **Reporting**
  - Nightly baseline run stored as `RUN_latest`
  - Markdown summary snippet for PRs (pass %, top failures, new fixes)

#### Exit Criteria
- [ ] Simple tier ≥50% coverage with quality=5
- [ ] Medium tier pilot (>30% quality=5) ready for next iteration
- [ ] Regression alarms when template answers drift from parquet data
- [ ] Documented playbook for updating expected answers safely
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

### Time-Series Template Roadmap (NEW)

**Goal**: Land reusable parameterized SQL templates that unlock the curated 25-question time-series suite without ad-hoc LLM work.

| Template Family | Template IDs | Scope / Notes |
|-----------------|--------------|---------------|
| Profitability trends | `profit_margin_consistency_trend`, `consumer_staples_gross_margin_trend`, `hardware_gross_margin_trend`, `cross_sector_gross_margin_spread`, `ebitda_margin_improvement_rank`, `roe_trend_named_semis`, `bank_roe_consecutive_threshold`, `roe_vs_revenue_growth_flag` | Multi-year margin/ROE deltas leveraging revenue, cost, and equity tags plus cohort filters. |
| Cash flow & capital allocation | `sector_free_cash_flow_trend`, `top_tech_cfo_trend`, `cfo_to_net_income_ratio_trend`, `healthcare_cfo_to_capex_ratio_trend`, `operating_cf_volatility_sector` | Operating cash flow contrasted with capex or net income to gauge quality of earnings and reinvestment. |
| Balance sheet health | `current_ratio_trend`, `cash_to_assets_ratio_trend`, `equity_to_assets_ratio_trend`, `working_capital_cash_cycle_trend`, `retail_cash_conversion_cycle_trend` | Liquidity metrics derived from assets/liabilities plus CCC decomposition (DSO/DIO/DPO). |
| Leverage & debt motion | `debt_reduction_progression`, `net_debt_to_ebitda_trend`, `energy_roe_threshold_detector` | Tracks leverage changes, approximated EBITDA, and high-ROE streaks for capital-intensive sectors. |
| Efficiency metrics | `operating_margin_trend`, `inventory_turnover_trend`, `asset_turnover_trend` | Ratio trends based on inventory, revenue, and asset balances; reusable across cohorts. |

**Next Actions**
1. Implement slot extractors + SQL builders for the profitability and cash-flow families (highest coverage impact).
2. Register each template in `data/template_intents.json` with clear natural-language exemplars for FAISS retrieval.
3. Add focused unit tests per family that validate metric math against DuckDB snapshots.
4. Re-run `scripts/run_eval_suite.py --suite time_series` and append telemetry to `evaluation/EVAL_WORKBOOK.csv`.

**Progress (Nov 10)**
- Ground-truthed TS_001 using a DuckDB profit-margin consistency query; JSON + validator entries now include the exact SQL, sample data, and insights, so the `profit_margin_consistency_trend` template has a concrete reference implementation.
- Registered `profit_margin_consistency_trend` in the template catalog / metadata / FAISS store so hybrid retrieval can route Technology profit-margin questions without falling back to the LLM.
- Ground-truthed TS_003 with FY2021-FY2023 total-debt reductions (AT&T, AIG, US Bancorp, Deere, Apple) and shipped the `debt_reduction_progression` template for leverage questions.
- Ground-truthed TS_004 with FY2019-FY2023 Healthcare current-ratio trends (Hologic, ResMed, Zoetis, Cooper, STERIS, IDEXX) and added the `current_ratio_trend` template to the catalog/FAISS store.
- Ground-truthed TS_005 (FY2022→FY2023 Technology operating-margin rebound), refreshed the JSON/validator artifacts with DuckDB-sourced numbers, and registered the new `operating_margin_delta` template (metadata + FAISS) so margin-rebound questions route deterministically.
- Ground-truthed TS_007 by adding the `working_capital_cash_cycle_trend` template, logging FY2020→FY2023 working-capital day reductions (airlines, rail, industrials) and updating JSON/validator artifacts so the CLI produces the curated list deterministically.
- Ground-truthed TS_006 with the `roe_revenue_divergence` template, which now powers ROE-decline-vs-revenue-growth questions end-to-end (DuckDB numbers captured in JSON + validator, FAISS rebuilt, CLI verified).
- Refreshed TS_008 with FY2019→FY2023 Consumer Staples gross-margin deltas (ADM, Constellation, Tyson, PepsiCo, Mondelez, Philip Morris, Monster) and captured the new DuckDB query, insights, and validator metadata ahead of wiring the `gross_margin_trend_sector` template.
- Ground-truthed TS_009 inventory turnover trends for the top six retailers (new `inventory_turnover_trend` template) and logged the run in the telemetry workbook; formatter now summarizes turnover + DIO deltas.
- Ground-truthed TS_010 leverage progression for Delta, Southwest, and United (new `net_debt_to_ebitda_trend` template) with FY2019–FY2023 DuckDB data and documented the dataset gap for American Airlines.
  - Re-validated the DuckDB + QueryEngine outputs on 11 Nov 2025 after tightening the EBITDA guards, reran the CLI end-to-end, and logged RUN_026 in `evaluation/EVAL_WORKBOOK.csv` to capture the refreshed telemetry.

---

### Phase 2D: Hybrid Retrieval Initiative (Next)

**Goal**: Replace LLM-heavy entity extraction and template selection with hybrid (keyword + embedding) retrieval while demonstrating measurable gains.

#### Metrics to Track (Baseline vs. Hybrid)
- **Entity Extraction Accuracy** – % of evaluation questions where all required slots match the expected context (derived from workbook + entity diff script). Target ≥98%.
- **Template Hit Rate** – % of questions routed to the correct template without fallback. Target ≥95%.
- **LLM Reliance** – Average number of LLM calls per question (entity + template + custom SQL). Target near-zero for template-backed queries.
- **Latency** – Median end-to-end time per question (captured in workbook metadata). Target ≥30% improvement vs RUN_020 baseline.
- **Custom SQL Success** – Semantic validator pass rate and latency for the remaining LLM-generated SQL cases to ensure no regressions.

#### Deliverables
- [ ] **Entity Catalog + Embeddings** – Curated dictionaries (sectors, jurisdictions, metrics, time phrases, question types) embedded via `sentence-transformers` and stored in FAISS/Chroma.
- [ ] **HybridEntityRetriever** – Combines existing regex/threshold hints with embedding similarity to produce canonical slot values with confidence.
- [ ] **TemplateIntentRetriever** – Keyword-filter + embedding similarity over template intent cards to select the template without hitting the LLM.
- [ ] **Telemetry & Metrics Script** – Log retrieval confidences/result and ship a notebook/script that compares baseline vs. hybrid runs.
- [ ] **Runbook Updates** – README/PLAN instructions on refreshing embeddings, tuning thresholds, and interpreting the metrics dashboard.

#### Exit Criteria
- [ ] ≥95% of simple-tier questions resolved without LLM entity/template calls.
- [ ] Entity extraction accuracy ≥98% on the evaluation suite.
- [ ] Template hit rate ≥95% with no quality regression.
- [ ] Median latency improvement ≥30% vs. RUN_020.
- [ ] Metrics dashboard attached to PRs demonstrating the improvement.

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

### 1. Codespaces & Devcontainer Enablement ✅
- ✅ Add `.devcontainer/devcontainer.json` using `mcr.microsoft.com/devcontainers/python:3.11` with Node 20 feature.
- ✅ Preinstall Python dependencies (`pip install -r requirements.txt`) and prep for future `npm install`.
- ✅ Forward ports 8000 (FastAPI) and 5173 (Vite), enable public URLs, and document DuckDB parquet handling plus required Azure secrets via Codespaces settings.

### 2. FastAPI Service Layer
- Introduce `src/services/query_service.py` (wraps entity extraction, SQL generation, execution, telemetry).
- Stand up `src/api/app.py` exposing `POST /query` returning structured answers, SQL, and metadata; include graceful fallbacks when Azure creds are absent.
- Add pytest coverage using `TestClient` for happy path, validation errors, and failure handling.

### 3. Frontend Scaffold (React + HTMX) ✅
- ✅ Create `frontend/` via Vite (React + TypeScript); configure Tailwind/PostCSS and load HTMX for progressive enhancement.
- ✅ Implement initial query form + results shell calling FastAPI; keep composition extensible for future charts/visuals.
- ✅ Skip authentication for first release; rely on Codespaces share links while leaving hooks for future auth layers.
- ✅ Establish fetch client conventions and state management (start lightweight hooks, evaluate React Query later).

#### Chat Interface (Completed November 6, 2025)
- ✅ **Production-Ready Chat UI** - Modern chat interface with:
  - Left sidebar (fixed): ASCENDION branding, chat history, quick access menu, settings
  - Main chat area (scrollable): conversation thread with user questions and AI responses
  - Bottom text input with aligned send button and auto-resize
  - API connection status indicator (top right)
  - Color scheme: Professional indigo/blue palette (indigo-600 to blue-500 gradient for user messages)
  - Chat session management and history tracking
  - Built with React + TypeScript + Tailwind CSS + Vite
  - Responsive design with smooth scrolling and animations

### 4. Tooling & Documentation ✅
- ✅ Provide shared commands (Makefile or tasks) for `pytest -m "not integration"`, `uvicorn src.api.app:app --reload`, and `npm run dev`.
- ✅ Update onboarding docs (`README.md`, AGENTS.md if needed) with Codespaces setup, env vars, and run instructions.
- ✅ Document chat interface features, setup, and usage patterns.
- ✅ Capture open questions (parquet distribution, streaming updates) for next iteration before implementation.
- ✅ Add per-session logging (CLI/API/UI) with structured Q&A records rotating via `.logs/session-<timestamp>/`.

### 5. Next UI Enhancements (Planned)

#### A. LLM Answer Polishing Layer
- Add optional “answer formatting” pass in the backend:
  - After SQL execution, call Azure Responses API with the original question, extracted entities, SQL template metadata, and the full result set (capped via row limit / JSON summary) to produce a business-ready narrative.
  - Use existing conversation history (last N question-answer pairs) from the UI payload so the formatter can reference prior context.
- API changes:
  - Extend `QueryResponseModel` with a `presentation` field containing the polished text + optional table schema.
  - Introduce request flag `include_formatted_answer` (default true for API/UI, optional false for CLI).
  - Log formatter prompts/responses in `session_logger` so we can debug bad phrasing.
- Quality gates:
  - Enforce max token usage (e.g., trim table data to top rows with summary stats) to keep formatter responsive.
  - Add tests that stub formatter responses to ensure the API degrades gracefully when the LLM fails (fallback to template formatter).

#### B. Collapsible SQL & Reasoning Trace (UI)
- Backend: continue returning raw SQL + metadata, but add a short “reasoning trace” object (template ID, key filters, constraints) for display. No change for CLI.
- Frontend:
  - Replace the static SQL block with a collapsible panel (default closed) styled like ChatGPT’s reasoning trace. Show summary (“SQL generated via `company_sector` template”) with a toggle to reveal the full query.
  - Add a second panel for the formatter’s explanation so the user can inspect how the answer was synthesized.
  - Maintain accessibility: keyboard-focusable toggles, copy-to-clipboard icon for SQL.
- UX polish:
  - Render tables returned by the formatter using responsive `<table>` components; collapse large datasets into paginated or scrollable areas.
  - Surface formatter errors inline (e.g., “Polished answer unavailable; showing raw summary”).

#### C. Validation & Rollout
- Update `tests/api/test_query_endpoint.py` to cover the new response fields and failure modes.
- Add unit tests for the formatter orchestration (mock Azure client).
- Extend README with “Formatted Answers & SQL Toggle” section describing the behavior and troubleshooting tips.
- Measure impact: capture latency stats for the formatter and expose them in metadata so we can monitor cost/perf.

---

**Status**: Phase 1 Complete (100/104 tests passing)  
**Next**: Phase 2 - Custom SQL + Validation + Coverage  
**Goal**: 86+/171 simple questions (50%+)  
**Timeline**: 20-26 hours

---

**Last Updated**: November 6, 2025  
**Version**: 2.1 (Added Chat Interface)
