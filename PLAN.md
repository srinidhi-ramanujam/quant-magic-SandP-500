# Agile Delivery Plan — S&P 500 Financial Analysis Platform

**Product Goal**: Natural language → SQL → analysis for S&P 500.  
**Quality Targets**: Simple ≥50% at quality=5 (86+/171), Time-series 100% of curated set, Medium ≥30% pilot at quality=5, Overall long-term 90%+ (369+/410).  
**Test Baseline**: 100 passing / 2 skipped / 2 xfailed (latest recorded).

---

## Task Management (bd/beads)
- Track all work in `bd`. Before coding, run `bd ready --json` and claim the task with `bd update <id> --status in_progress`.
- No markdown TODOs or external trackers; commit `.beads/issues.jsonl` with related code changes.
- Link discovered work with `bd create ... --deps discovered-from:<parent-id>` and close tasks via `bd close <id> --reason "Completed"`.

## Epic: Data Layer

### Feature: Parquet Catalog & DuckDB Access (Done)
- Curate parquet sources (`data/parquet/`) for facts (15.5M+), companies (589), template metadata, and catalogs.
- Expose DuckDB-backed `QueryEngine` helpers; keep parquet read-only.

### Feature: Schema Docs & Joins (Done)
- Generate schema docs (`src/schema_docs.py`) with table/column catalog, join hints, and metric taxonomy surfaced to prompts.

### Feature: Data Quality & Refresh (Planned)
- Add lightweight sanity checks (row counts, null thresholds) before releases.
- Document refresh playbook for parquet swaps and expected-answer updates.

---

## Epic: Semantic Layer (LLM + Templates + Validation)

### Feature: Core Template Engine (Done)
- Hybrid routing in `sql_generator.py` with deterministic templates, LLM confirmation, and fallback.
- Entity extraction (`entity_extractor.py`) with LLM + deterministic + hybrid retriever.
- Azure client with retry/circuit breaker; Pydantic contracts; telemetry hooks.

### Feature: Custom SQL Generation & Two-Pass Validation (Done)
- Custom SQL path with prompt/few-shots, read-only enforcement, schema guardrails.
- Two-pass validator (`sql_validator.py`): static scan + LLM semantic verdict; telemetry on every attempt.
- Tests for generation, validation, guardrails, and telemetry.

### Feature: Time-Series Templates (In Progress)
- Parameterized templates live in `sql_templates/` (e.g., `asset_turnover_trend.sql`, `cfo_to_net_income_trend.sql`, `current_ratio_trend.sql`, `operating_margin_delta.sql`, `gross_margin_trend_sector.sql`, `inventory_turnover_trend.sql`, `working_capital_cash_cycle_trend.sql`, `net_debt_to_ebitda_trend.sql`, `semiconductor_roe_trend.sql`, etc.).
- **Work Recipe (apply per time-series question)**:
  1) Author/adjust template SQL with parameters (sector/company filters, fiscal window, thresholds, limits, SIC bounds, coverage guards, casing-safe tags) in `sql_templates/<template_id>.sql`.
  2) Register intent in `data/parquet/query_intelligence.parquet` + `data/template_intents.json`; rebuild vector store (`python scripts/export_template_intents.py` then `python scripts/build_vector_store.py`).
  3) Ground truth via DuckDB/QueryEngine; update `evaluation/questions/time_series_analysis.json` (sample_data, business_insight, key_findings) and `time-series-validator.csv`.
  4) Formatter: ensure `response_formatter` emits narrative + table (`truncated` flag) with any bespoke phrasing.
  5) Verify: `python -m src.cli "<question>" --debug` and `python scripts/run_eval_suite.py --question "<question>" --no-json`; confirm template ID, validator pass, row counts.
  6) Tests: add/extend regression in `tests/test_sql_templates.py` (parameter substitution/selection, validator confidence).
- **Acceptance (per task)**: Parameterized template checked in; intent registered + vector store rebuilt; grounded expected answer/table in JSON + validator CSV; CLI + eval command pass with template ID logged; regression test added.
- **Pending tasks (28)** — convert each into a reusable parameterized template following the recipe:
  1) Industrials working capital compression FY2020–FY2023; cash conversion cycle impact.
  2) Consumer Staples gross-margin trend FY2019–FY2023; inflation resilience.
  3) Large US banks ROE ≥12% streak 2021–2023.
  4) Equity-to-assets ratio JPM/BAC/Citi/WFC 2019–2024.
  5) Financials operating cash flow volatility (coef of variation) quarterly 2021–2023.
  6) Staples vs Discretionary gross-margin divergence 2019–2024 quarterly.
  7) Healthcare CFO-to-capex ratios 2019–2024.
  8) Cloud software (MSFT/ADBE/CRM) operating margin acceleration post-COVID vs pre.
  9) Apple/Dell/HP gross margins pre-COVID vs supply-chain disruption.
  10) Exxon/Chevron/Conoco FCF swing 2018–2019 vs 2021–2022.
  11) US airlines net-debt-to-EBITDA reversion to pre-COVID by 2023.
  12) Walmart/Target/Costco inventory turnover + CCC across pre/lockdown/normalization.
  13) Large banks equity-to-assets bands during 2020–2021 and reversion by 2023.
  14) Pfizer/J&J/Merck cash-to-assets pre-COVID vs vaccine scale-up.
  15) Semiconductor ROE growth 2021–2023 vs 2018–2019.
  16) Consumer staples gross-margin compression pre-COVID to 2022 inflation.
  17) Tech/Energy/Industrials CFO-to-capex ratio lift post-COVID vs baseline.
  18) Walmart/Target/Costco quarterly revenue growth + inventory turnover lockdown vs restock.
  19) Specialty retailers (HD/LOW/BBY) operating margins post-COVID vs pre-COVID.
  20) UPS/FedEx/XPO operating cash flow recovery and steepest year.
  21) Airline interest coverage 2018–2023.
  22) Trucking/logistics (JBHT/ODFL/KNX) gross-margin trajectory 2021 spike vs 2023 normalization.
  23) Healthcare providers/device makers (UNH/HCA/MDT/ABT) OCF vs net income post-COVID.
  24) Pfizer/Moderna/J&J capex intensity 2020–2022 vs pre-COVID.
  25) Biotech majors (AMGN/GILD/BIIB) cash-to-assets 2018–2019 through 2020–2021.
  26) Top US banks ROE within ±200 bps of pre-COVID during 2020–2021 and reversion by 2023.
  27) Quarterly loan-loss provisions JPM/BAC/Citi/WFC 2018–2023.
  28) Regional banks (PNC/Truist/USB) net interest income vs interest expense zero-rate vs hike era.
- **Exit**: 25/25 time-series questions hit templates (no custom SQL), validation clean, tables render, workbook logs template IDs and row counts.

### Feature: Medium-Complexity Analysis Templates (Planned)
- Design ~10–12 reusable templates (comparatives, rankings, deltas: margin/revenue/ROE divergences, EBITDA/FCF quality, acquisition thresholds, sector swaps).
- Register intents and regenerate vector store; expand few-shots for medium phrasing.
- Enhance entity extractor for fiscal-period and comparative language.
- Add unit tests for selection/parameter inference; validator tests for ranking/aggregation semantics.
- Map medium eval questions (50 active in `medium_analysis_v3.json`) to templates; refresh expected answers where needed.
- **Acceptance (per task)**: Parameterized template checked in; intent registered + vector store rebuilt; grounded expected answer/table in medium JSON; CLI + eval command for mapped question passes with template ID logged; regression test added (selection + validator).
- **Planned tasks (initial 12)**:
  1) Revenue growth vs ROE divergence (identify companies with rising revenue but falling ROE; rank deltas).
  2) Multi-year operating margin rebound by sector (post-COVID vs pre) with thresholds and limits.
  3) EBITDA margin improvement rank with revenue floors (sector-agnostic).
  4) Acquisition/threshold screen (e.g., M&A spend or capex-to-revenue spikes) with parameterized thresholds.
  5) Debt-to-equity and interest coverage comparative screen across cohorts.
  6) FCF quality screen (CFO vs net income) with sector filters and outlier caps.
  7) Dividend + buyback payout ratio leaderboard relative to CFO for top cohorts.
  8) Gross-margin spread comparisons between two sectors over a multi-year window.
  9) Working-capital efficiency comparisons (DSO/DIO/DPO) across two sectors.
  10) Asset turnover rank within sector with revenue/SIC filters.
  11) Capex intensity rank within sector with revenue floors and SIC ranges.
  12) Top-N growth vs profitability quadrant (high growth + high margin) with tunable cutoffs.
- **Exit**: ≥10 medium questions routed to templates (no custom SQL) with validator confidence ≥0.8; workbook shows template IDs and intent confidence.

### Feature: Hybrid Retrieval (Planned/Future)
- Harden FAISS-based entity/template retrieval; measure hit rate vs. LLM fallback.
- Metrics: entity accuracy ≥98%, template hit ≥95%, LLM calls minimized, latency gain ≥30% vs baseline.

### Feature: Business-Ready Response Formatting (Planned)
- Heuristics to emit tables for rankings/aggregations; concise narratives + highlights; warnings on truncation.
- Parity of presentation payload across CLI/API/UI; toggle for raw vs formatted.
- Tests for formatter outputs and CLI contract snapshots.

---

## Epic: Service Layer (CLI + API)

### Feature: CLI Core (Done)
- Interactive and single-shot modes with debug; flags for formatted answers; deterministic fallback when LLM unavailable.

### Feature: FastAPI Service (Done)
- `/health` and `/query` with `QueryService` wiring; mirrors CLI behavior, includes presentation/reasoning/SQL hints; structured errors for LLM unavailability.

### Feature: Stability & Telemetry (Planned)
- Enrich request IDs/latency/component timings in responses; configurable timeouts/retries.
- Add lightweight rate limiting and clearer error surfacing for validator blocks.

---

## Epic: UI (React + Vite)

### Feature: Chat Shell (Done)
- ASCENDION-branded chat, health badge, SQL toggle, highlights/table rendering, auto-resizing input, local session list.

### Feature: UI–Backend Parity (In Progress)
- Ensure `/api/query` responses render identically to CLI (narrative, highlights, tables with `truncated`, reasoning trace, SQL hint).
- Better error/loading states; handle empty SQL gracefully; show request IDs for debug (non-invasive).
- Optional smoke tests (React Testing Library/Cypress) for representative flows.
- **Exit**: Same answers/structure across CLI and UI for sampled simple, time-series, medium questions; health badge reflects LLM availability.

### Feature: Streaming Thinking Trace (Planned)
- Add streaming endpoint `/query/stream` (SSE) that emits start → entities → template/SQL preview → row_count/timings → reasoning tokens → final answer/error, preserving existing `/query`.
- Extend `QueryService` with streaming generator and telemetry/logging; use Azure Responses API streaming where available, fallback to chunked reasoning trace when not.
- UI: consume `/api/query/stream` with EventSource/streaming fetch; render a live “Thinking” panel showing tokens, SQL hint, and row counts; collapse into final answer message and support abort/retry.
- **Exit**: Visible tokens start within ~1–2s during long (≈21s) queries; final payload matches existing answer/sql/presentation/reasoning fields; graceful fallback when streaming disabled.

---

## Epic: Evaluation, Telemetry, and Reporting

### Feature: Eval Runner (Done)
- `scripts/run_eval_suite.py` to run suites (`simple`, `medium`, `time-series`) or custom questions; logs to `evaluation/EVAL_WORKBOOK.csv` and `evaluation/logs/`.

### Feature: Workbook Analytics (Planned)
- Summaries by tier/tag/failure type (template miss, entity miss, SQL error); regression filters; markdown snippet for PRs.
- Nightly/regular baseline runs stored as `RUN_latest` (simple + time-series + selected medium).

### Feature: Test & Formatting Discipline (Ongoing)
- Commands: `python -m pytest -m "not integration"` (fast), `python -m pytest tests/ -v` (full), `python -m black src/ tests/`.
- No new deps beyond `requirements.txt`; no stray files.

---

## Quick Runbooks

- **Connectivity/Smoke**: `source .venv/bin/activate && source .env && python -m src.cli "How many companies are in Technology?" --debug`
- **Eval Suites**: `source .venv/bin/activate && source .env && python scripts/run_eval_suite.py --suite simple --no-json` (add `--suite time-series` / `--suite medium` as needed)
- **API + UI Local**: `./scripts/run_local_ui.sh` (starts uvicorn + Vite; requires `.env` and `frontend/node_modules/`)

---

## Completion Definition (per Epic)
- **Data Layer**: Parquet catalog documented; schema docs current; refresh and quality checks documented.
- **Semantic Layer**: Time-series templates complete and grounded; medium templates live; formatter produces business-ready narratives/tables; validator + retriever telemetry healthy.
- **Service Layer**: CLI/API parity with robust errors, telemetry, and rate/timeout controls.
- **UI**: End-to-end parity with CLI/API including tables/reasoning; resilient health/error states.
- **Evaluation**: Workbook and analytics reflect latest runs; regression alarms on coverage drops; tests and formatting clean.
