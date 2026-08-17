# 项目状态文档（自动生成）

> 本文件由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 自动派生，生成时间 2026-08-17 10:31。请勿手工编辑——改完受监控目录后重跑生成器即可。
>
> 旧文档 `docs/task-progress-2026-08-12-ui-autotest.md` 已过期被本文件取代。

## 1. 生产默认套件规模（pytest 实际收集）

- **总用例数**：123
- **生产默认收集（smoke + readonly）**：49 / 123
- **被默认排除（write / destructive）**：74

> 生产强制走查套件 = `smoke and readonly`，与 AGENTS.md 声明一致，零写入风险。

## 2. 资产治理状态（来自 registry）

- **登记资产总数**：103

### 按生命周期（lifecycle）

| lifecycle | 数量 |
| --- | --- |
| uat_automated | 90 |
| prod_regression | 8 |
| candidate | 5 |

### 按自动化状态（automation_status）

| automation_status | 数量 |
| --- | --- |
| automated | 98 |
| needs_stabilization | 5 |

### 按模块（module）

| module | 数量 |
| --- | --- |
| 分层数据资源导入 | 41 |
| 数据资源导入功能优化 | 24 |
| 移动端 | 11 |
| 控制台 | 4 |
| 资源管理 | 4 |
| 订单管理 | 4 |
| 审批待办 | 4 |
| 文档中心 | 3 |
| 工单中心 | 3 |
| 登录 | 2 |
| 运维巡检 | 2 |
| 门户 | 1 |

## 3. 待稳定资产与监控项（needs_stabilization）

共 **5** 条，根因多为 UAT 未暴露对应菜单入口，处置方式见各条 notes：

| asset_id | module | title | test_path | notes |
| --- | --- | --- | --- | --- |
| UI-REG-CONSOLE-001 | 控制台 | 服务供给入口 | `tests/console/test_console_navigation.py::TestConsoleNavigation::test_navigate_to_service_supply` | 弹性导航已接入：菜单点击→直链兜底(DEEP_LINKS)→入口未暴露自动 pytest.skip，运行结果保持纯洁。2026-08-13 门户控制台入口已修复：navigate_to_console() 现兼容“管理后台”下拉→“控制台”新标签页路径（UAT 实测 PASSED）；服务供给二级入口在 UAT 仍不暴露，对应 UI-REG-CONSOLE-001 的 service_supply 用例保持安全 SKIP，待入口暴露后自动晋级。 |
| UI-REG-DOCCENTER-001 | 文档中心 | 我的文档导航 | `tests/doccenter/test_doc_center.py::TestDocCenter::test_navigate_to_my_documents` | 弹性导航已接入：菜单点击→直链兜底→入口未暴露自动 skip。2026-08-13 UAT 验证：我的文档入口未暴露，已安全 skip；待确认入口或填入 config DEEP_LINKS['my_documents'] 后晋级。 |
| UI-REG-OPS-001 | 运维巡检 | 人工巡检页面可访问 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_inspection_page_accessible` | 弹性导航已接入：菜单点击→直链兜底→入口未暴露自动 skip。2026-08-13 UAT 验证：运维巡检菜单未暴露，已安全 skip；待确认入口路径或填入 config DEEP_LINKS['manual_inspection'] 后晋级。 |
| UI-WRITE-OPS-001 | 运维巡检 | 执行人工巡检保存流程 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_do_inspection` | 写入类用例，默认仅 UAT/PRE；弹性导航已接入，入口未暴露时自动 skip 避免脏写；需确认巡检项目测试数据和入口后再执行。 |
| UI-REQ-DATARESOURCE-M04-009 | 数据资源导入功能优化 | M04 是否本系统产生的数据非是/否当前 UAT 仍拦截 | `tests/dataresources/test_m03_m04_import_contracts.py::TestM03M04ImportA3PositiveContracts::test_m04_non_yes_no_source_system_flag_does_not_block_validation` | 受控监控项（strict xfail）。根因：后端尚未放开「是否本系统产生的数据」的非 是/否 取值。转正条件 = UAT 放开后该用例 XPASS（strict xfail 下 XPASS 判失败），届时移除 test_m03_m04_import_contracts.py 中该用例的 @pytest.mark.xfail 装饰器，转正为正式断言。prod_default/prod_explicit 均关闭，不参与生产套件。 |

## 4. 复用与维护约定

- 变更 `pages/ tests/ core/ config/ test_assets/ docs/` 中任一目录后，运行 `python tools/generate_progress_doc.py` 刷新本文档。
- 自动提交前请遵循 AGENTS.md 的 Git 作用域约束（仅暂存本工程 6 个受监控目录）。

