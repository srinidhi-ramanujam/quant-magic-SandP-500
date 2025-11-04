# Agent Operating Guide

## Mission Snapshot
- Build S&P 500 query intelligence features in focused, reviewable increments.
- Honor roadmap in `PLAN.md` and design notes before altering architecture.

## Repo Landmarks
- `src/`: core pipeline modules (`azure_client.py`, `entity_extractor.py`, `sql_generator.py`, `cli.py`, supporting models/prompts).
- `tests/`: mirrors `src/` structure; integration markers highlight external dependencies.
- `data/parquet/`: DuckDB inputs and intelligence catalogs; treat as read-only unless directed.
- `pipeline/` & `scripts/`: automation, ETL, and maintenance helpers.
- `evaluation/questions/`: harness prompts for coverage tracking.

## Working Principles
- No persistent scratch artifacts: remove exploratory scripts, notebooks, or extra Markdown before handing off.
- Stay within approved dependencies (`requirements.txt`); never install new tools without explicit go-ahead.
- Seek clarification early; do not diverge from existing plans unauthorised.
- Deliver meaningful increments with clear exit criteria (e.g., `pytest` target, CLI scenario, evaluation batch).
- Maintain secrets outside git; rely on env vars for Azure configuration.

## Standard Workflow
1. Confirm scope and acceptance checks with the requester.
2. Activate the venv and sync deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Drive development with tests (`python -m pytest tests/ -v` or narrowed focus).
4. Format touched code: `python -m black src/ tests/`.
5. Document verification steps in PR notes or handoff summary.

## Exit Checklist
- ✅ Requirement satisfied and demonstrated via agreed command or test.
- ✅ No stray files; git status only shows intentional changes.
- ✅ Commit message follows Conventional style (`feat:`, `fix:`, `chore:`, etc.).
- ✅ README or docs updated when behavior or process changes.

## Quick Verification Commands
- Interactive CLI: `python -m src.cli --interactive`.
- Debug single query: `python -m src.cli "How many companies are in Technology?" --debug`.
- Fast non-integration suite: `python -m pytest -m "not integration"`.

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
