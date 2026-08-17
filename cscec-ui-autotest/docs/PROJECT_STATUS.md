# 项目状态文档（自动生成）

> 本文件由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 自动派生，生成时间 2026-08-13 15:45。请勿手工编辑——改完受监控目录后重跑生成器即可。
>
> 旧文档 `docs/task-progress-2026-08-12-ui-autotest.md` 已过期被本文件取代。

## 1. 生产默认套件规模（pytest 实际收集）

- **总用例数**：80
- **生产默认收集（smoke + readonly）**：49 / 80
- **被默认排除（write / destructive）**：31

> 生产强制走查套件 = `smoke and readonly`，与 AGENTS.md 声明一致，零写入风险。

## 2. 资产治理状态（来自 registry）

- **登记资产总数**：62

### 按生命周期（lifecycle）

| lifecycle | 数量 |
| --- | --- |
| uat_automated | 49 |
| prod_regression | 8 |
| candidate | 5 |

### 按自动化状态（automation_status）

| automation_status | 数量 |
| --- | --- |
| automated | 57 |
| needs_stabilization | 5 |

### 按模块（module）

| module | 数量 |
| --- | --- |
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
| UI-REG-CONSOLE-001 | 控制台 | 服务供给入口 | `tests/console/test_console_navigation.py::TestConsoleNavigation::test_navigate_to_service_supply` | 已从 smoke 降级到 regression；需单独稳定二级页面断言后再晋级。 |
| UI-REG-DOCCENTER-001 | 文档中心 | 我的文档导航 | `tests/doccenter/test_doc_center.py::TestDocCenter::test_navigate_to_my_documents` | 当前 UAT 页面未暴露“我的文档”入口，需确认入口或调整定位。 |
| UI-REG-OPS-001 | 运维巡检 | 人工巡检页面可访问 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_inspection_page_accessible` | 当前门户首页未暴露“运维巡检”菜单，需确认入口路径。 |
| UI-WRITE-OPS-001 | 运维巡检 | 执行人工巡检保存流程 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_do_inspection` | 写入类用例，默认仅 UAT/PRE；需确认巡检项目测试数据和入口后再执行。 |
| UI-REQ-DATARESOURCE-M04-009 | 数据资源导入功能优化 | M04 是否本系统产生的数据非是/否当前 UAT 仍拦截 | `tests/dataresources/test_m03_m04_import_contracts.py::TestM03M04ImportA3PositiveContracts::test_m04_non_yes_no_source_system_flag_does_not_block_validation` | 受控监控项（strict xfail）。根因：后端尚未放开「是否本系统产生的数据」的非 是/否 取值。转正条件 = UAT 放开后该用例 XPASS（strict xfail 下 XPASS 判失败），届时移除 test_m03_m04_import_contracts.py 中该用例的 @pytest.mark.xfail 装饰器，转正为正式断言。prod_default/prod_explicit 均关闭，不参与生产套件。 |

## 4. 复用与维护约定

- 变更 `pages/ tests/ core/ config/ test_assets/ docs/` 中任一目录后，运行 `python tools/generate_progress_doc.py` 刷新本文档。
- 自动提交前请遵循 AGENTS.md 的 Git 作用域约束（仅暂存本工程 6 个受监控目录）。

