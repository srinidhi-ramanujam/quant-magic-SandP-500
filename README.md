# S&P 500 Financial Analysis Platform

A simple, maintainable command-line tool for analyzing S&P 500 financial data using natural language queries.

## Quick Start

```bash
# Setup
cd /Users/Srinidhi/my_projects/quant-magic-SandP-500
source .venv/bin/activate

# Start interactive CLI (recommended)
python -m src.cli --interactive

# Or ask a single question
python -m src.cli "How many companies are in Technology?"

# Verify data layer
python -c "from src.query_engine import QueryEngine; qe = QueryEngine(); print(f'Ready: {qe.count_companies()} companies')"

# Run tests (55 tests, all passing)
python -m pytest tests/ -q
```

---

## Project Overview

### What This Does

Convert natural language questions about S&P 500 companies into SQL queries and return human-readable answers.

**Example Flow:**
```
Question: "How many companies are in the Technology sector?"
   ↓ Entity Extraction
   ↓ SQL Generation
   ↓ Query Execution
   ↓ Response Formatting
Answer: "There are 143 companies in the Information Technology sector."
```

### Current Status

✅ **Phase 0 - PoC Complete** (November 3, 2025)
- End-to-end flow working (10/10 questions correct)
- Interactive CLI with REPL mode
- 55 tests passing (100% pass rate)
- Response time: <1.1s average

✅ **Data Layer**: Complete and tested
- 15.5M+ financial facts from SEC EDGAR filings
- 589 S&P 500 companies with sector classifications
- Optimized parquet storage (253MB)
- DuckDB for fast analytics

✅ **Application Layer**: Phase 0 complete
- Entity extraction (deterministic patterns)
- SQL generation (3 template patterns)
- Response formatting (natural language)
- Telemetry infrastructure (logging, timing, metrics)
- 7 Pydantic v2 models for all contracts

🚀 **Phase 1 - Azure OpenAI Integration Complete** (November 3, 2025)
- ✅ Azure OpenAI Responses API integration
- ✅ Embeddings API infrastructure ready
- ✅ 7 additional Pydantic models for LLM interactions
- ✅ Comprehensive Azure client wrapper (~720 lines)
- ✅ Retry logic with exponential backoff
- ✅ Token tracking with GPT-5 reasoning breakdown
- ✅ 20 new tests (75 total tests, 100% passing)
- ✅ Production-ready with circuit breaker and error handling

⏳ **Phase 1 - Next Steps**
- Template expansion (3 → 20+)
- LLM-assisted entity extraction
- Router pattern (template fast path + AI fallback)
- Target: 50%+ simple question coverage (145+/295)

---

## Architecture

### Design Philosophy

**Simple > Complex**

This project uses a straightforward 4-layer architecture:

```
┌─────────────────────────────────┐
│  1. ENTITY EXTRACTION           │
│  Extract: company, metric,      │
│  period from user question      │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│  2. SQL GENERATION              │
│  Convert entities to SQL        │
│  (template-based, LLM fallback) │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│  3. QUERY EXECUTION             │
│  Execute SQL on parquet files   │
│  via DuckDB                     │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│  4. RESPONSE FORMATTING         │
│  Convert results to natural     │
│  language with context          │
└─────────────────────────────────┘
```

### Key Principles

1. **Template First**: Start with SQL templates for common patterns, add LLM only when needed
2. **Test Driven**: 410 evaluation questions guide development
3. **Incremental**: Get 10 questions working, then 50, then 200+
4. **Synchronous**: Keep it simple - no async complexity unless required
5. **Maintainable**: Clear code over clever code

---

## Project Structure

```
quant-magic-SandP-500/
├── data/
│   └── parquet/              # Financial + intelligence assets (253MB)
│       ├── num.parquet       # 15.5M financial metrics
│       ├── sub.parquet       # 22.8K submissions
│       ├── tag.parquet       # 481K XBRL tags
│       ├── companies_with_sectors.parquet  # 589 companies
│       ├── query_intelligence.parquet      # NL ⇄ SQL templates
│       ├── financial_concepts.parquet      # Domain concept catalog
│       └── financial_ratios_definitions.parquet  # Ratio formulas & metadata
│
├── evaluation/
│   └── questions/            # Test questions (410 total)
│       ├── simple_lineitem.json     # 295 questions
│       ├── medium_analysis.json     # 50 questions
│       ├── complex_strategic.json   # 25 questions
│       └── time_series_analysis.json # 40 questions
│
├── src/                      # Application source code (Phase 0 + Phase 1 partial)
│   ├── __init__.py
│   ├── config.py             # ✅ Configuration with Azure OpenAI
│   ├── query_engine.py       # ✅ DuckDB query execution (6 tests passing)
│   ├── telemetry.py          # ✅ Logging, timing, request tracking
│   ├── models.py             # ✅ 14 Pydantic v2 models (7 base + 7 LLM)
│   ├── intelligence_loader.py # ✅ Loads 3 templates from parquet
│   ├── entity_extractor.py   # ✅ Deterministic entity extraction
│   ├── sql_generator.py      # ✅ Template-based SQL generation
│   ├── response_formatter.py # ✅ Natural language formatting
│   ├── cli.py                # ✅ Interactive REPL + single-shot modes
│   └── azure_client.py       # ✅ Azure OpenAI client wrapper (NEW)
│
├── tests/                    # Test suite (75 tests, 100% passing)
│   ├── test_query_engine.py        # ✅ Data layer (6 tests)
│   ├── test_telemetry.py           # ✅ Telemetry (6 tests)
│   ├── test_models.py              # ✅ Pydantic models (8 tests)
│   ├── test_intelligence_loader.py # ✅ Template matching (4 tests)
│   ├── test_entity_extractor.py    # ✅ Entity extraction (6 tests)
│   ├── test_sql_generator.py       # ✅ SQL generation (5 tests)
│   ├── test_response_formatter.py  # ✅ Response formatting (4 tests)
│   ├── test_cli_integration.py     # ✅ End-to-end (6 tests)
│   ├── test_eval_poc.py            # ✅ PoC evaluation (11 tests)
│   └── test_azure_client.py        # ✅ Azure OpenAI client (20 tests - NEW)
│
├── .venv/                    # Virtual environment (Python 3.11)
├── requirements.txt          # Minimal dependencies
├── README.md                 # This file
└── PLAN.md                   # Development plan and roadmap
```

---

## Technology Stack

### Core Dependencies
- **Python 3.11+**: Modern Python with type hints
- **pandas**: Data manipulation and analysis
- **DuckDB**: High-performance analytical database
- **pyarrow**: Columnar data format
- **pydantic**: Data validation

### Optional Dependencies
- **openai**: For Azure OpenAI "responses" API integration ✅ (Installed: 2.2.0)
- **python-dotenv**: Environment variable management ✅
- **pytest**: For testing ✅
- **black/ruff**: Code formatting ✅

**Total**: ~10 core packages (minimal and focused)

---

## Data Layer

### Data Pipeline & Reproducibility

**Full reproducibility is built in.** All data transformations are documented and scripted.

#### Raw Data (565MB)
The `data/raw/` directory contains the original SEC EDGAR TSV files:
- `num.txt` - 3.4M rows of financial facts (469MB)
- `sub.txt` - 6.7K rows of submission metadata (2MB)
- `tag.txt` - 103K rows of XBRL tag definitions (22MB)
- `pre.txt` - 805K rows of presentation linkbase (99MB)
- `comprehensive_companies.csv` - S&P 500 company list with sectors

**Source**: SEC EDGAR Financial Statement Data Sets  
**URL**: https://www.sec.gov/dera/data/financial-statement-data-sets  
**Downloaded**: Multi-quarter dataset (2014-2026)

#### Processing Pipeline

**Step 1: Convert TSV to Parquet**
```bash
# Convert raw TSV files to optimized Parquet format
python -m pipeline.convert_to_parquet

# This creates:
# - data/parquet/num.parquet (199MB, 15.5M rows)
# - data/parquet/sub.parquet (902KB, 22.8K rows)
# - data/parquet/tag.parquet (23MB, 481K rows)
# - data/parquet/pre.parquet (30MB, 805K rows)
```

**Step 2: Add Company Sectors**
```bash
# Merge S&P 500 company list with GICS sectors
python -m pipeline.add_company_sectors

# This creates:
# - data/parquet/companies_with_sectors.parquet (589 companies)
```

#### Quarterly Data Updates

When new quarterly data is released by SEC:

```bash
# 1. Download new quarter from SEC
wget https://www.sec.gov/files/dera/data/financial-statement-data-sets/2025q3.zip

# 2. Extract to quarterly directory
unzip 2025q3.zip -d data/raw/quarterly/2025q3/

# 3. Merge with existing data
python -m pipeline.update_quarterly_data --quarter 2025q3

# This automatically:
# - Reads new TSV files
# - Merges with existing parquet files
# - Removes duplicates
# - Creates backups (.parquet.backup)
# - Updates all tables atomically
```

### Available Data (Post-Processing)

**Companies**: 589 S&P 500 companies with:
- CIK (SEC identifier)
- Company name
- GICS sector classification
- Country of incorporation

**Financial Facts**: 15.5M+ records including:
- Income statement items (revenue, net income, etc.)
- Balance sheet items (assets, liabilities, equity)
- Cash flow items
- Financial ratios and derived metrics
- Quarterly and annual data (2014-2026)

**XBRL Tags**: 481K tag definitions for:
- Standard financial terms
- Company-specific metrics
- Industry-specific measures

### Semantic Intelligence Layer

Beyond raw data, the project ships a curated business intelligence layer stored as parquet files. These assets ground the NL → SQL workflow and will power both the CLI and future UI experiences:

- `query_intelligence.parquet`: Natural-language patterns, intent metadata, reusable SQL templates, and suggested follow-ups.
- `financial_concepts.parquet`: Canonical catalog of metrics with XBRL tags, synonyms, and business logic notes.
- `financial_ratios_definitions.parquet`: Ratio formulas (e.g., ROE, debt/equity) with interpretation guidance and required data elements.
- `sector_intelligence.parquet`: Sector-specific playbooks covering key metrics, risk factors, and benchmarking anchors.
- `analytical_views_metadata.parquet`: Predefined analytical views (materialized or virtual) including dependencies and refresh guidance.
- `statement_relationships.parquet`: Cross-statement linkage graph to assist with balanced calculations and drill-throughs.
- `time_series_intelligence.parquet`: Patterns for growth rates, trend detection, and seasonality analysis.

During early sprints we will load these files via an `intelligence_loader` module, exposing Pydantic models so outputs remain type-safe and easily serializable for the upcoming React UI.

### Query Engine (Working ✅)

The `QueryEngine` class provides a simple interface to the data:

```python
from src.query_engine import QueryEngine

qe = QueryEngine()

# Count companies
count = qe.count_companies()  # 589

# List sectors
sectors = qe.list_sectors()   # ['Technology', 'Healthcare', ...]

# Find company
apple = qe.get_company_info('Apple')  # {'cik': '0001418121', ...}

# Custom SQL
result = qe.execute("SELECT COUNT(*) FROM companies WHERE gics_sector = 'Technology'")

qe.close()
```

**Test Status**: 6/6 data layer tests passing ✅ (part of 55 total tests)

---

## Data Pipeline Maintenance

### Processing from Scratch

If you need to regenerate all parquet files:

```bash
# Delete existing parquet files
rm data/parquet/*.parquet

# Step 1: Convert raw TSV to Parquet
python -m pipeline.convert_to_parquet

# Step 2: Add company sectors
python -m pipeline.add_company_sectors

# Verify
python -m pytest tests/test_query_engine.py -v
```

**Processing Time**: ~2-3 minutes on MacBook Pro  
**Memory Usage**: Peak 2-3GB

### Quarterly Data Updates

SEC releases new data quarterly (Feb, May, Aug, Nov):

```bash
# 1. Download new quarter
wget https://www.sec.gov/files/dera/data/financial-statement-data-sets/2025q3.zip

# 2. Extract to staging directory
unzip 2025q3.zip -d data/raw/quarterly/2025q3/

# 3. Merge with existing data
python -m pipeline.update_quarterly_data --quarter 2025q3

# 4. Verify
python -c "from src.query_engine import QueryEngine; qe = QueryEngine(); print(f'{qe.count_companies()} companies'); qe.close()"
```

**Update Process**:
- Reads new TSV files from quarterly directory
- Merges with existing parquet files
- Removes duplicates automatically
- Creates backups (.parquet.backup)
- Updates all tables atomically

**Duplicate Handling**:
- `num`: Unique by (adsh, tag, version, ddate, qtrs)
- `sub`: Unique by (adsh)
- `tag`: Unique by (tag, version)
- `pre`: Unique by (adsh, report, line)

### Troubleshooting

**Issue**: Conversion fails with memory error  
**Solution**: Reduce chunk size in `convert_to_parquet.py`:
```python
converter.convert_file('num', chunk_size=50000)  # Default is 100000
```

**Issue**: Query returns no results for known company  
**Check**:
- Company name spelling (use `LIKE '%APPLE%'`)
- Company is in S&P 500 list
- Data exists for requested period
- CIK is 10-digit zero-padded

**Issue**: Quarterly update creates duplicates  
**Solution**: Script automatically deduplicates. If issues persist:
```bash
# Restore from backup
cp data/parquet/num.parquet.backup data/parquet/num.parquet
# Report issue for investigation
```

### Data Sources

**SEC EDGAR**:
- URL: https://www.sec.gov/dera/data/financial-statement-data-sets
- Format: Quarterly ZIP files with TSV
- License: Public domain (U.S. government data)
- Coverage: 2009-present (updated quarterly)

**S&P 500 Company List**:
- Source: Multiple (S&P, Wikipedia, manual curation)
- Format: CSV with CIK, name, GICS sector
- Maintenance: Updated as constituents change

---

## Development Setup

### Prerequisites
- Python 3.11 or higher
- 4GB+ RAM recommended
- ~500MB disk space for data

### Installation

```bash
# 1. Navigate to project
cd /Users/Srinidhi/my_projects/quant-magic-SandP-500

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Verify installation
python -m pytest tests/ -v
# Expected: 75 passed in ~1.5s

# 4. Test data access
python -c "
from src.query_engine import QueryEngine
qe = QueryEngine()
print(f'✅ {qe.count_companies()} companies ready')
qe.close()
"
```

### Development Workflow

```bash
# Daily workflow
source .venv/bin/activate     # Activate environment
python -m pytest tests/ -v    # Run tests

# Add new feature
# 1. Write test in tests/
# 2. Write implementation in src/
# 3. Run tests until passing
# 4. Commit

# Code formatting
python -m black src/ tests/   # Format code

# Check line count
find src tests -name '*.py' | xargs wc -l
```

---

## Testing Strategy

### Test Pyramid

1. **Unit Tests**: Test individual components
   - Entity extraction
   - SQL generation
   - Response formatting
   - Target: Fast, isolated, deterministic

2. **Integration Tests**: Test component interaction
   - Entity → SQL → Execution → Response
   - Target: End-to-end flows work

3. **Evaluation Tests**: Test against real questions
   - 410 questions with golden answers
   - Target: 90% pass rate (369/410 questions)

### Evaluation Framework

The `evaluation/questions/` directory contains 410 test questions organized by complexity:

**Simple (295 questions)**: Basic lookups
- "How many companies in Technology sector?"
- "What is Apple's CIK?"
- "List companies in Energy sector"

**Medium (50 questions)**: Multi-step analysis
- "Calculate Apple's ROE and compare to sector average"
- "Top 5 companies by debt-to-equity ratio in Healthcare"
- "Microsoft's gross margin trend over past 4 quarters"

**Complex (25 questions)**: Strategic analysis
- "Analyze capital allocation efficiency using ROIC vs WACC"
- "Compare competitive moats of tech giants"
- "Develop sector rotation strategy with backtesting"

**Time Series (40 questions)**: Temporal analysis
- "Revenue growth trends by quarter"
- "Working capital efficiency over time"
- "Multi-year profitability patterns"

---

## Performance Targets

### Response Times
- Simple queries: <1 second
- Medium queries: <5 seconds
- Complex queries: <15 seconds

### Accuracy Targets
- Simple questions: 90% pass rate (266/295)
- Medium questions: 85% pass rate (43/50)
- Complex questions: 75% pass rate (19/25)
- Time series: 80% pass rate (32/40)
- **Overall: 90% pass rate (369/410)**

### Code Quality
- Maintainability: <1000 total lines of code
- Test coverage: >80% for core modules
- Startup time: <1 second
- Memory usage: <2GB for typical queries

---

## Usage Examples

### Interactive Mode (Recommended) ✨

Run the CLI in interactive mode to ask multiple questions in a session:

```bash
# Start interactive mode
python -m src.cli --interactive

# Or simply (no question defaults to interactive)
python -m src.cli
```

**Interactive session example:**
```
======================================================================
🔮 Quant Magic - S&P 500 Financial Analysis
======================================================================

Ask questions about S&P 500 companies in natural language.

Examples:
  - How many companies are in the Technology sector?
  - What is Apple's CIK?
  - What sector is Microsoft in?

Commands:
  - 'exit' or 'quit': Exit the application
  - 'help': Show this help message
  - 'debug on/off': Toggle debug mode
======================================================================

💬 Ask: How many companies are in the Technology sector?

💡 Answer: There are 143 companies in the Information Technology sector.

💬 Ask: What is Apple's CIK?

💡 Answer: APPLE INC's CIK is 0000320193.

💬 Ask: What sector is Microsoft in?

💡 Answer: MICROSOFT CORP is in the Information Technology sector.

💬 Ask: exit

👋 Goodbye! Thanks for using Quant Magic.

📊 Session summary: Processed 3 questions
```

### Single-Shot Mode

For one-off questions or scripting:

```bash
# Basic question
python -m src.cli "How many companies are in Healthcare?"

# With debug information
python -m src.cli "What is Tesla's CIK?" --debug

# JSON output (for programmatic use)
python -m src.cli "What sector is Amazon in?" --json --pretty
```

### Phase 0 Supported Queries ✅

Currently supported (3 template patterns):

```bash
# 1. Count companies by sector
python -m src.cli "How many companies in Technology?"
python -m src.cli "How many companies are in the Healthcare sector?"
python -m src.cli "Count companies in Financials"

# 2. Look up company CIK
python -m src.cli "What is Apple's CIK?"
python -m src.cli "Get Microsoft's CIK"
python -m src.cli "Show me Tesla's CIK"

# 3. Find company sector
python -m src.cli "What sector is Amazon in?"
python -m src.cli "Which sector does JPMorgan belong to?"
python -m src.cli "What is Alphabet's sector?"
```

### Advanced Queries (Coming in Phase 1-3)

Future capabilities:

```bash
# Financial metrics (Phase 1)
python -m src.cli "What was Microsoft's revenue in Q3 2024?"
python -m src.cli "Show Apple's total assets for FY2023"

# Ratios and comparisons (Phase 2)
python -m src.cli "Calculate Apple's ROE for latest quarter"
python -m src.cli "Compare Microsoft and Apple revenue"

# Time series (Phase 3)
python -m src.cli "Show revenue trend for Tesla over 5 years"
python -m src.cli "Quarterly margin analysis for tech sector"

# Complex analysis (Phase 3)
python -m src.cli "Sector rotation recommendation based on ROE"
python -m src.cli "Working capital efficiency by sector"
```

### CLI Contracts (UI-Ready)

All CLI responses use structured Pydantic models that are ready for API/UI integration:

**Request payload** (JSON):
```json
{
  "question": "What is Apple's CIK?",
  "user_context": {"role": "analyst"},
  "debug_mode": false
}
```

**Response payload** (JSON):
```json
{
  "answer": "APPLE INC's CIK is 0000320193.",
  "confidence": 0.95,
  "sources": ["companies_with_sectors.parquet"],
  "metadata": {
    "request_id": "a1b2c3d4",
    "total_time_seconds": 0.0234,
    "row_count": 1,
    "timestamp": "2025-11-03T10:30:45.123456"
  },
  "success": true
}
```

All models are defined in `src/models.py` with full Pydantic v2 validation.

---

## Contributing Guidelines

### Code Style
- Use Black for formatting (line length: 88)
- Type hints for all function signatures
- Docstrings for all public functions
- Keep functions under 50 lines
- Keep files under 500 lines

### Testing Requirements
- Write tests before implementation
- Each new feature needs tests
- Maintain >80% test coverage
- All tests must pass before commit

### Commit Messages
```
Format: <type>: <description>

Types:
- feat: New feature
- fix: Bug fix
- test: Add or update tests
- docs: Documentation changes
- refactor: Code restructuring

Examples:
- feat: Add entity extraction for company names
- test: Add tests for SQL template matching
- fix: Handle empty query results gracefully
```

---

## Project Goals

### ✅ Phase 0: PoC & Foundations (COMPLETE)
- ✅ Data layer working and tested
- ✅ Evaluation framework ready
- ✅ Project structure established
- ✅ Core components operational
- ✅ Entity extraction (deterministic)
- ✅ SQL generation (3 templates)
- ✅ Response formatting (natural language)
- ✅ Interactive CLI (REPL mode)
- ✅ 55 tests passing (100%)
- ✅ 10/10 PoC questions correct

### Phase 1: Template Expansion & LLM Integration (In Progress)
- ✅ Azure OpenAI integration (COMPLETE)
  - Production-ready client wrapper
  - Responses API integration
  - Token tracking with GPT-5 reasoning breakdown
  - Retry logic and circuit breaker
  - 20 comprehensive tests
- ⏳ Template expansion (3 → 20+)
- ⏳ LLM-assisted entity extraction
- ⏳ Router pattern (fast path + AI fallback)
- Target: 50%+ simple question coverage (145+/295)

### Phase 2-3: Coverage Expansion (Future)
- Advanced query patterns
- Medium question support (85%+)
- Complex question support (75%+)
- Time series analysis (80%+)
- Target: 90% overall pass rate (369+/410)

### Phase 4+: Enhancement & Production (Future)
- Performance optimization
- Web interface (optional)
- Multi-tenant SaaS features
- Azure Marketplace deployment

---

## FAQ

### Q: What Python version is required?
**A**: Python 3.11+ is required for optimal compatibility with dependencies.

### Q: How big is the dataset?
**A**: 253MB of parquet files containing 15.5M+ financial facts for 589 companies.

### Q: What's the difference between simple and complex questions?
**A**: Simple questions need 1 SQL query (lookups), medium need multiple steps (calculations), complex need multi-table joins and business logic.

### Q: How are evaluation questions validated?
**A**: Each question has a golden answer. The system's output is compared against the expected answer with configurable tolerance for numeric values.

### Q: Can I add my own SQL templates?
**A**: Yes! See `src/sql_generator.py` for the template structure.

### Q: Do I need an LLM API key?
**A**: No, not for initial development. Templates handle most queries. LLM is optional for complex queries.

---

## License

MIT License - Free for research, education, and commercial use.

## Data Attribution

- **Primary Source**: SEC EDGAR Database (public domain)
- **Processing**: Custom ETL pipeline
- **Format**: Parquet files optimized for analytics

---

## Support

For questions, issues, or contributions:
1. Check `PLAN.md` for development roadmap
2. Review existing tests in `tests/`
3. See code examples in `src/query_engine.py`

---

**Status**: ✅ Phase 0 Complete | 🚀 Phase 1 Azure OpenAI Integration Complete  
**Current**: 75/75 tests passing (55 original + 20 new), production-ready Azure client  
**Features**: Responses API, retry logic, token tracking, circuit breaker, GPT-5 reasoning  
**Next Phase**: Template expansion (3 → 20+) + LLM-assisted extraction - see PLAN.md  
**Ultimate Goal**: 90% evaluation pass rate (369+/410 questions) across all complexity levels
