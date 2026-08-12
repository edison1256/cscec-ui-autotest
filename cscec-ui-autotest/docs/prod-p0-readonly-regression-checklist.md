# PROD P0 只读页面回归清单

本文档记录阶段 3-C 第一轮从 PROD 环境反向梳理出的 P0 只读页面回归清单，目标是覆盖“页面可访问、核心区域可展示、基础只读交互不报错”。第一批 `ready` 候选已落地为 pytest 自动化，并通过 PROD 默认 `smoke + readonly` 实跑。

## 1. 梳理依据

- 探查环境：PROD，`https://irp.cscec.com/`
- 探查日期：2026-08-11
- 探查方式：使用 `.env` 中 PROD 账号登录临时浏览器上下文，仅做页面访问和只读安全交互抽样。
- 登录态处理：本轮未保存 `auth_states/prod.json`。
- 工程边界：本工程保持纯 UI 自动化，不通过后端接口或数据库做断言。
- 安全边界：不点击新增、保存、提交、删除、导入、审批、订阅、加入购物车、确认等可能写入或改变业务状态的控件。

## 2. 通过标准

每个 P0 只读页面进入自动化候选前，至少满足：

- 页面能打开，URL 或菜单入口稳定。
- 页面核心标题、菜单、列表、工作台区域或搜索区域可见。
- 未跳回登录页，未出现空白页、浏览器错误页或系统报错页。
- 页面存在安全只读控件时，抽样执行 1 到 3 个交互后无明显报错。
- 只读交互优先选择菜单展开/收起、页签切换、搜索输入填充清空、下拉展开收起、详情弹窗打开关闭、分页切换。

## 3. 第一批 P0 候选清单

| ID | 区域 | 页面/入口 | 入口或路由 | 核心 UI 断言 | 安全只读交互 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C-P0-PORTAL-001 | 门户 | 首页 | `/` | 标题为“中建云”，首页核心内容区域可见 | 本轮未发现必须抽样的明显只读控件 | ready | 适合作为 PROD 默认 smoke 基线 |
| C-P0-PORTAL-002 | 门户 | 服务中心 | `/#/service-center/2` | 标题为“中建云 · 服务中心”，搜索框可见 | 搜索框“请输入搜索内容”填充清空 | ready | 可做搜索框只读交互 |
| C-P0-PORTAL-003 | 门户 | 智能建造 | `/#/smart-construction` | 标题为“智能建造”，“产品市场”区域可见 | 搜索框“请输入搜索内容”填充清空 | ready | 可做页面展示与搜索框只读交互 |
| C-P0-PORTAL-004 | 门户 | 解决方案 | `/#/solution` | 页面可打开，“合作伙伴”等核心区域可见 | 本轮未发现必须抽样的明显只读控件 | ready | 第一版只做展示断言 |
| C-P0-PORTAL-005 | 门户 | 开发者平台 | `/#/developer-platform` | 页面可打开，无登录跳转或错误页 | 安全按钮抽样点击后无明显错误 | ready | 后续实现时需把按钮定位改为语义化控件 |
| C-P0-PORTAL-006 | 门户 | 支持与帮助 | `/#/support` | 页面可打开，无登录跳转或错误页 | 本轮未发现必须抽样的明显只读控件 | ready | 第一版只做展示断言 |
| C-P0-CONSOLE-001 | 控制台 | 工作台首页 | `/udpweb/portal/index.html#/portal/home/workbench...` | “控制台”“工作台”“常用模块”等区域可见 | 菜单名称搜索框填充清空 | ready | 可复用现有控制台登录后新页签能力 |
| C-P0-CONSOLE-002 | 控制台 | 应用中心/菜单总览 | 控制台工作台内入口 | 工作台与常用模块区域可见 | 菜单名称搜索框填充清空 | ready | PROD 当前未稳定暴露“查看全部菜单”，自动化以当前菜单总览为准 |
| C-P0-CONSOLE-003 | 控制台 | 订阅服务菜单组 | 控制台左侧菜单 | “订阅服务”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 第一版检查菜单组展示，不要求所有子菜单默认展开 |
| C-P0-CONSOLE-004 | 控制台 | 审批流程菜单组 | 控制台左侧菜单 | “审批流程”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 只检查菜单和入口展示，不进入审批动作 |
| C-P0-CONSOLE-005 | 控制台 | 订单中心菜单组 | 控制台左侧菜单 | “订单中心”“订单管理”等菜单项可见 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-006 | 控制台 | 工单中心菜单组 | 控制台左侧菜单 | “工单中心”“工单管理”等菜单项可见 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-007 | 控制台 | 评价中心菜单组 | 控制台左侧菜单 | “评价中心”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-008 | 控制台 | 系统配置菜单组 | 控制台左侧菜单 | “系统配置”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-009 | 控制台 | 计量统计菜单组 | 控制台左侧菜单 | “计量统计”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-010 | 控制台 | 运维监控菜单组 | 控制台左侧菜单 | “运维监控”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 可与现有 ops 资产衔接 |
| C-P0-CONSOLE-011 | 控制台 | 运营管理菜单组 | 控制台左侧菜单 | “运营管理”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 只读展示检查 |
| C-P0-CONSOLE-012 | 控制台 | 权限管理菜单组 | 控制台左侧菜单 | “权限管理”菜单组可见，已展开子项作为附加证据 | 菜单名称搜索框填充清空 | ready | 仅检查菜单可见，不进入新增或授权动作 |
| C-P0-CONSOLE-013 | 控制台 | 流程 | `#/sub/resource/flowmodel/list...` | 页面可打开，流程相关区域可见 | 菜单名称搜索框填充清空 | ready | 可作为独立二级页面候选 |

## 4. 暂缓/需确认入口

| ID | 区域 | 页面/入口 | 当前现象 | 结论 | 后续处理 |
| --- | --- | --- | --- | --- | --- |
| C-P0-PENDING-001 | 门户 | 建证大模型 | 本轮点击后采样结果仍为首页内容，未形成稳定独立页面断言 | needs_confirmation | 先确认产品入口、路由和预期展示，再决定是否纳入自动化 |
| C-P0-PENDING-002 | 控制台 | 资源管理菜单组 | 本轮泛化选择器点击超时，最终停留在全部菜单视图；页面本身未观察到系统错误 | needs_stabilization | 后续用更精确菜单选择器重探查，再晋级为 ready |

## 5. 现有 PROD 回归基线

当前资产登记中已有 5 条 `prod_regression + smoke + readonly + prod_default=true` 基线，可继续保留为 PROD 默认集合：

| 资产 ID | 已有测试路径 | 覆盖点 |
| --- | --- | --- |
| UI-BASE-LOGIN-001 | `tests/login/test_login.py::TestLogin::test_login_success` | 登录成功 |
| UI-BASE-LOGIN-002 | `tests/login/test_login.py::TestLogin::test_portal_homepage_accessible` | 门户首页可访问 |
| UI-BASE-CONSOLE-001 | `tests/console/test_console_navigation.py::TestConsoleNavigation::test_console_home_accessible` | 控制台首页可访问 |
| UI-BASE-DOCCENTER-001 | `tests/doccenter/test_doc_center.py::TestDocCenter::test_doc_center_accessible` | 文档中心可访问 |
| UI-BASE-DOCCENTER-002 | `tests/doccenter/test_doc_center.py::TestDocCenter::test_workspace_visible` | 工作区可见 |

## 6. 自动化落地状态

第一批已落地测试：

| 覆盖范围 | 测试路径 | PROD 验证 |
| --- | --- | --- |
| `C-P0-PORTAL-001` 到 `C-P0-PORTAL-006` | `tests/portal/test_portal_p0_readonly_regression.py` | `2026-08-11 python run_tests.py --env prod --refresh-auth -p portal -m "smoke and readonly" -v: 6 passed` |
| `C-P0-CONSOLE-001` 到 `C-P0-CONSOLE-013` | `tests/console/test_console_p0_readonly_regression.py` | `2026-08-11 python run_tests.py --env prod -p console -k "p0_readonly" -m "smoke and readonly" -v: 13 passed` |
| PROD 默认集合 | `tests` | `2026-08-11 python run_tests.py --env prod -m "smoke and readonly" -v: 24 passed, 8 deselected` |

第一批实现保持窄范围：

1. 先扩展门户只读导航：`C-P0-PORTAL-001` 到 `C-P0-PORTAL-006`，暂不包含 `C-P0-PENDING-001`。
2. 再扩展控制台菜单组健康检查：`C-P0-CONSOLE-001` 到 `C-P0-CONSOLE-012`，以菜单可见和安全搜索框交互为主。
3. 最后补一个独立二级页面样例：`C-P0-CONSOLE-013`，验证控制台内真实路由页面能打开。
4. `C-P0-PENDING-001` 和 `C-P0-PENDING-002` 先保留探查记录，不进入 pytest 和 registry。

已落地用例统一标记为 `smoke + readonly + regression`，模块 marker 按入口分别使用 `portal` 和 `console`。进入 `test_assets/registry/ui_case_assets.yaml` 的资产以分组形式登记，避免为参数化用例重复登记大量相同治理信息。
