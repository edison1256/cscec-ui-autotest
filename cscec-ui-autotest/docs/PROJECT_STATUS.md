# 项目状态文档（自动生成）

> 本文件由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 自动派生，生成时间 2026-09-18 11:29。请勿手工编辑——改完受监控目录后重跑生成器即可。
>
> 旧文档 `docs/task-progress-2026-08-12-ui-autotest.md` 已过期被本文件取代。

## 1. 生产默认套件规模（pytest 实际收集）

- **总用例数**：483
- **生产默认收集（smoke + readonly）**：98 / 483
- **被默认排除（write / destructive）**：385

> 生产强制走查套件 = `smoke and readonly`，与 AGENTS.md 声明一致，零写入风险。

## 2. 资产治理状态（来自 registry）

- **登记资产总数**：177

### 按生命周期（lifecycle）

| lifecycle | 数量 |
| --- | --- |
| uat_automated | 96 |
| prod_regression | 41 |
| candidate | 40 |

### 按自动化状态（automation_status）

| automation_status | 数量 |
| --- | --- |
| automated | 143 |
| needs_stabilization | 34 |

### 按模块（module）

| module | 数量 |
| --- | --- |
| 分层数据资源导入 | 53 |
| 数据资源导入功能优化 | 24 |
| 资源管理 | 14 |
| 移动端 | 12 |
| 系统配置 | 10 |
| 控制台 | 8 |
| 计量统计 | 8 |
| 订阅服务 | 8 |
| 权限管理 | 5 |
| 订单管理 | 5 |
| 审批待办 | 5 |
| 文档中心 | 4 |
| 工单中心 | 4 |
| 运营管理 | 4 |
| 运维监控 | 3 |
| 登录 | 2 |
| 门户 | 2 |
| 运维巡检 | 2 |
| 控制台工作台 | 2 |
| 评价中心 | 2 |

## 3. 待稳定资产与监控项（needs_stabilization）

共 **34** 条，根因多为 UAT 未暴露对应菜单入口，处置方式见各条 notes：

| asset_id | module | title | test_path | notes |
| --- | --- | --- | --- | --- |
| UI-REG-CONSOLE-001 | 控制台 | 服务供给入口 | `tests/console/test_console_navigation.py::TestConsoleNavigation::test_navigate_to_service_supply` | 弹性导航已接入：菜单点击→直链兜底(DEEP_LINKS)→入口未暴露自动 pytest.skip，运行结果保持纯洁。2026-08-13 门户控制台入口已修复：navigate_to_console() 现兼容“管理后台”下拉→“控制台”新标签页路径（UAT 实测 PASSED）；服务供给二级入口在 UAT 仍不暴露，对应 UI-REG-CONSOLE-001 的 service_supply 用例保持安全 SKIP，待入口暴露后自动晋级。 |
| UI-REG-DOCCENTER-001 | 文档中心 | 我的文档导航 | `tests/doccenter/test_doc_center.py::TestDocCenter::test_navigate_to_my_documents` | 弹性导航已接入：菜单点击→直链兜底→入口未暴露自动 skip。2026-08-13 UAT 验证：我的文档入口未暴露，已安全 skip；待确认入口或填入 config DEEP_LINKS['my_documents'] 后晋级。 |
| UI-REG-OPS-001 | 运维巡检 | 人工巡检页面可访问 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_inspection_page_accessible` | 弹性导航已接入：菜单点击→直链兜底→入口未暴露自动 skip。2026-08-13 UAT 验证：运维巡检菜单未暴露，已安全 skip；待确认入口路径或填入 config DEEP_LINKS['manual_inspection'] 后晋级。 |
| UI-WRITE-OPS-001 | 运维巡检 | 执行人工巡检保存流程 | `tests/ops/test_manual_inspection.py::TestManualInspection::test_do_inspection` | 写入类用例，默认仅 UAT/PRE；弹性导航已接入，入口未暴露时自动 skip 避免脏写；需确认巡检项目测试数据和入口后再执行。 |
| UI-REQ-DATARESOURCE-M04-009 | 数据资源导入功能优化 | M04 是否本系统产生的数据非是/否当前 UAT 仍拦截 | `tests/dataresources/test_m03_m04_import_contracts.py::TestM03M04ImportA3PositiveContracts::test_m04_non_yes_no_source_system_flag_does_not_block_validation` | 受控监控项（strict xfail）。根因：后端尚未放开「是否本系统产生的数据」的非 是/否 取值。转正条件 = UAT 放开后该用例 XPASS（strict xfail 下 XPASS 判失败），届时移除 test_m03_m04_import_contracts.py 中该用例的 @pytest.mark.xfail 装饰器，转正为正式断言。prod_default/prod_explicit 均关闭，不参与生产套件。 |
| UI-LAYERED-M04-004 | 分层数据资源导入 | M04-04 表英文名实体在库中不存在输出错误数据行 | `tests/layered_data_resource_import/test_m04_attribute_import.py::TestM04EntityLocatorErrors::test_m04_04_missing_entity_shows_error` |  |
| UI-LAYERED-M04-005 | 分层数据资源导入 | M04-05 是否主键/可空/外键非是否或为空校验拦截 | `tests/layered_data_resource_import/test_m04_attribute_import.py::TestM04RequiredAndEnumValidation::test_m04_05_boolean_flags_enum_validation` |  |
| UI-LAYERED-M04-006 | 分层数据资源导入 | M04-06 数据安全分类与安全分级为空校验拦截 | `tests/layered_data_resource_import/test_m04_attribute_import.py::TestM04RequiredAndEnumValidation::test_m04_06_security_classification_required` |  |
| UI-LAYERED-M04-007 | 分层数据资源导入 | M04-07 是否本系统产生的数据为空放行校验 | `tests/layered_data_resource_import/test_m04_attribute_import.py::TestM04PassAndOptionalValidation::test_m04_07_source_system_flag_empty_passes` |  |
| UI-LAYERED-M04-008 | 分层数据资源导入 | M04-08 编码/长度/外键关联/来源系统等非必填放行 | `tests/layered_data_resource_import/test_m04_attribute_import.py::TestM04PassAndOptionalValidation::test_m04_08_optional_fields_pass` |  |
| UI-PROD-SUPP-CONSOLE-001 | 控制台 | 生产控制台补充深层只读探活候选 | `tests/console/test_console_p0_readonly_supp.py::TestConsoleP0ReadonlySupp` | 候选补充探活，不进入生产默认 smoke；入口未暴露按 skip，入口存在但页面/弹窗异常按失败处理。 |
| UI-PROD-SUPP-ORDER-001 | 订单管理 | 生产订单链路补充只读探活候选 | `tests/console/test_order_subscription_chain_supp.py::TestOrderSubscriptionChainSupp` | 覆盖订单状态 Tab、搜索重置、订单详情审批节点渲染；仅显式执行，稳定后再评估是否晋级 smoke。 |
| UI-PROD-SUPP-RESOURCE-001 | 资源管理 | 生产资源管理补充只读探活候选 | `tests/console/test_resource_baseline_supp.py::TestResourceBaselineSupp` | 覆盖高级检索、分页健康和全局动作按钮可见性；只验证展示和查询，不点击新增、保存、删除等动作。 |
| UI-PROD-SUPP-APPROVAL-001 | 审批待办 | 生产审批链路补充只读探活候选 | `tests/console/test_approval_todo_chain_supp.py::TestApprovalTodoChainSupp` | 覆盖已办列表和审批历史/流程图只读查看；不点击同意、驳回、提交等流转动作。 |
| UI-PROD-SUPP-TICKET-001 | 工单中心 | 生产工单链路补充只读探活候选 | `tests/console/test_ticket_basic_chain_supp.py::TestTicketBasicChainSupp` | 仅允许点击工单历史、操作日志、流转日志等只读入口；转派、回复、挂起等流程动作不纳入 readonly。 |
| UI-PROD-SUPP-DOCCENTER-001 | 文档中心 | 生产文档中心补充只读探活候选 | `tests/doccenter/test_doc_center_supp.py::TestDocCenterSupp` | 覆盖文档中心搜索和详情渲染；断言失败不再吞掉，入口未暴露按 skip 处理。 |
| UI-PROD-SUPP-MOBILE-001 | 移动端 | 生产移动端补充只读探活候选 | `tests/mobile/test_mobile_baseline_supp.py::TestMobileBaselineSupp` | 移动端金刚区穿透只允许点击服务、消息、公告、帮助、文档、知识、工作台等只读白名单入口。 |
| UI-PROD-SUPP-PORTAL-001 | 门户 | 生产门户补充只读探活候选 | `tests/portal/test_portal_p0_readonly_supp.py::TestPortalP0ReadonlySupp` | 覆盖门户链接、用户浮层、未授权拦截、图片渲染，以及组织选择页组织树接口返回可选组织数据；候选阶段不进入生产默认 smoke。 |
| UI-PROD-BATCH-G-OPS-CAPACITY-001 | 运维监控 | 容量指标页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 仅校验真实三级菜单、容量指标路由、标题及浏览器健康；暂无稳定业务接口证据，不触发配置或写操作。 |
| UI-PROD-BATCH-G-OPS-PERFORMANCE-001 | 运维监控 | 性能指标查询页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 校验真实三级菜单、性能指标路由、标题、分类/系统查询区与空态；不触发写操作。 |
| UI-PROD-BATCH-G-OPS-POLLING-001 | 运维监控 | 运维巡检页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 校验真实菜单、巡检路由、概览/人工/自动页签、任务指标和可见图表画布；不启动巡检。 |
| UI-PROD-BATCH-G-OPERATION-KANBAN-001 | 运营管理 | 运营看板页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 仅校验真实三级菜单、运营看板路由、标题及浏览器健康；不修改看板配置。 |
| UI-PROD-BATCH-G-OPERATION-INSIGHT-001 | 运营管理 | 效能洞察页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 仅校验真实三级菜单、效能洞察路由、标题及浏览器健康；暂无稳定业务接口证据。 |
| UI-PROD-BATCH-G-OPERATION-DASHBOARD-001 | 运营管理 | 应用看板页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 仅校验真实三级菜单、应用看板路由、标题及浏览器健康；不修改看板配置。 |
| UI-PROD-BATCH-G-OPERATION-MESSAGE-001 | 运营管理 | 消息推送页面只读探查候选 | `tests/console/test_console_operations_deep_readonly.py::TestConsoleOperationsDeepReadonly::test_operations_page_shell` | 仅校验真实菜单、消息推送路由、标题及浏览器健康；不新建、保存或发送消息。 |
| UI-PROD-BATCH-H1-RESOURCE-APP-001 | 资源管理 | 应用管理列表与详情只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 校验真实菜单、应用列表接口动态身份、精确虚拟表格行及同 ID 详情接口；不新增、编辑、上架、排序或同步。 |
| UI-PROD-BATCH-H1-RESOURCE-CLOUD-001 | 资源管理 | 云产品管理列表与查看弹窗只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 校验真实菜单、云产品列表接口动态名称和编码、精确行及查看弹窗四个页签；不变更、上下架或排序。 |
| UI-PROD-BATCH-H1-RESOURCE-API-001 | 资源管理 | API管理应用选择区只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 校验真实菜单、应用接口业务成功且 data 为列表，以及选择应用控件；生产当前返回空列表，不能选择应用，不宣称 API 列表覆盖。 |
| UI-PROD-BATCH-H1-RESOURCE-COMPONENT-001 | 资源管理 | 组件管理页面外壳只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 当前仅校验真实菜单、组件管理路由、标题和浏览器健康；未观察到稳定业务接口或页面内容。 |
| UI-PROD-BATCH-H2-RESOURCE-DATA-ASSET-001 | 资源管理 | 数据资产管理列表与详情只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 校验真实菜单、数据资产列表接口动态名称和编码、精确行及三类元数据详情；不批量编辑、导出、修改或上下架。 |
| UI-PROD-BATCH-H2-RESOURCE-SOLUTION-001 | 资源管理 | 解决方案管理列表与详情只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 校验真实菜单、解决方案列表接口动态名称和编码、精确行及详情专属内容；不新增、编辑、上下架或排序。 |
| UI-PROD-BATCH-H2-RESOURCE-HARDWARE-001 | 资源管理 | 硬件管理页面外壳只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_resource_catalog_leaf` | 当前仅校验真实菜单、硬件管理路由、标题和浏览器健康；未观察到稳定业务接口或页面内容。 |
| UI-PROD-BATCH-H3-RESOURCE-APP-CONFIRM-001 | 资源管理 | 生产专用应用下架确认边界只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_prod_dedicated_sample_confirmation_guard` | 仅精确检索生产专用应用 0512prodtest，打开下架确认框并取消；断言最终确认前没有非 GET 请求。 |
| UI-PROD-BATCH-H3-RESOURCE-CLOUD-CONFIRM-001 | 资源管理 | 生产专用云产品删除确认边界只读探查候选 | `tests/console/test_resource_catalog_management_readonly.py::TestResourceCatalogManagementReadonly::test_prod_dedicated_sample_confirmation_guard` | 仅精确检索生产专用云产品 金仓数据库_测试专用，悬浮展开更多后打开删除确认框并取消；不点击最终确定。 |

## 4. 复用与维护约定

- 变更 `pages/ tests/ core/ config/ test_assets/ docs/` 中任一目录后，运行 `python tools/generate_progress_doc.py` 刷新本文档。
- 自动提交前请遵循 AGENTS.md 的 Git 作用域约束（仅暂存本工程 6 个受监控目录）。

