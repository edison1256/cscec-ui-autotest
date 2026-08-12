# UI 自动化适配规则

## 输入

只消费 `test-case-generator` 生成的结构化用例数据：

- `详细测试用例数据.json`
- 顶层可以是 `{"cases": [...]}` 或直接是用例数组
- 字段沿用原生成器：`所属模块`、`标题`、`类型`、`优先级`、`前置条件`、`步骤`、`预期结果`、`所涉及到的数据`

## 输出

输出 UI 自动化资产候选清单，不生成 Playwright 代码：

- `asset_id`
- `source_case`
- `module`
- `title`
- `automation.status`
- `automation.suggested_markers`
- `automation.env_policy`
- `automation.reason`
- `promotion.lifecycle`

## 状态流转

- `new_requirement`: 新需求黑盒测试阶段
- `candidate`: 适合进入 UI 自动化候选池
- `uat_automated`: 已在 UAT 自动化验证
- `pre_verified`: 已在 PRE 验证通过
- `prod_regression`: 上线后沉淀为生产回归
- `manual_only`: 不适合 UI 自动化，保留手工
- `api_preferred`: 更适合接口或数据校验
- `deprecated`: 需求废弃、页面下线或不再适用

## 准入原则

- 优先自动化稳定、可重复、价值高的主路径和高频回归路径。
- 包含点击、输入、选择、搜索、查看、打开、进入等前端交互的功能/UI/权限/回归用例可进入候选。
- 写入类用例可以进入 UAT/PRE 自动化，但默认不进入 PROD 默认执行集合。
- 删除、撤回、审批流转、终止、下架、停用等破坏性用例必须标记 `destructive`。
- 接口字段兼容、批量数据校验、性能、安全渗透、复杂并发优先标记为 `api_preferred` 或 `manual_only`。
- 生产默认执行仅允许 `smoke + readonly`。

## Marker 建议

- `readonly`: 不产生业务写入或状态变更
- `write`: 新增、保存、上传、提交、编辑等写入动作
- `destructive`: 删除、撤回、审批流转、终止、下架、停用等高风险动作
- `smoke`: 稳定核心只读路径
- `regression`: 历史功能回归或新需求上线后沉淀资产
- 模块 marker: `login`、`console`、`doccenter`、`ops` 等

## 生产沉淀规则

新需求迭代中的 UI 自动化候选用例，必须满足以下条件后才进入 `prod_regression`：

- UAT 自动化通过
- PRE 自动化或人工复核通过
- 已上线且页面入口、数据条件稳定
- 风险等级与执行环境标记明确
- PROD 下默认只读；写入/破坏性用例必须显式指定 marker/path 执行
