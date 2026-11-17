# AGENTS.md — CSCEC UI Automation Project Instructions

## Backdoor Login Boundary

`pages/portal/backdoor_login_page.py` 直连 `/udpweb/portal/index.html#/login`，
绕过 4A/SSO。使用边界（2026-11-12 明确）：

1. **允许** — 环境装配：准备账号、验证租户/权限、只读盘点。
2. **允许** — **无法走 4A 的测试专用账号**执行只读业务用例。
   典型场景：个人视角账号只有后门口令，在 4A 侧不存在或口令不同
   （如 PRE 的 `METERING_USERNAME` 槽位账号）。
   此时后门只承担「登录」职责：**所有断言仍必须基于真实 UI 与真实业务数据**，
   不得因为走了后门就放宽断言、跳过校验或构造假数据。
3. **禁止** — 用管理员后门账号替代业务账号跑业务断言。
   权限溢出会让越权类用例得出虚假通过（例如「无权限账号应被拦截」）。
4. 账号一律通过 `.env` 的 `METERING_USERNAME` / `METERING_PASSWORD`
   （支持 `METERING_<ENV>_USERNAME` 按环境覆盖）配置，**不硬编码**。
   换人只改配置，不改代码；未配置时自动回退主账号 + 4A 登录。

## Black-box Navigation Boundary（最高优先级，不可协商）

> **禁止用任何 URL 直链到功能页。必须模拟真实用户的鼠标点击。**
>
> 用户已就此强调 **三次以上**（2026-11-12、2026-11-17 ×2）。这不是风格偏好，
> 是正确性问题。

### 为什么（真实案例，会得出相反结论）

| 直链 | 后果 |
| --- | --- |
| `#/sub/resource/subscription/app/appInfo?suitKey=1899...727` | 绕过路由守卫，进到该账号本不该有的套件，看到**其他租户的数据**，据此误判"账号有数据、可替代主账号" |
| `#/portal/home/workbench?suitKey=portal` | 绕过「显示名 → 切换租户」的视图选择，进到不属于该账号的空间，看到 828 条 / 26 租户的数据，据此误判"四个列表全部越权" |
| `#/portal/order/list` | 生产路由已迁到 `#/sub/resource/orderCenter/myOrders`，直链落到非列表页，列表接口根本不发，断言只能失败 |

**关键**：直链看到的"丰富数据"往往不是业务视图，而是权限收口被绕过后的产物。
用它下结论，方向就是反的。

### 唯一允许的 URL 导航

1. **登录入口**（等价于用户在浏览器输入站点地址）：`BASE_URL`、`ADMIN_LOGIN_URL`、`iam cas/login`、`passport/login`
2. **门户首页**：`云门户 BASE_URL`

其余一律点击。

### 正确的进入路径（2026-11-17 用户明确）

- **进控制台空间（irp 域）**：门户 → 右上角显示名 → 切换租户 → 「中建云控制台空间」
- **进工作台空间某租户（cloud 域）**：门户 → 右上角「管理后台」→ 选择「工作台」→ 右上角显示名 → 切换租户 → 指定租户
- **进控制台内二级页**（订单/审批/工单/订阅…）：`ConsoleMenuPage.open_menu_path()` 走左侧菜单树
- **进工作台卡片**：点「常用模块」卡片

### 强制检查（CI 必过）

```bash
python tools/check_no_deeplink.py     # 违规 exit 1
```

扫描 `pages/`、`tests/` 里所有 `goto` / `goto_url` / `goto_path` 调用，目标含
`#/` 或 `suitKey=` 即违规；同时识别"引用了含路由片段的常量"（如
`CONSOLE_WORKBENCH_ROUTE`），避免用变量绕过检查。

确属登录入口才可豁免，写法：行尾 `# noqa: deeplink 原因`。

---

## Mandatory Production Release Walkthrough Suite
- **Mandatory Suite**: All 115 PC + Mobile read-only smoke cases defined in `docs/prod-release-mandatory-walkthrough-suite.md` are mandatory on every release. This count grows when a production probe is stabilized and approved as a release gate.
- **Production Execution**: `python run_tests.py --env prod` automatically executes the full 115-case mandatory suite with 0 write risk.
- **Strict Console Gate**: `python run_tests.py --env prod --prod-suite mandatory` executes the 44 strict console Mandatory cases with no skip or soft-pass path.
- **Conditional Console Gate**: `python run_tests.py --env prod --prod-suite conditional` currently executes 69 API-gated console cases and reports unmet preconditions as `NOT_APPLICABLE`.
- **Count Semantics**: The 115 default production nodes (`smoke and readonly`) and the 113 console contracts are overlapping sets, not a parent/child count. The default gate also contains login, portal, mobile, and document-center nodes, while some Conditional console contracts are explicit-only and therefore outside the default gate.

## Automatic Git & DevOps Maintenance

> **作用域约束（关键安全规则）**：本工程是 `D:/Automation` 这个更大 git 仓库的子目录。仓库根在父目录，其中含大量无关项目（JaCoCo / Jmeter / Playwright / Claude / AutoInspection 等）。**所有 git 操作必须显式限定到本工程子树，绝不可在父目录作用域执行 `git add` / `git commit` / `git push`，否则会误提交/误推送无关代码。**
>
> 定义常量：`PROJECT_DIR = D:/Automation/cscec-ui-autotest`（即本工程根目录）。

1. **Auto-Evaluate Updates**: Automatically determine if file changes in `pages/`, `tests/`, `core/`, `config/`, `test_assets/`, `docs/`, `tools/`, `utils/`, or the project-root files (`AGENTS.md`, `handoff.md`, `README.md`, `.gitignore`, `requirements.txt`, `run_tests.py`, `pytest.ini`) constitute a key/meaningful update.
2. **Auto-Verify**: Before committing, automatically run `python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml`, `python tools/validate_prod_console_contracts.py`, and `python run_tests.py --env uat --dry-run`.
3. **Auto-Commit & Push**（全部使用 `git -C "$PROJECT_DIR"` 限定作用域）:
   - **Pre-commit guard（提交前必做）**: 运行 `git -C "$PROJECT_DIR" diff --cached --name-only`，**断言所有暂存路径均以 `cscec-ui-autotest/` 开头**。若有任何路径逸出本工程子树，立即中止提交并告警，不得继续。
   - **Stage only monitored paths（绝不使用 `.` 或 `-A`）**: `git -C "$PROJECT_DIR" add pages tests core config test_assets docs tools utils AGENTS.md handoff.md README.md .gitignore requirements.txt run_tests.py pytest.ini`。
   - **Commit**: Format Conventional Commits (e.g. `feat`, `fix`, `refactor`) — `git -C "$PROJECT_DIR" commit -m "<type>: <summary>"`。
   - **Push**: 先 `git -C "$PROJECT_DIR" push github master`。
   - **Dual-remote sync（GitHub + 公司内网差异化同步）**: 重要变更推送 GitHub 后，运行 `powershell -ExecutionPolicy Bypass -File tools/sync_project_remotes.ps1`。该脚本会：
     - 推送 GitHub `master`，保留 `.github/`。
     - 通过 `git subtree split --prefix=cscec-ui-autotest` 生成只包含本工程的镜像分支。
     - 为公司内网仓库生成 `cscec-ui-autotest-devops` 镜像，删除 `.github/`，并拦截 `.agents/`、`.workbuddy/`、`.claude/`、`.playwright-cli/`、`auth_states/`、`logs/`、`reports/`、`screenshots/`、`.env`、`.idea/`、`.venv/`、`.pytest_cache/`、`scratch*` 等本地文件。
     - 推送公司内网仓库 `https://devops.cscec.com/osc/irp/irp-ui-autotest.git master`。
   - 在任何 cwd 下执行上述命令，都不会触及 `D:/Automation` 下的无关项目；公司内网仓库也不会包含父目录 `D:/Automation` 内容。
4. **Safety Protection**: 以下路径已被 `.gitignore` 覆盖，禁止提交：`.env`、`auth_states/`（含 `auth_states/*.json`）、`logs/`、`screenshots/`、`reports/`。提交前护栏（第 3 步）是第二道防线：即便 `.gitignore` 遗漏，暂存路径检查也会拦截越界文件。
5. **Status Doc Refresh**: After any change to the monitored dirs, run `python tools/generate_progress_doc.py` to regenerate `docs/PROJECT_STATUS.md` from the asset registry + dry-run (replaces manual maintenance to prevent drift).
