# CSCEC UI Automation Handoff

Last updated: 2026-11-02 (Asia/Shanghai)

## 1. Current Objective

Maintain an engineering-grade Python + Playwright UI automation project for CSCEC UAT, PRE, and production. Production read-only gates cover both split domains:

- Console: `https://irp.cscec.com/`
- Workbench, service center, portal, and mobile: `https://cloud.cscec.com/`

Current execution tracks:

- **Default production walkthrough gate**: `-m "smoke and readonly"` across PC and mobile.
- **Console contract gates**: `--prod-suite mandatory` (strict, zero skip/soft-pass) and `--prod-suite conditional` (API-gated, reports unmet declared prerequisites as `NOT_APPLICABLE`).
- **Explicit metering-subscription 260901 production regression**: `--prod-suite metering` over `tests/metering_subscription_260901/verified` with `context.route` domain/POST read-only allowlists and `retain-on-failure` traces (async CSV export tasks excluded in PROD).
- **BK-CI (蓝盾) UAT daily test toolchain**: `tools/ci_setup.py`, `tools/ci_probe.py`, and `tools/ci_daily_test.py` for Pipeline `9784`.
- **Controlled production writes**: `--prod-suite controlled-write` remains isolated; data-import writes may only touch `中建云测试专用 / 中建云测试专用L1 / 中建云测试专用L2 / 中建云测试专用L3`.

## 2. Current Verified Baseline

Use `docs/PROJECT_STATUS.md` as the generated source of truth for current collection, contract, asset, and stabilization counts. Do not maintain expected counts manually in this file.

Set-relationship semantics:

- Default production nodes (`smoke and readonly`) and console contracts (`prod_console_case_contracts.yaml`) are overlapping sets, not parent/child counts: the default gate includes login, portal, mobile, and doccenter smoke cases, while some Conditional console contracts are explicit-only.
- Metering `tests/metering_subscription_260901/` contains two distinct layers: legacy PRE-only outline scripts (skipped before browser launch outside PRE) and the audited `verified/` workflow suite (enabled for PRE and explicit `--prod-suite metering` in PROD; candidate status, not part of default `--env prod`).

Key commands:

```powershell
python run_tests.py --env prod
python run_tests.py --env prod --prod-suite mandatory
python run_tests.py --env prod --prod-suite conditional
python run_tests.py --env prod --prod-suite metering --headless
python tools/ci_daily_test.py --env uat --scope readonly
```

## 3. Latest Production Results

The following is the last executed production snapshot from **2026-10-15** (local evidence archived in gitignored `reports/production-release-20261015-182209/`). It is historical execution evidence, not a generated current count.

### Default 115-case production gate (2026-10-15 first full batch)

- **Overall**: 109 passed, 6 failed, 0 skipped
- **Console contract subset in this batch (92 cases)**:
  - Mandatory: 42 passed, 2 failed
  - Conditional: 44 passed, 4 failed

### Six failures recorded in the 2026-10-15 default gate

1. **`C-P0-CONSOLE-WB-008` (`data-source-config`, Conditional — real product SSO defect)**
   - Path: console workbench -> 数据源配置.
   - Destination page renders, but cross-domain authorization consistently returns:
     ```text
     https://data.cscec.com/auth/resolve/getNoGrantButtons
     code=1401
     当前用户已经退出登录，请重新登录
     ```
   - Treat as a real cross-domain SSO defect. Never add an ignore rule, soft pass, or skip.
2. **`SUBSCRIPTION-API-001` (`test_subscription_sidebar_leaf`, Mandatory — post-release contract drift)**
   - Following the 2026-10-15 metering release, production console API list switched from `/console/rsc/api/apply/history/list` to `/quota-instance/aggregateForConsole` (HTTP 200). Legacy test timed out waiting for the retired endpoint and needs contract migration to the new parent-child aggregation model.
3. **`METER-SUBSCRIPTION-DETAIL-001` (`test_first_subscription_tenant_detail`, Mandatory — health-monitor noise candidate)**
   - Tenant identity and detail business assertions passed, then `GET https://irp.cscec.com/udpweb/portal/image/skeleton-screen.png` aborted (`net::ERR_ABORTED`) during navigation/teardown and failed `BrowserHealthMonitor`.
4. **`C-P0-CONSOLE-WB-004` (`api-subscription`, Conditional — locator/readiness mismatch)**
   - Failure screenshot confirmed `常用模块` and `API订阅` were visible on the console workbench, but the module-card readiness locator failed before clicking.
5. **`M3-04` (`test_m3_04_message_bell_click_and_navigate`, Conditional — response listener race)**
   - Unread-message API returned HTTP 200 ~106ms before the bell click; waiting for a post-click response on the same path timed out at 60s.
6. **`M4-10` (`test_m4_10_ticket_creation_day_filter_and_reset`, Conditional — cross-month picker gap)**
   - Sample ticket creation date (`2026-09-16`) was in a prior month while the calendar popup stayed on `2026-10`, matching 0 day cells before any filter request was sent.

> Note: Conditional order-action boundary cases (`M2-09` edit, `M2-10` evaluate, `M2-11` terminate) remain explicit Conditional cases (`--prod-suite conditional`) and legitimately report `NOT_APPLICABLE` when no order carries both API permission and an enabled button.

### Metering-subscription 260901 explicit production regression (2026-10-15)

- **Scope**: 38 collected read-only workflows (mapping 61 outline items; 1 async CSV export workflow excluded in PROD).
- **Outcome**: Initial full batch recorded 30 passed / 8 skipped (`exitstatus=0`). Combined with same-release production route configuration and the component-delivery query fix (`7bb8b4b`), **32 workflows passed with 0 business assertion failures and 6 open coverage/sample gaps**:
  - `wb_modes`: selected production resource lacked a multi-service-mode sample.
  - `unlimited`: lacked independent order/spec confirmation for unlimited quota (do not infer from `quota=0` or UI text alone).
  - `personal_isolation`: lacked a strict same-resource, same-app, different-user sample.
  - `daily_pagination`: sampled interface lacked a multi-page daily detail dataset.
  - `M7.1.2`: formal console column order contract still awaits product confirmation.
  - `delivery`: `component-portal/my/list` succeeded with an empty list (no positive API/SDK provider component sample in current tenant).
- **Confirmed formal labels (2026-10-15)**: `M2.1.2` = `资源发布方`, `M5.2.1` = `订阅人所在租户`.

## 4. Recently Completed Capabilities

1. **Metering-Subscription 260901 Black-Box & PROD Read-Only Suite** (`docs/metering-subscription-260901-prod-regression.md`, `docs/metering-subscription-260901-blackbox-automation.md`)
   - Dynamic current-run reconciliation across parent-child `instanceIds`, account quotas, interface summaries, paginated daily details, and order forms (`core/metering_blackbox_contract.py`, `pages/metering_blackbox_page.py`).
   - Strict `context.route` host and read-only POST allowlist enforcement, isolated per-domain/tenant browser contexts, `MeteringTraces` failure trace retention (`core/metering_trace.py`), phase-aware `ResultRecorder` (`tools/metering_results_260901.py`), and non-destructive XMind outline export (`tools/generate_metering_outline_260901.py`).
2. **BK-CI (蓝盾) Daily Test Toolchain & Remote Mirror Hardening** (`docs/ci-cicd-daily-test-guide.md`)
   - Environment-agnostic scripts (`tools/ci_setup.py`, `tools/ci_probe.py`, `tools/ci_daily_test.py`, `tools/ci_locate_workspace.sh`) handling workspace subdirectory checkouts, `BROWSER_CHANNEL=chromium` in Linux containers, multi-mirror pip fallback, and secret-injected `.env` generation.
   - Idempotent dual-remote subtree sync (`tools/sync_project_remotes.ps1`) stripping `.github/` and blocking local/secret paths when pushing to company DevOps (`https://devops.cscec.com/osc/irp/irp-ui-autotest.git`).
3. **Local Planning & Exploration Artifacts (Gitignored, Not Committed)**
   - `reports/prod-tenant-role-planning-20261016/plan.html`: 5-tenant production probe and P0–P5 single-account multi-tenant persona plan. Key finding: switching tenants updates `orgNo/orgName` while `tenantNo/tenantName` can remain root `ZH_01_0000` — never verify active tenant by `tenantNo` alone.
   - `reports/api-restart-research/`: 2026-10-20 inventory of 417 legacy DevOps API scenes and 1 passing linkroad POC.
   - `debug/uat_login.py`: local UAT session helper covering `irp-uat`, `cloud-uat`, and `customer-uat.cscec.com` (kept in gitignored `debug/` until credentials/waits are refactored into formal Page Objects).

## 5. Decisions That Must Be Preserved

- Production release gates are not capped at a fixed count. Every stabilized production probe may become a gate.
- Production read-only tests must not click final submit, delete confirmation, reminder, approval, termination, async export task creation, or other direct-write actions.
- Confirmation-boundary tests may open a confirmation dialog and cancel only when no non-GET request is emitted before final confirmation.
- Conditional cases may report `NOT_APPLICABLE` only for a registered prerequisite checked before the business action. Runtime errors must fail.
- Use real menu navigation and dynamic API identities. Never reuse PRE menu IDs, stale direct URLs, historical counts, or PRE pass records as production proof.
- Verify tenant switches via `orgNo/orgName` and visible tenant/menu evidence, not `tenantNo` or `help/curRole` alone.
- A rendered page with a failing critical business response is a failure, not a pass. Do not hide the data-source `1401` defect.
- Keep `time.sleep()` and fixed sleeps out of Playwright tests; use Playwright web-first waits and assertions.
- Prefer role, text, label, placeholder, and test-id locators over absolute XPath or fragile hierarchy CSS.

## 6. Code and Git State

Read current project history with `git -C D:/Automation/cscec-ui-autotest log -5 --oneline -- .` and verify remote synchronization when needed.

Important repository topology and hygiene rules:

- Project directory: `D:/Automation/cscec-ui-autotest`
- Actual Git repository root is the parent `D:/Automation` and contains many unrelated projects.
- Every Git operation must use `git -C D:/Automation/cscec-ui-autotest`.
- Never stage `.` or `-A`; stage only monitored paths defined in `AGENTS.md`.
- Before committing, verify every cached path begins with `cscec-ui-autotest/`.
- Keep the project root free of untracked scratch files: `tools/sync_project_remotes.ps1` aborts if any unexpected modified or untracked path exists under `cscec-ui-autotest/`. Local-only debug scripts belong in gitignored `debug/`.
- `.env.example` uses placeholders only; real credentials belong in gitignored `.env` or CI secret variables. Never commit `.env`, `auth_states/`, `reports/`, `screenshots/`, `logs/`, or `debug/`.

Dual remote workflow:

```powershell
git -C D:/Automation/cscec-ui-autotest push github master
powershell -ExecutionPolicy Bypass -File tools/sync_project_remotes.ps1
```

## 7. Required Verification Before Any Future Commit

Run all of the following:

```powershell
.venv\Scripts\python.exe tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml
.venv\Scripts\python.exe tools/validate_prod_console_contracts.py
.venv\Scripts\python.exe run_tests.py --env uat --dry-run
.venv\Scripts\python.exe tools/generate_progress_doc.py
```

Read generated counts from `docs/PROJECT_STATUS.md`; all validators must exit with code `0`.

## 8. Remaining Work

1. **Repair the 5 test/contract regressions from the 2026-10-15 production gate** (excluding the real `1401` SSO defect):
   - Migrate `SUBSCRIPTION-API-001` from retired `/console/rsc/api/apply/history/list` to `/quota-instance/aggregateForConsole` parent-child contract.
   - Support cross-month calendar navigation in `M4-10` (`pages/console/ticket_center_page.py`).
   - Capture preloaded unread-message responses before/around bell click in `M3-04` (`pages/portal/message_center_page.py` / `tests/console/test_approval_todo_chain.py`).
   - Diagnose and update workbench module-card readiness in `C-P0-CONSOLE-WB-004` (`pages/console/console_workbench_page.py`).
   - Audit `skeleton-screen.png` `net::ERR_ABORTED` navigation timing vs `BrowserHealthMonitor` in `METER-SUBSCRIPTION-DETAIL-001`.
2. **Track external SSO defect `C-P0-CONSOLE-WB-008`**: once the SSO/data-platform team resolves `data.cscec.com` `code=1401`, rerun `C-P0-CONSOLE-WB-008` first, then the Conditional and default production suites.
3. **Provision clean production personas & sample data for metering gaps**: execute the `2026-10-16` tenant-role plan (new clean ordinary-member & restricted-member tenants, positive API/SDK component samples, multi-mode/multi-page samples) and confirm `M7.1.2` console column order with product.
4. **Refresh static baseline numbers in `docs/ci-cicd-daily-test-guide.md`**: update its `2026-09-22` example counts (`521` / `183`) to reference `docs/PROJECT_STATUS.md` so BK-CI Stage 2 checks are not misread.
5. **Formalize `customer-uat.cscec.com` if brought into scope**: remove hardcoded fallback credentials and fixed sleeps from `debug/uat_login.py` before moving anything into `config/`, `pages/`, or `tools/`.

## 9. Recommended First Action in the New Chat

Read this file, `AGENTS.md`, and `docs/PROJECT_STATUS.md` (plus `reports/production-release-20261015-182209/summary.html` if still present locally). Report the verified baseline and open items concisely, then confirm which workstream the user wants to execute. Do not launch the full ~20-minute production browser suite unless requested or verifying an explicit fix.
