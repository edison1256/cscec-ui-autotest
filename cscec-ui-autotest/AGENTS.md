# AGENTS.md — CSCEC UI Automation Project Instructions

## Mandatory Production Release Walkthrough Suite
- **Mandatory Suite**: All 68 PC + Mobile read-only smoke cases defined in `docs/prod-release-mandatory-walkthrough-suite.md` are mandatory on every release.
- **Production Execution**: `python run_tests.py --env prod` automatically executes the full 68-case mandatory suite with 0 write risk.

## Automatic Git & DevOps Maintenance

> **作用域约束（关键安全规则）**：本工程是 `D:/Automation` 这个更大 git 仓库的子目录。仓库根在父目录，其中含大量无关项目（JaCoCo / Jmeter / Playwright / Claude / AutoInspection 等）。**所有 git 操作必须显式限定到本工程子树，绝不可在父目录作用域执行 `git add` / `git commit` / `git push`，否则会误提交/误推送无关代码。**
>
> 定义常量：`PROJECT_DIR = D:/Automation/cscec-ui-autotest`（即本工程根目录）。

1. **Auto-Evaluate Updates**: Automatically determine if file changes in `pages/`, `tests/`, `core/`, `config/`, `test_assets/`, `docs/`, `tools/`, `utils/`, or the project-root files (`AGENTS.md`, `README.md`, `.gitignore`, `requirements.txt`, `run_tests.py`, `pytest.ini`) constitute a key/meaningful update.
2. **Auto-Verify**: Before committing, automatically run `python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml` and `python run_tests.py --env uat --dry-run`.
3. **Auto-Commit & Push**（全部使用 `git -C "$PROJECT_DIR"` 限定作用域）:
   - **Pre-commit guard（提交前必做）**: 运行 `git -C "$PROJECT_DIR" diff --cached --name-only`，**断言所有暂存路径均以 `cscec-ui-autotest/` 开头**。若有任何路径逸出本工程子树，立即中止提交并告警，不得继续。
   - **Stage only monitored paths（绝不使用 `.` 或 `-A`）**: `git -C "$PROJECT_DIR" add pages tests core config test_assets docs tools utils AGENTS.md README.md .gitignore requirements.txt run_tests.py pytest.ini`。
   - **Commit**: Format Conventional Commits (e.g. `feat`, `fix`, `refactor`) — `git -C "$PROJECT_DIR" commit -m "<type>: <summary>"`。
   - **Push**: `git -C "$PROJECT_DIR" push github master`。
   - 在任何 cwd 下执行上述命令，都不会触及 `D:/Automation` 下的无关项目。
4. **Safety Protection**: 以下路径已被 `.gitignore` 覆盖，禁止提交：`.env`、`auth_states/`（含 `auth_states/*.json`）、`logs/`、`screenshots/`、`reports/`。提交前护栏（第 3 步）是第二道防线：即便 `.gitignore` 遗漏，暂存路径检查也会拦截越界文件。
5. **Status Doc Refresh**: After any change to the monitored dirs, run `python tools/generate_progress_doc.py` to regenerate `docs/PROJECT_STATUS.md` from the asset registry + dry-run (replaces manual maintenance to prevent drift).
