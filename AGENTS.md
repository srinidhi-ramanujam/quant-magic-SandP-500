# Agent Operating Guide

## Mission Snapshot
- Build S&P 500 query intelligence features (NL → SQL → answer) in focused, reviewable increments.
- Honor roadmap in `PLAN.md` and design notes before altering architecture or prompts.

## Layer Map (current state)
- **Data**: DuckDB-backed parquet catalogs (`data/parquet/`) are mature (15.5M+ facts, 589 companies). Treat as read-only unless told otherwise.
- **Pipeline / Semantic**: LLM-first entity extraction + hybrid template routing + custom SQL generation + two-pass SQL validation are in place. Time-series templates and coverage are mid-flight (`sql_templates/`, `PLAN.md` Phase 2/TS roadmap).
- **Service Layer**: FastAPI (`src/api/app.py`, `src/services/`) wraps the CLI pipeline; health + `/query` endpoints mirror CLI fallbacks.
- **UI (WIP)**: React + TypeScript + Tailwind chat interface in `frontend/` hitting `/api/query`; no persisted sessions yet, relies on backend health/snippet checks.

## Repo Landmarks
- `src/`: core pipeline (`azure_client.py`, `entity_extractor.py`, `sql_generator.py`, `sql_validator.py`, `cli.py`, `prompts.py`, supporting models/telemetry).
- `src/api/`: FastAPI entrypoint (`app.py`) and service wiring (`services/`).
- `frontend/`: React + Vite chat UI (ASCENDION-branded, talks to FastAPI).
- `tests/`: mirrors `src/`; integration markers highlight Azure dependencies.
- `data/parquet/`: DuckDB inputs and intelligence catalogs; do not edit without approval.
- `pipeline/` & `scripts/`: automation, ETL, and maintenance helpers.
- `evaluation/questions/`: harness prompts for coverage tracking.

## Working Principles
- No persistent scratch artifacts: remove exploratory scripts, notebooks, or extra Markdown before handing off.
- Stay within approved dependencies (`requirements.txt`); never install new tools without explicit go-ahead.
- Seek clarification early; do not diverge from existing plans unauthorised.
- Deliver meaningful increments with clear exit criteria (e.g., `pytest` target, CLI scenario, evaluation batch).
- Maintain secrets outside git; rely on env vars for Azure configuration.

## Standard Workflow
1. Check ready work and claim it: `bd ready --json` then `bd update <id> --status in_progress`.
2. Confirm scope and acceptance checks with the requester.
3. Activate the venv and sync deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
4. Drive development with tests (`python -m pytest tests/ -v` or narrowed focus).
5. Format touched code: `python -m black src/ tests/`.
6. For UI work, install deps in `frontend/` and use Vite scripts; keep API + UI ports aligned with scripts.
7. Document verification steps in PR notes or handoff summary.

## Exit Checklist
- ✅ Requirement satisfied and demonstrated via agreed command or test.
- ✅ No stray files; git status only shows intentional changes.
- ✅ Commit message follows Conventional style (`feat:`, `fix:`, `chore:`, etc.).
- ✅ README or docs updated when behavior or process changes.

## Quick Verification Commands
- Interactive CLI: `python -m src.cli --interactive`.
- Debug single query: `python -m src.cli "How many companies are in Technology?" --debug`.
- Fast non-integration suite: `python -m pytest -m "not integration"`.
- API health: `uvicorn src.api.app:app --reload --port 8000` then `curl http://localhost:8000/health`.
- UI dev: from `frontend/`, `npm install` (once) then `npm run dev -- --host --port 5173` (or `./scripts/run_local_ui.sh` to run API + UI together).

Keep this guide and the expanded contributor notes in `README.md` handy during each iteration.

---

## Git Repository Details

**Repository URL (SSH):**
```
git@github.com-work:srinidhi-ramanujam/quant-magic-SandP-500.git
```

**Repository URL (HTTPS):**
```
https://github.com/srinidhi-ramanujam/quant-magic-SandP-500.git
```

**Main Branch:** `master`

## PR Review Workflow for Agents

When asked to review a Pull Request:

1. **Check out the PR branch locally:**
   ```bash
   git fetch origin
   git checkout branch-name
   ```

2. **Review the changes:**
   ```bash
   # See all changes compared to master
   git diff master...HEAD
   
   # Or review specific files
   git diff master...HEAD -- path/to/file
   ```

3. **Run verification checks:**
   ```bash
   # Activate venv if not already active
   source .venv/bin/activate
   
   # Run tests
   python -m pytest tests/ -v
   
   # Check formatting
   python -m black --check src/ tests/
   
   # Run non-integration tests only
   python -m pytest -m "not integration"
   ```

4. **Review checklist:**
   - ✅ Code follows existing patterns and architecture
   - ✅ Changes align with `PLAN.md` roadmap
   - ✅ Tests added/updated for new functionality
   - ✅ Pydantic models used for API response validation
   - ✅ Azure OpenAI 'responses' API used (not chat completions)
   - ✅ No stray files (scratch scripts, extra .md files except README.md/PLAN.md)
   - ✅ Dependencies only use approved `requirements.txt` packages
   - ✅ Commit messages follow Conventional Commits style
   - ✅ Secrets not hardcoded (use environment variables)
   - ✅ README.md or PLAN.md updated if behavior changes

5. **Provide structured feedback:**
   - List files reviewed
   - Highlight what works well
   - Flag any issues with severity (blocking, suggestion, question)
   - Verify alignment with project rules and memories
   - Suggest improvements with code examples if needed

## Making Changes as an Agent

When making changes to the repository:

1. **Always work in context of current git state:**
   ```bash
   git status
   git diff
   ```

2. **Before committing:**
   - Run `python -m black src/ tests/`
   - Run `python -m pytest tests/ -v`
   - Verify no unintended files in `git status`

3. **Commit with Conventional Commits style:**
   - `feat:` - new feature
   - `fix:` - bug fix
   - `chore:` - maintenance, deps, refactor
   - `docs:` - documentation only
   - `test:` - test additions/modifications

4. **Never:**
   - Run `git push --force` to master
   - Skip hooks with `--no-verify`
   - Commit without explicit user request
   - Create extra markdown files (only README.md and PLAN.md allowed)
   - Install packages not in `requirements.txt`

## Quick Git Commands Reference

```bash
# See current branch and status
git branch --show-current
git status

# View commit history
git log --oneline -10

# Compare branches
git diff master...feature-branch

# List all branches
git branch -a

# Return to master
git checkout master
git pull origin master
```

# Task management with Beads
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Auto-syncs to JSONL for version control
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**
```bash
bd ready --json
```

**Create new issues:**
```bash
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json
bd create "Subtask" --parent <epic-id> --json  # Hierarchical subtask (gets ID like epic-id.1)
```

**Claim and update:**
```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**
```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`
6. **Commit together**: Always commit the `.beads/issues.jsonl` file together with the code changes so issue state stays in sync with code state

### Auto-Sync

bd automatically syncs with git:
- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!


### MCP Server (Recommended)

If using Claude or MCP-compatible clients, install the beads MCP server:

```bash
pip install beads-mcp
```

Add to MCP config (e.g., `~/.config/claude/config.json`):
```json
{
  "beads": {
    "command": "beads-mcp",
    "args": []
  }
}
```

Then use `mcp__beads__*` functions instead of CLI commands.

### Managing AI-Generated Planning Documents

AI assistants often create planning and design documents during development:
- PLAN.md, IMPLEMENTATION.md, ARCHITECTURE.md
- DESIGN.md, CODEBASE_SUMMARY.md, INTEGRATION_PLAN.md
- TESTING_GUIDE.md, TECHNICAL_DESIGN.md, and similar files

**Best Practice: Use a dedicated directory for these ephemeral files**

**Recommended approach:**
- Create a `history/` directory in the project root
- Store ALL AI-generated planning/design docs in `history/`
- Keep the repository root clean and focused on permanent project files
- Only access `history/` when explicitly asked to review past planning

**Example .gitignore entry (optional):**
```
# AI planning documents (ephemeral)
history/
```

**Benefits:**
- ✅ Clean repository root
- ✅ Clear separation between ephemeral and permanent documentation
- ✅ Easy to exclude from version control if desired
- ✅ Preserves planning history for archeological research
- ✅ Reduces noise when browsing the project

### CLI Help

Run `bd <command> --help` to see all available flags for any command.
For example: `bd create --help` shows `--parent`, `--deps`, `--assignee`, etc.

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Store AI planning docs in `history/` directory
- ✅ Run `bd <cmd> --help` to discover available flags
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems
- ❌ Do NOT clutter repo root with planning documents

For more details, see README.md and QUICKSTART.md.
