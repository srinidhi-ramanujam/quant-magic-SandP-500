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
- **What’s ready (use as-is)** — questions already backed by checked-in templates in `sql_templates/`:
  - TS_001 profit_margin_consistency_trend
  - TS_003 debt_reduction_progression
  - TS_004 current_ratio_trend
  - TS_005 operating_margin_delta
  - TS_006 roe_revenue_divergence
  - TS_007 working_capital_cash_cycle_trend
  - TS_008 gross_margin_trend_sector
  - TS_009 inventory_turnover_trend
  - TS_010 net_debt_to_ebitda_trend
  - TS_011 asset_turnover_trend
  - TS_012 cfo_to_net_income_trend
  - TS_019 semiconductor_roe_trend
  - TS_022 equity_to_assets_ratio_trend
  - TS_023 operating_cf_volatility_sector
- **What to build (TODO) and where** — author new templates under `sql_templates/<template>.sql`, then wire intents + ground truth:
  - TS_013 energy_roe_threshold_detector
  - TS_014 fcf_to_capex_trend
  - TS_015 shareholder_return_trend
  - TS_016 top_tech_cfo_trend
  - TS_017 ebitda_margin_improvement_rank
  - TS_018 cash_to_assets_ratio_trend
  - TS_020 hardware_gross_margin_trend
  - TS_021 bank_roe_consecutive_threshold
  - TS_024 cross_sector_gross_margin_spread
  - TS_025 healthcare_cfo_to_capex_ratio_trend
  - TS_026 cloud_margin_pre_post_covid
  - TS_027 pc_maker_gross_margin_lockdown_compare
  - TS_028 energy_fcf_pre_post_covid
  - TS_029 airlines_net_debt_to_ebitda_recovery
  - TS_030 omnichannel_cash_conversion_cycle_segments
  - TS_031 bank_equity_to_assets_pre_post
  - TS_032 healthcare_cash_to_assets_buffer
  - TS_033 semiconductor_roe_momentum
  - TS_034 staples_margin_inflation_spread
  - TS_035 cross_sector_cfo_to_capex_ratio_shift
  - TS_036 retail_revenue_growth_inventory_turnover_compare
  - TS_037 specialty_retail_operating_margin_recovery
  - TS_038 parcel_cfo_recovery_timeline
  - TS_039 airline_interest_coverage_rebuild
  - TS_040 trucking_gross_margin_normalization
  - TS_041 healthcare_cfo_vs_net_income_quality
  - TS_042 vaccine_capex_intensity_window
  - TS_043 biotech_cash_to_assets_liquidity
  - TS_044 bank_roe_band_monitor
  - TS_045 bank_loan_loss_provision_trend
  - TS_046 regional_bank_net_interest_income_shift
- **Priority starting points (map of Plan items → TS/template)** — do these first to clear the 28 plan items:
  1) Industrials WC compression → TS_007 (Ready)
  2) Staples gross-margin trend → TS_008 (Ready; set sector=Staples, 2019–2023)
  3) Large US banks ROE ≥12% streak → TS_021 (Build)
  4) Equity-to-assets ratio JPM/BAC/Citi/WFC → TS_022 (Ready)
  5) Financials OCF volatility → TS_023 (Ready)
  6) Staples vs Discretionary gross-margin divergence → TS_024 (Build)
  7) Healthcare CFO-to-capex ratios → TS_025 (Build)
  8) Cloud software operating margin acceleration → TS_026 (Build)
  9) Apple/Dell/HP gross margins (supply-chain) → TS_027 (Build)
  10) Exxon/Chevron/Conoco FCF swing → TS_028 (Build)
  11) US airlines net-debt-to-EBITDA reversion → TS_029 (Build)
  12) WMT/TGT/COST inventory turnover + CCC → TS_030 (Build)
  13) Large banks equity-to-assets bands → TS_031 (Build)
  14) Pfizer/J&J/Merck cash-to-assets → TS_032 (Build)
  15) Semiconductor ROE growth vs baseline → TS_033 (Build)
  16) Staples gross-margin compression (pre-COVID→inflation) → TS_034 (Build)
  17) Tech/Energy/Industrials CFO-to-capex lift → TS_035 (Build)
  18) WMT/TGT/COST revenue growth + inv turnover → TS_036 (Build)
  19) Specialty retailers post-COVID operating margin → TS_037 (Build)
  20) UPS/FedEx/XPO OCF recovery → TS_038 (Build)
  21) Airline interest coverage → TS_039 (Build)
  22) Trucking/logistics gross-margin normalization → TS_040 (Build)
  23) Healthcare providers/device makers OCF vs NI → TS_041 (Build)
  24) Pfizer/Moderna/J&J capex intensity → TS_042 (Build)
  25) Biotech majors cash-to-assets → TS_043 (Build)
  26) Top US banks ROE bands ±200 bps → TS_044 (Build)
  27) Quarterly loan-loss provisions JPM/BAC/Citi/WFC → TS_045 (Build)
  28) Regional banks NII vs interest expense → TS_046 (Build)
- **How to build/verify each template (repeatable loop)**:
  1) Author SQL in `sql_templates/<template>.sql` with parameters (sector/company filters, fiscal window, thresholds/limits, SIC bounds, coverage/null guards).
  2) Register intent: update `data/template_intents.json` + parquet; run `python scripts/export_template_intents.py` then `python scripts/build_vector_store.py`.
  3) Ground truth: edit the matching entry in `evaluation/questions/time_series_analysis.json` (sample_data, business_insight, key_findings) and add/update `time-series-validator.csv` (Question_ID, SQL_template, expected summary).
  4) Verify: `python -m src.cli "<question>" --debug` and `python scripts/run_eval_suite.py --question "<question>" --no-json`; confirm template ID chosen, row counts sensible, validator pass.
  5) Tests: add/extend `tests/test_sql_templates.py` for parameter substitution/selection and validator confidence where relevant.
  6) Formatter: ensure `response_formatter` emits narrative + table with `truncated` guard for the new template.
- **Exit**: 25/25 time-series questions hit templates (no custom SQL), validation clean, tables render, workbook logs template IDs and row counts.

### Feature: Medium-Complexity Analysis Templates (Planned)
- Design 20 reusable templates (comparatives, rankings, deltas: margin/revenue/ROE divergences, EBITDA/FCF quality, acquisition thresholds, sector swaps).
- Register intents and regenerate vector store; expand few-shots for medium phrasing.
- Enhance entity extractor for fiscal-period and comparative language.
- Add unit tests for selection/parameter inference; validator tests for ranking/aggregation semantics.
- Map medium eval questions (50 active in `medium_analysis_v3.json`) to templates; refresh expected answers where needed.
- **Acceptance (per task)**: Parameterized template checked in; intent registered + vector store rebuilt; grounded expected answer/table in medium JSON; CLI + eval command for mapped question passes with template ID logged; regression test added (selection + validator).

- **Completed this phase**
  - Added templates/intents + vector store for: operating_margin_rebound_sector, capital_allocation_spike_screen, leverage_coverage_comparison, fcf_quality_screen, payout_ratio_leaderboard, gross_margin_sector_spread, working_capital_efficiency_compare, capex_intensity_rank, growth_profitability_quadrant; reused roe_revenue_divergence and asset_turnover_trend for ROE divergence and asset turnover asks.
  - Mapped 11 medium questions in `medium_analysis_v3.json` to these template_ids; rebuilt `query_intelligence.parquet` and `template_intents.json`; added regression cases in `tests/test_sql_templates.py`.
  - Entity extractor broadened for comparative phrasing and relative time spans (last N quarters/years, pre/post-COVID) with tests.

- **Pending to finish the feature**
  - Wire the new templates into CLI/UI flows and `run_eval_suite.py` so medium suite exercises them end-to-end (add parameter defaults/sample runs).
  - Refresh expected answers/tolerances in `medium_analysis_v3.json` for newly mapped questions; add workbook log entries via eval runs.
  - Expand few-shots/intent examples for broader phrasing (e.g., growth/profit quadrant, leverage-only phrasing) and verify router confidence ≥0.8.
  - Run CLI and eval suite for mapped medium questions; capture results in `EVAL_WORKBOOK.csv` and address any misses.

- **Planned tasks (initial 12)**:
  1) Revenue growth vs ROE divergence (identify companies with rising revenue but falling ROE; rank deltas). **Covered:** `roe_revenue_divergence`
  2) Multi-year operating margin rebound by sector (post-COVID vs pre) with thresholds and limits. **Covered:** `operating_margin_rebound_sector`
  3) EBITDA margin improvement rank with revenue floors (sector-agnostic). **Covered:** use `operating_margin_rebound_sector`/existing margin deltas; add EBITDA variant if needed.
  4) Acquisition/threshold screen (e.g., M&A spend or capex-to-revenue spikes) with parameterized thresholds. **Covered:** `capital_allocation_spike_screen`
  5) Debt-to-equity and interest coverage comparative screen across cohorts. **Covered:** `leverage_coverage_comparison`
  6) FCF quality screen (CFO vs net income) with sector filters and outlier caps. **Covered:** `fcf_quality_screen`
  7) Dividend + buyback payout ratio leaderboard relative to CFO for top cohorts. **Covered:** `payout_ratio_leaderboard`
  8) Gross-margin spread comparisons between two sectors over a multi-year window. **Covered:** `gross_margin_sector_spread`
  9) Working-capital efficiency comparisons (DSO/DIO/DPO) across two sectors. **Covered:** `working_capital_efficiency_compare`
  10) Asset turnover rank within sector with revenue/SIC filters. **Covered:** `asset_turnover_trend`
  11) Capex intensity rank within sector with revenue floors and SIC ranges. **Covered:** `capex_intensity_rank`
  12) Top-N growth vs profitability quadrant (high growth + high margin) with tunable cutoffs. **Covered:** `growth_profitability_quadrant`
- **Exit**: ≥10 medium questions routed to templates (no custom SQL) with validator confidence ≥0.8; workbook shows template IDs and intent confidence; CLI + eval suite runs pass for mapped questions.

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
