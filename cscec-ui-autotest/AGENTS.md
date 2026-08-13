# AGENTS.md — CSCEC UI Automation Project Instructions

## Mandatory Production Release Walkthrough Suite
- **Mandatory Suite**: All 49 PC + Mobile read-only smoke cases defined in `docs/prod-release-mandatory-walkthrough-suite.md` are mandatory on every release.
- **Production Execution**: `python run_tests.py --env prod` automatically executes the full 49-case mandatory suite with 0 write risk.

## Automatic Git & DevOps Maintenance

1. **Auto-Evaluate Updates**: Automatically determine if file changes in `pages/`, `tests/`, `core/`, `config/`, `test_assets/`, or `docs/` constitute a key/meaningful update.
2. **Auto-Verify**: Before committing, automatically run `python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml` and `python run_tests.py --env uat --dry-run`.
3. **Auto-Commit & Push**: Format Conventional Commits (e.g. `feat`, `fix`, `refactor`), run `git add`, `git commit`, and `git push github master` without requiring manual prompts.
4. **Safety Protection**: Never commit `.env`, `auth_states/`, `logs/`, `screenshots/`, or `reports/`.
