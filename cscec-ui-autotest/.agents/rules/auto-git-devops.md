# Auto Git & DevOps Maintenance Protocol

This project enforces automatic evaluation, verification, and Git commit/push for key codebase updates.

## 1. Automatic Evaluation Rules (Determining Key Updates)

The agent MUST evaluate all file modifications at the end of a feature, fix, or maintenance task:

### 🟢 Key Updates (Must Auto-Commit & Push)
- **New/Modified Page Objects**: Any changes to `pages/**/*.py`
- **New/Modified Test Cases**: Any changes to `tests/**/*.py`
- **Asset Registry Updates**: Changes to `test_assets/registry/ui_case_assets.yaml` or `test_assets/incoming/*.yaml`
- **Core Framework & Helpers**: Changes to `core/*.py`, `config/*.py`, `utils/*.py`, `run_tests.py`, `pytest.ini`
- **CI & Documentation**: Changes to `.github/workflows/*.yml` or `docs/*.md`

### 🔴 Excluded / Non-Committable Artifacts (Never Commit)
- Runtime logs (`logs/`), screenshots (`screenshots/`), HTML reports (`reports/`)
- Pytest cache (`.pytest_cache/`), Python bytecode (`__pycache__/`)
- Temporary authentication states containing secrets (`auth_states/*.json`)
- Environment files containing passwords (`.env`)

---

## 2. Pre-Commit Automated Verification Protocol

Before performing any commit, the agent MUST run:

```powershell
python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml
python run_tests.py --env uat --dry-run
```

- If both verification commands exit with code 0, proceed to commit.
- If verification fails, fix the errors first or notify the user without committing broken code.

---

## 3. Automated Git Commit & Push Execution

When a key update passes verification, the agent MUST automatically execute:

```powershell
git add <relevant_modified_files>
git commit -m "<type>(<scope>): <concise_description>"
git push github master
```

**Commit Types**:
- `feat`: New test cases, Page Objects, or features
- `fix`: Locator repairs, assertion fixes, or bug fixes
- `refactor`: Page Object / helper code structure improvements
- `ci`: Workflow updates
- `docs`: Documentation updates

After pushing, summarize the commit hash and GitHub push status to the user.
