# Time-Series Templates — Parallel Run Playbook

Use this to coordinate parallel work on time-series templates. Run prompts in order: master → parallel template prompts (one per template) → integration.

## Master Prompt (run first)
```
Goal: Prepare workspace and shared artifacts for time-series template updates.

Steps:
1) Activate env: `source .venv/bin/activate && source .env`
2) Pull latest changes; ensure on the correct branch.
3) Regenerate template intent vectors (single-threaded):
   - `python scripts/export_template_intents.py`
   - `python scripts/build_vector_store.py`
4) Do NOT edit template SQLs, intents, ground-truth JSON/CSV, or tests in this prompt. Only prep and verify.
5) Smoke check routing baseline:
   - `python -m pytest tests/test_sql_templates.py -k time_series --maxfail=1`
6) If failures, capture logs; stop and notify before parallel prompts.
Output: confirmation that env is set, vectors built, baseline tests pass/fail summary.
```

## Parallel Template Prompts (run independently, one per template)
Use one prompt per template to avoid file conflicts. Each prompt edits ONLY its template SQL, intent entry, ground truth rows, and a new test block.

Template Prompt Skeleton (fill in TEMPLATE_ID and question set)
```
Goal: Fully ground TEMPLATE_ID time-series template with data-backed answers, parameterized SQL, and flexible reuse.

Scope (only these files):
- sql_templates/TEMPLATE_ID.sql
- data/template_intents.json (add/adjust the TEMPLATE_ID entry only)
- evaluation/questions/time_series_analysis.json (add/refresh expected answer rows for TEMPLATE_ID)
- time-series-validator.csv (add/refresh validator rows for TEMPLATE_ID)
- tests/test_sql_templates.py (add a new test function for TEMPLATE_ID routing/params)

Steps:
1) Activate env: `source .venv/bin/activate && source .env`
2) Review the question; confirm required data exists. If data is missing, note the gap early.
3) Verify metadata in JSON (ids, category, difficulty, spans) is accurate.
4) Build expected_answer with actual numbers from parquet (DuckDB). Update sample_analysis SQL, sample_data, business_insight, key_findings, investment_implications.
5) Template: parameterize/adjust sql_templates/TEMPLATE_ID.sql (sector/company/time spans; SIC/revenue floors). If no template, create one.
6) Run SQL via DuckDB and via QueryEngine; reconcile results with JSON/CSV. Align time-series-validator.csv and time_series_analysis.json with verified outputs.
7) Update data/template_intents.json for TEMPLATE_ID with diverse examples (sectors, year ranges, verbs like trend/expand/start-end/start/end levels); keep edits scoped to this block.
8) Tests: append a new test function in tests/test_sql_templates.py asserting routing/parameter fill and non-empty SQL.
9) Do NOT rebuild vectors here. Do NOT touch other templates.
10) Run focused tests:
   - `python -m pytest tests/test_sql_templates.py -k TEMPLATE_ID --maxfail=1`
   - Optional: `python -m pytest -k TEMPLATE_ID --maxfail=1`
Output: summary of edits, data values used, test results, and any TODOs.
```

Recommended TEMPLATE_ID slots to run in parallel:
- asset_turnover_trend
- gross_margin_trend_sector
- operating_margin_delta
- cfo_to_net_income_trend
- working_capital_cash_cycle_trend
- inventory_turnover_trend
- net_debt_to_ebitda_trend

## Integration Prompt (run after all template prompts complete)
```
Goal: Consolidate all parallel changes, rebuild shared artifacts, and run full checks.

Steps:
1) Activate env: `source .venv/bin/activate && source .env`
2) Merge all updates locally (rebasing if needed).
3) Rebuild intents/vectors once:
   - `python scripts/export_template_intents.py`
   - `python scripts/build_vector_store.py`
4) Run extended test sweep:
   - `python -m pytest tests/test_sql_templates.py -k time_series`
   - `python -m pytest -m "not integration" --maxfail=1`
5) Optional targeted evals (sample):
   - `python -m src.cli "<representative time-series question>" --debug`
6) Spot-check JSON/CSV vs SQL outputs for a few updated templates; ensure alignment.
7) Verify no missing files and review `git status` for unintended changes.
8) Summarize outcomes: which templates updated, test results, data gaps flagged, remaining work.
Output: consolidated status ready for PR or further review.
```

## Notes to Avoid Conflicts
- Only one person edits `data/template_intents.json` at a time; if multiple edits are needed, stage locally and merge sequentially before vector rebuild.
- Vector rebuild must be done once in the integration prompt after all intent edits land.
- Append tests as new functions to minimize merge clashes.
- Keep changes template-scoped; avoid touching shared router/formatter code unless coordinated.
