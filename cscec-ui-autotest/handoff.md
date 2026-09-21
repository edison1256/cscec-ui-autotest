# CSCEC UI Automation Handoff

Last updated: 2026-09-21 (Asia/Shanghai)

## 1. Current Objective

Maintain an engineering-grade Python + Playwright UI automation project for CSCEC UAT, PRE, and production. The current production goal is a read-only release gate that covers both split domains:

- Console: `https://irp.cscec.com/`
- Workbench, service center, portal, and mobile: `https://cloud.cscec.com/`

Production write cases remain separately controlled. Data-import writes may only touch the dedicated production hierarchy `中建云测试专用 / 中建云测试专用L1 / 中建云测试专用L2 / 中建云测试专用L3`.

## 2. Current Verified Baseline

- Full project collection: 513 tests.
- Default production read-only gate: 115 tests.
- Strict console Mandatory suite: 44 tests.
- Console Conditional suite: 69 tests.
- Machine-readable production console contracts: 113 total = 44 Mandatory + 69 Conditional.
- UI asset registry: 183 assets.
- Assets still marked `needs_stabilization`: 18, reduced from 34 after correcting 16 already-stable Batch G/H assets to `prod_regression/automated`.

Required commands:

```powershell
python run_tests.py --env prod
python run_tests.py --env prod --prod-suite mandatory
python run_tests.py --env prod --prod-suite conditional
```

## 3. Latest Production Results

### Default 115-case production gate

- 113 passed
- 1 failed
- 1 NOT_APPLICABLE
- Mandatory: 44/44 passed

### Full 69-case Conditional suite

- 64 passed
- 1 failed
- 4 NOT_APPLICABLE

### Stable production defect

Case: `C-P0-CONSOLE-WB-008-data-source-config`

Path: console workbench -> 数据源配置.

The destination page renders, but the cross-domain authorization request consistently fails:

```text
https://data.cscec.com/auth/resolve/getNoGrantButtons
code=1401
当前用户已经退出登录，请重新登录
```

This reproduced in the default gate, full Conditional suite, and a targeted rerun. Treat it as a real cross-domain SSO defect. Do not add an ignore rule, soft pass, or skip.

### Current NOT_APPLICABLE cases

- `M3-04`: no unread message with a navigable business URL.
- `M2-09`: no order with both API `edit` permission and an enabled edit button.
- `M2-10`: no order with both API `evaluate` permission and an enabled evaluation action.
- `M2-11`: no order with both API `terminate` permission and an enabled termination action.

These are valid, contract-defined precondition outcomes before any business action. When production data changes, the same tests automatically continue into the real read-only interaction.

## 4. Recently Completed Automation

The ticket-management query area is fully covered:

- `M4-01`: exact ticket-code query.
- `M4-02`: detail and process identity.
- `M4-04`: action safety boundary.
- `M4-05`: pagination identity.
- `M4-06`: status filter and reset.
- `M4-07`: ticket-type filter and reset.
- `M4-08`: urgency filter and reset.
- `M4-09`: title/description filter via `queryfilter.description` and reset.
- `M4-10`: same-day creation-time filter via `insertDtStart/insertDtEnd` and reset.

`M4-09` and `M4-10` passed targeted and combined production runs. Ticket Page Object contract tests include positive and negative checks for keyword matching and date boundaries.

The six visible ticket query controls now have request/response/UI closure: type, status, urgency, creation time, ticket code, and title/description.

## 5. Decisions That Must Be Preserved

- Production release gates are not capped at a fixed count. Every stabilized production probe may become a gate.
- Production read-only tests must not click final submit, delete confirmation, reminder, approval, termination, or other direct-write actions.
- Confirmation-boundary tests may open a confirmation dialog and cancel only when no non-GET request is emitted before final confirmation.
- Conditional cases may report `NOT_APPLICABLE` only for a registered prerequisite checked before the business action. Runtime errors must fail.
- Use real menu navigation and dynamic API identities. Do not rely on stale direct URLs or fixed production records unless an explicitly dedicated test record is registered.
- A rendered page with a failing critical business response is a failure, not a pass.
- Do not hide the data-source `1401` defect.
- Keep `time.sleep()` out of Playwright tests; use Playwright web-first waits and assertions.
- Prefer role, text, label, placeholder, and test-id locators over absolute XPath or fragile hierarchy CSS.

## 6. Code and Git State

Latest project commits:

- `f3d3db8 docs: close completed production probe stages`
- `9a6deaf feat: complete ticket filter release gates`
- `5ee87ac feat: add ticket urgency filter release gate`

Both GitHub and the company DevOps repository were synchronized after `f3d3db8`.

Important repository topology:

- Project directory: `D:/Automation/cscec-ui-autotest`
- Actual Git repository root is the parent `D:/Automation` and contains many unrelated projects.
- Every Git operation must use `git -C D:/Automation/cscec-ui-autotest`.
- Never stage `.` or `-A`.
- Before committing, verify every cached path begins with `cscec-ui-autotest/`.
- `.env.example` contains a pre-existing user change and must not be staged unless the user explicitly requests it.
- Never commit `.env`, `auth_states/`, `reports/`, `screenshots/`, or `logs/`.

Dual remote workflow:

```powershell
git -C D:/Automation/cscec-ui-autotest push github master
powershell -ExecutionPolicy Bypass -File tools/sync_project_remotes.ps1
```

The sync script keeps `.github/` on GitHub and removes it from the company mirror.

## 7. Required Verification Before Any Future Commit

Run all of the following:

```powershell
.venv\Scripts\python.exe tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml
.venv\Scripts\python.exe tools/validate_prod_console_contracts.py
.venv\Scripts\python.exe run_tests.py --env uat --dry-run
.venv\Scripts\python.exe tools/generate_progress_doc.py
```

Current expected verification values:

- Registry valid, 183 assets.
- Production contracts valid, 113 cases.
- Contract classifications: Conditional 69, Mandatory 44.
- UAT dry-run collection: 513 tests.
- Generated project status: production collected 115/513, needs stabilization 18.

## 8. Remaining Work

There is no unfinished implementable phase in the current production interaction-matrix plan. Remaining work is event-driven:

1. After the data-source cross-domain SSO defect is fixed, rerun `C-P0-CONSOLE-WB-008` first, then the complete Conditional suite.
2. When unread messages or actionable edit/evaluate/terminate order samples appear, rerun `M3-04` and `M2-09/M2-10/M2-11`; successful real execution may justify promotion review.
3. The remaining 18 `needs_stabilization` assets are blocked by unexposed entries, controlled-write scope, an unreleased UAT backend rule, or supplementary probe status. Review individually; do not bulk-promote them.
4. Preserve the production defect evidence and report it to the owning SSO/data-platform team.

## 9. Recommended First Action in the New Chat

Read this file, `AGENTS.md`, and the latest production contract report if it still exists locally. Then report the current baseline and ask only for a new requirement or notification that one of the external blockers has changed. Do not rerun the 12-minute full production gate unless requested or an external fix has been released.
