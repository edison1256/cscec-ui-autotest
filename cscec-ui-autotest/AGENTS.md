# AGENTS.md — CSCEC UI Automation Project Instructions

## Automatic Git & DevOps Maintenance

1. **Auto-Evaluate Updates**: Automatically determine if file changes in `pages/`, `tests/`, `core/`, `config/`, `test_assets/`, or `docs/` constitute a key/meaningful update.
2. **Auto-Verify**: Before committing, automatically run `python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml` and `python run_tests.py --env uat --dry-run`.
3. **Auto-Commit & Push**: Format Conventional Commits (e.g. `feat`, `fix`, `refactor`), run `git add`, `git commit`, and `git push github master` without requiring manual prompts.
4. **Safety Protection**: Never commit `.env`, `auth_states/`, `logs/`, `screenshots/`, or `reports/`.
