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
- Current state:
  - All 45 time-series eval questions now have `template_id` mappings; `time-series-validator.csv` rebuilt one-row-per-question.
  - Eval run surfaced blocking issues:
    - Router/intent drift: LLM selected unknown IDs (e.g., 53, 99) for TS_004/TS_005; some time-series asks fell back to custom SQL despite mapped templates (TS_003, TS_004, TS_005).
    - Validation failures: `staples_margin_inflation_spread`, `inventory_turnover_trend`, `net_debt_to_ebitda_trend`, `hardware_gross_margin_trend` rejected for tag casing, missing parameters (`use_sector_filter`), or malformed SQL.
    - Parser error: `top_tech_cfo_trend` SQL broke on braces/missing defaults (max_abs_cfo/result_limit/min_revenue).
    - Semantic validator rejections: cohort templates referencing `num.segments` and lowercase company filters (e.g., airline/semi variants).
  - Latest time-series run (RUN_206) failing IDs to fix next:
    - Tag casing: TS_013 (`energy_roe_threshold_detector`).
    - ROE logic/schema: TS_019 (`semiconductor_roe_trend`), TS_033 (`semiconductor_roe_momentum` expected).
    - No-rows returns (param/SQL gaps): TS_016, TS_020–TS_025, TS_027–TS_031, TS_034, TS_037–TS_040, TS_042, TS_044–TS_046 (see workbook for questions/templates).
- Next actions (concrete, run in order):
  1) Rebuild template intelligence/vector store after the latest intent updates (refresh `data/parquet/query_intelligence.parquet` + `template_metadata.parquet`).
  2) Patch/validate failing templates: `staples_margin_inflation_spread`, `inventory_turnover_trend`, `net_debt_to_ebitda_trend`, `hardware_gross_margin_trend`, `top_tech_cfo_trend` (tag casing, required params, remove `num.segments`, sector/company fallbacks, defaults for max_abs_cfo/result_limit/min_revenue).
  3) Tighten deterministic param fill for `use_sector_filter` and company lists; ensure required params across these templates have safe defaults.
  4) Router sanity for TS_003/TS_004/TS_005: confirm LLM template_id stays within allowed set and avoids custom-SQL fallback.
  5) Run `scripts/run_eval_suite.py --suite time-series --no-json`; review `EVAL_WORKBOOK.csv` and `time-series-validator.csv` for template hits + row counts; log any remaining rejects for a follow-up fix.

### Feature: Medium-Complexity Analysis Templates (In Progress)
- Current state:
  - All medium questions now carry `template_id` mappings, but many are mapped to “closest available” templates; coverage is not yet semantically correct.
  - Medium suite run still leans on generic templates; many asks need purpose-built SQL (correlations, seasonality, FX/hedging, ESG/regulatory risk, guidance accuracy).
- Next actions:
  - Author/adjust templates for unmapped or weakly mapped asks (correlation/seasonality/FX/hedging/ESG/guidance).
  - Rebuild intents + vector store after template additions; expand few-shots for comparative and period phrasing.
  - Add grounded expected answers/tolerances in `medium_analysis_v3.json` as templates land; rerun medium suite and capture workbook rows.
  - Strengthen validator coverage for ranking/aggregation semantics and parameter defaults per template.

### Feature: Guided Questions Tier (Planned)
- Goal: Small, repeatable template set powering guided UI deep-dives for sectors and top 10 companies; new eval tier `guided_questions`.
- Templates (sector-focused, reused per sector):
  - `sector_growth_leaders`: top companies by revenue CAGR since 2020 with caps on minimum revenue/sample size.
  - `sector_margin_trend`: operating margin trend last 4 fiscal years, sorted by latest margin.
  - `sector_fcf_stability`: free cash flow level and volatility since 2020.
  - `sector_roic_improvers`: ROIC improvement over last 3 years with baseline/ending levels.
  - `sector_share_gainers`: revenue share gains within sector using CAGR vs peers.
- Templates (company-focused, reused per company):
  - `company_rev_margin_trend`: revenue + operating margin trend since 2020.
  - `company_fcf_stability`: free cash flow level/volatility last 4 fiscal years.
  - `company_peer_margin_compare`: compare company margins vs sector peers last 3 years.
  - `company_segment_growth`: segment/line-of-business growth contribution since 2020.
  - `company_leverage_liquidity`: leverage (debt/equity or net debt/EBITDA) and cash balance change last 4 years.
- Coverage scope:
  - Sectors: Technology, Information Technology, Banking/Financials, Healthcare, Consumer/E-commerce, Industrials/Manufacturing, Energy, Utilities, Communications, Materials.
  - Companies: Apple, Microsoft, Nvidia, Amazon, Alphabet, Tesla, Meta Platforms, JPMorgan Chase, UnitedHealth, Exxon Mobil.
- Tasks (routing-strengthen plan):
  - Tighten guided regex + parameters to beat legacy templates: require both revenue + margin tokens and explicit year windows on company starters; add `start_year`/`end_year` params where missing; ensure peer/segment/leverage patterns demand company and sector context.
  - Raise guided scoring/ordering in `query_intelligence.parquet`/vector store: set intent_category/tier to `guided_questions`, lower thresholds in router only for guided IDs, and rerank guided rows ahead of overlapping legacy patterns.
  - Regenerate `data/parquet/query_intelligence.parquet`, `template_metadata.parquet`, and `artifacts/vector_store/templates_metadata.json` after pattern tweaks so embeddings and defaults align.
  - Add regression tests: pattern-match coverage for all 10 guided questions, router default-param assertions, and CLI/eval harness runs for `--suite guided_questions` (plus a UI smoke that starters hit guided template IDs).
  - Validate sample runs (sector + company) through CLI/UI and eval workbook; keep workbook rows for guided tier runs.

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
