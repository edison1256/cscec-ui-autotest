# 项目状态文档（自动生成）

> 本文件由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 自动派生，生成时间 2026-09-21 17:02。请勿手工编辑——改完受监控目录后重跑生成器即可。
>
> 旧文档 `docs/task-progress-2026-08-12-ui-autotest.md` 已过期被本文件取代。

## 1. 生产默认套件规模（pytest 实际收集）

- **总用例数**：515
- **生产默认收集（smoke + readonly）**：115 / 515
- **被默认排除（write / destructive）**：400

- **控制台机器契约**：113
  - Mandatory：44
  - Conditional：69

> 生产默认节点与控制台契约是交叉集合，不可直接相减。默认套件还包含登录、门户、移动端和文档中心节点；部分 Conditional 控制台契约只允许显式执行。

## 2. 资产治理状态（来自 registry）

- **登记资产总数**：183

### 按生命周期（lifecycle）

| lifecycle | 数量 |
| --- | --- |
| uat_automated | 96 |
| prod_regression | 63 |
| candidate | 24 |

### 按自动化状态（automation_status）

| automation_status | 数量 |
| --- | --- |
| automated | 173 |
| needs_stabilization | 10 |

### 按模块（module）

| module | 数量 |
| --- | --- |
| 分层数据资源导入 | 53 |
| 数据资源导入功能优化 | 24 |
| 资源管理 | 14 |
| 移动端 | 12 |
| 计量统计 | 12 |
| 系统配置 | 10 |
| 控制台 | 8 |
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
| 审批流程 | 2 |

## 3. 外部阻塞与待稳定资产（needs_stabilization）

共 **10** 条，仍受入口、数据、环境或后端规则阻塞，处置方式见各条 notes：

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

## 4. 已自动化但未晋级的候选观察项

共 **14** 条。它们可稳定显式执行，但尚未批准进入生产默认门禁：

| asset_id | module | title | test_path | notes |
| --- | --- | --- | --- | --- |
| UI-PROD-PERM-ROLE-001 | 权限管理 | 角色成员、数据权限与编辑回显深层只读回归 | `tests/console/test_role_management_readonly_regression.py::TestRoleManagementDeepReadonlyCandidate::test_role_members_data_permissions_and_edit_preview` | 从角色列表接口动态建立角色身份；验证成员表、数据权限两个业务接口、所属租户/后端类目/领域及禁用的全量数据开关；编辑仅检查回显与禁用保存，随后取消并确认，不修改角色。 |
| UI-PROD-PERM-LOGIN-001 | 权限管理 | 4A登录资源、组织与部门用户深层只读回归 | `tests/console/test_permission_management_deep_readonly.py::TestPermissionManagementDeepReadonly::test_4a_login_resource_organization_and_users` | 从资源与组织接口动态建立身份，选择组织后严格核对 userPage 请求中的资源 ID、组织编码和首条用户回显；授权登录、取消授权仅验证可见，不点击。 |
| UI-PROD-PERM-LOGIN-002 | 权限管理 | 组织登录资源与组织树深层只读回归 | `tests/console/test_permission_management_deep_readonly.py::TestPermissionManagementDeepReadonly::test_organization_login_resource_and_tree` | 资源身份由 cloud/page 与页面选中项共同证明，组织树由当前资源 ID 查询并严格校验业务码和根组织回显；授权按钮只检查展示。 |
| UI-PROD-PERM-USER-001 | 权限管理 | 当前用户精确查询、详情与重置深层只读回归 | `tests/console/test_permission_management_deep_readonly.py::TestPermissionManagementDeepReadonly::test_user_list_exact_query_detail_and_reset` | 以当前登录账号建立可解密的用户身份；生产后端会拒绝查看其他用户详情并返回 10006，因此不再随机选择首行用户。详情仅检查禁用字段并返回，重置仅清空查询条件。 |
| UI-PROD-PERM-TENANT-001 | 权限管理 | 中建云租户身份与成员空查询深层只读回归 | `tests/console/test_permission_management_deep_readonly.py::TestPermissionManagementDeepReadonly::test_current_tenant_identity_and_empty_member_query` | 固定核对当前中建云租户 100000 / ZH_01_0000；成员表本身有数据，测试使用每次唯一的不存在关键字验证严格空结果。添加、待加入和批量移出入口仅检查可见，不点击。 |
| UI-LAYERED-M02-PROD-SEED-001 | 分层数据资源导入 | 生产专用域下运行时唯一层级路径种子构造与可见性验证 | `tests/layered_data_resource_import/test_m02_layering_import.py::TestM02ProdExplicitBusinessPaths::test_m02_prod_explicit_business_paths_seed` | 写入型种子按运行 token 生成唯一后缀，避免重复插入；重复校验类用例仍保留重复数据不改造。 |
| UI-PROD-SUPP-CONSOLE-001 | 控制台 | 生产控制台补充深层只读探活候选 | `tests/console/test_console_p0_readonly_supp.py::TestConsoleP0ReadonlySupp` | 候选补充探活，不进入生产默认 smoke；入口未暴露按 skip，入口存在但页面/弹窗异常按失败处理。 |
| UI-PROD-SUPP-ORDER-001 | 订单管理 | 生产订单链路补充只读探活候选 | `tests/console/test_order_subscription_chain_supp.py::TestOrderSubscriptionChainSupp` | 覆盖订单状态 Tab、搜索重置、订单详情审批节点渲染；仅显式执行，稳定后再评估是否晋级 smoke。 |
| UI-PROD-SUPP-RESOURCE-001 | 资源管理 | 生产资源管理补充只读探活候选 | `tests/console/test_resource_baseline_supp.py::TestResourceBaselineSupp` | 覆盖高级检索、分页健康和全局动作按钮可见性；只验证展示和查询，不点击新增、保存、删除等动作。 |
| UI-PROD-SUPP-APPROVAL-001 | 审批待办 | 生产审批链路补充只读探活候选 | `tests/console/test_approval_todo_chain_supp.py::TestApprovalTodoChainSupp` | 覆盖已办列表和审批历史/流程图只读查看；不点击同意、驳回、提交等流转动作。 |
| UI-PROD-SUPP-TICKET-001 | 工单中心 | 生产工单链路补充只读探活候选 | `tests/console/test_ticket_basic_chain_supp.py::TestTicketBasicChainSupp` | 仅允许点击工单历史、操作日志、流转日志等只读入口；转派、回复、挂起等流程动作不纳入 readonly。 |
| UI-PROD-SUPP-DOCCENTER-001 | 文档中心 | 生产文档中心补充只读探活候选 | `tests/doccenter/test_doc_center_supp.py::TestDocCenterSupp` | 覆盖文档中心搜索和详情渲染；断言失败不再吞掉，入口未暴露按 skip 处理。 |
| UI-PROD-SUPP-MOBILE-001 | 移动端 | 生产移动端补充只读探活候选 | `tests/mobile/test_mobile_baseline_supp.py::TestMobileBaselineSupp` | 移动端金刚区穿透只允许点击服务、消息、公告、帮助、文档、知识、工作台等只读白名单入口。 |
| UI-PROD-SUPP-PORTAL-001 | 门户 | 生产门户补充只读探活候选 | `tests/portal/test_portal_p0_readonly_supp.py::TestPortalP0ReadonlySupp` | 覆盖门户链接、用户浮层、未授权拦截、图片渲染，以及组织选择页组织树接口返回可选组织数据；候选阶段不进入生产默认 smoke。 |

## 5. 复用与维护约定

- 变更 `pages/ tests/ core/ config/ test_assets/ docs/` 中任一目录后，运行 `python tools/generate_progress_doc.py` 刷新本文档。
- 自动提交前请遵循 AGENTS.md 的 Git 作用域约束，只暂存其中列出的本工程目录和根文件。

