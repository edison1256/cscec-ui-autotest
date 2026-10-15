# 计量订阅生产上线回归

本入口为 2026-10-15 计划上线的计量订阅准备。确认生产部署完成后才执行真实回归；准备阶段执行收集校验和 PRE 预演。代码可运行不代表生产需求已上线或已验证通过。

## 执行范围

- 计量专项：38 个只读流程，映射原大纲 61 项，包含工作台/控制台/本人视图、父子表、订单、用量、日明细、分页、普通订阅及交付方式的已实现流程。
- 3 项仍待确认/待数据：M7.1.2 列顺序契约、M4.3.4 严格跨用户反例、M6.2.3 独立确认的不限量规格。不会因为允许生产而取消跳过。
- 2026-10-15 已确认正式字段采用 PRE 当前名称：M2.1.2 为“资源发布方”，M5.2.1 为“订阅人所在租户”。本轮按此精确断言，原大纲及历史失败记录不改写。
- 原有 4 项限定范围说明仍有效，见 [已验证黑盒覆盖说明](metering-subscription-260901-blackbox-automation.md)。
- 重复 CSV 导出 M12.2.3 会创建异步任务，属于 write；生产只读套件不收集，即使传入 `--metering-allow-export` 也不能在生产运行它。
- 原大纲 194 项不等于已有 194 项完整自动化。未验证的旧脚本仍只允许 PRE，不整体解禁到生产。

本套件是上线后的显式专项回归，不自动晋级为固定发布门禁。原有默认生产 115 条、严格控制台 44 条及条件控制台 69 条保持原选择规则。

## 上线前准备

### 门户初始化查询依据

2026-10-15 的 PRE 严格预演曾拦截工作台首页的社区组件接口。对已有 Trace 记录的静态脚本进行只读检查：

- `/udpweb/portal/3862.ba1caf85.async.js` 的模块 13409 导出 `qe`，根据控制台/工作台布尔值选择 `postPortalConsole` 或 `postPortalWorkbench`，请求不提交帖子内容。
- `/udpweb/portal/pages/homePage-irpWorkbench.8104a31c.async.js` 调用 `W.qe(ze)` 后，将返回值 `data.configList`、`postHotList`、`groupList`、`postTitleUrl` 等用于横幅和开发者社区列表展示。
- 控制台失败取证的 `auth/irp-pre.cscec.com-cs-assets.json` 证实实际加载的是同一首页组件。对控制台来源脚本复核：`ze=Oe.field===p.GJ.control`，`W.qe(ze)` 的响应随后按 `ze ? AD_CONSOLE : AD_WORKBENCH` 和 `MESSAGE_CONSOLE/MESSAGE_WORKBENCH` 选择展示配置，再将 `postHotList`、`groupList` 交给社区组件；控制台分支也不提交帖子或配置保存内容。
- 同一 API 模块的 `CO` 导出调用 `/irp-api/irp-portal-public/knowledge-center/queryNoAuth`，首页调用后将 `data` 数组交给知识组件。
- 控制台实际观察到同一知识组件经命名空间转换请求 `/irp-api/irp-portal-console/knowledge-center/queryNoAuth`，同样只放行这个完整查询路径。
- 控制台实际文档 `/udpweb/portal/index.html` 引用的 `umi.455f5846.js` 中，`getSystemName` 只提交 `domainName`、`secondPath`；对应 effect 把响应 `data` 交给 `setSystemName`，用于显示系统名称，不保存系统配置。
- `/irp-api/irp-portal-console/link/checkNoAuth` 的静态证据不足时曾保持拦截；2026-10-15 用户确认该接口不写数据后，仅将这个完整路径纳入允许清单。
- 门户 `static/js/index.2db80470.js` 的 `getUserData` POST `/basedata/api/tenant/getUserJobByUserCodeAndDataSource`，只传 `userNos`、`dataSource`；返回 `orgName`、`orgNo` 数组用于账号信息及租户选择器。`/portal/login/changeOrgByNo` 单独归为切换登录身份的认证动作，不允许同类租户保存接口。
- 同一门户脚本的 `getViewBatch` 用租户编号数组查询 `/irp-api/irp-portal-public/tenant/viewBatch`，返回 `tenantNo`、`mainDataName` 用于填充租户选择器显示名。
- 组件实际加载的 `business/resource/3618712f-async.e850db0c.js` 和 `framework_0.1545935f.js` 用 `menuCode`、`bizCode` POST `/engine/metadata/getMenuPageName`，将返回字符串数组作为 `pageRightNameList` 查询 `/auth/resolve/getNoGrantButtons`；响应仅用于隐藏/禁用按钮显示。

`/udp-monitor/logging` 与 `/integration-portal/recentUseMenu/useMenu` 属于菜单访问日志/最近使用记录，仍阻断，不放行写入；它们与共享 tracker 一样作为可选跟踪抑制，不当成计量业务失败。

因此这里的 post 指社区帖子，调用用途是读取首页展示配置/列表。允许清单只增加已核实的完整工作台/控制台路径，不放行同命名空间下的保存、发布或任意 POST。上述静态资源是本次构建的核验依据，不代表未来任意同名接口都自动批准。

只收集用例，不启动浏览器、不登录生产：

```powershell
python run_tests.py --env prod --prod-suite metering --dry-run --keep-allure-results
```

预期选择 38/39 个流程，1 个导出流程被排除。待数据/契约项仍会被收集，但执行时明确跳过。在 PRE 演练相同的只读请求策略：

```powershell
python run_tests.py --env pre --headless -p metering_subscription_260901/verified -k "wb_entry or cs_entry or personal_default" --tracing on --keep-allure-results --pytest-args --metering-readonly-preflight --metering-results reports/metering260901/preflight-prod.json
```

生产身份使用 `USERNAME` 和 `PROD_PASSWORD`，不会回退到 PRE/UAT 密码。默认沿用已声明账号/显示名/租户画像，页面仍需实际验证身份和所选租户；不同账号或租户通过 `--metering-profile` 指定非敏感 JSON。模板为 `test_assets/metering_subscription_260901/prod_profile.example.json`，其中的角色不是本次生产复核结果。

生产查询资源默认从当前响应选取，不要求存在 PRE 的 WPS 服务组件。PRE 的个人订阅和资源目录直链带菜单编号，生产不会自动继承。优先从当前生产页面的真实链接发现；找不到唯一链接时，需在生产画像中填写 `personal_subscription_path` / `resource_catalog_path`，内容必须来自生产实际菜单。不能把 PRE 域名替换后直接复用编号。缺少入口证据的流程标为 ROLE_REQUIRED。

## 确认部署完成后执行

先执行原有完整基础发布回归：

```powershell
python run_tests.py --env prod --headless --keep-allure-results
```

首次上线可先选择本次已在 PRE 定向复核的六个入口/字段流程：

```powershell
python run_tests.py --env prod --prod-suite metering --headless -k "wb_entry or cs_entry or wb_component or cs_component or wb_columns or wb_order_columns" --keep-allure-results
```

再执行完整计量只读专项；首批通过不能替代完整专项结果：

```powershell
python run_tests.py --env prod --prod-suite metering --headless --html-path reports/metering260901/prod-report.html --keep-allure-results
```

有生产画像时，在命令最后附加：

```text
--pytest-args --metering-profile <生产画像JSON路径>
```

保持串行执行，首次上线排查不启用自动重跑。专项命令自动选择审查过的 verified 路径、排除 write/destructive、传入生产已部署确认标记，并默认开启 `retain-on-failure`。单独传 `--env prod` 或把旧计量目录直接换成 prod 不会解禁旧脚本。UAT 继续在登录前跳过。

## 只读与结果口径

生产请求限制在 `cloud.cscec.com` / `irp.cscec.com`；共享 IAM 仅用于认证，不能借认证域访问 PRE/UAT 业务 API。计量命名空间仅允许已观察的聚合、列表、账户、订单及用量查询动作；其他 POST 仅放行显式查询动作，未知写操作和导出任务被拦截。合法初始化查询若未在允许清单中，会保守失败；应先复核接口语义再扩充清单。

总数、父子关系、额度、日期、订单 ID、分页均使用本轮生产数据。连续展开只比较账户/接口身份，各次展示分别与当次响应核对，避免用 PRE 历史数量或把正常用量变化当作重复展开缺陷。跨多次请求的累计/日明细对账仍可能受生产实时增长影响，发生差异需结合 Trace 核对统计时点，不能直接确认业务 bug。

失败、ROLE_REQUIRED、DATA_REQUIRED、契约待复核及尚未执行分别报告。退出码 0 不表示所有大纲项通过，必须核对 skipped 和限定范围；生产无正向样本时不能以空页面通过代替。

## 失败证据

当前生产结果单独写入 `reports/metering260901/prod-results.json`，每轮另存 `runs/<run_id>/results.json`。不复用 PRE 通过记录。页面证据和各域 Trace 写入唯一 `blackbox-<时间>-<随机标识>/<worker>/<scenario>/`。

自建业务上下文显式录制 Trace；日常成功后删除，setup/call/teardown 任一阶段失败保留已录制文件。认证上下文仍保存失败截图/文本，不宣称已录制登录 Trace。JSON 结果中的 `metering_traces` 指向实际文件，`metering_trace_errors` 记录录制异常。只收集或登录前跳过不会产生 Trace。

专项排障可在运行命令追加 `--tracing on`，保留成功与失败记录。关闭浏览器前保存 Trace，避免只加 pytest 参数但自建上下文未被录制。查看文件：

```powershell
python -m playwright show-trace <实际的wb-trace.zip或cs-trace.zip路径>
```

Trace 与断言日志、截图、业务响应联合复核。证据仅留本地/流水线制品，不提交 reports、认证状态或密码；按已有制品保留周期清理，避免长期累积。

## 2026-10-15 准备验证快照

- 本地工具回归 327 项通过；资产登记有效，既有生产控制台契约 44 严格 + 69 条件不变。UAT 只做收集检查，没有登录或执行本次业务。
- 生产专项只收集 38/39 流程，排除 1 个导出流程；默认生产仍收集 115 条。尚未执行生产业务，不能据此判断上线成功。
- PRE 大批次 `f4bf6909a8a849df8bfe303498623f80` 在初始化/详情等待失败后主动中断，退出状态 -1。记录 28 个流程：12 通过、13 失败、2 跳过、1 仅记录 setup；另 10 个没有记录。该批次不是完整回归，不能对外声称 38 项已执行完毕。
- 修正已核实的元数据/权限查询拦截后，PRE 定向复核 `wb_entry`、`cs_entry`、`wb_component`、`cs_component`、`wb_columns`、`wb_order_columns`：6 项全部通过。结果为 `reports/metering260901/pre-prod-focused-20261015.json`，使用生产相同只读策略。
- 大批次待复核：同一账户累计用量 6854、接口汇总 8，UI 各自与当次响应一致，但两层合计不一致；需核对统计窗口/账户归属，不能直接定性为业务 bug。订单详情的订单编码输入框为空，以及白屏、菜单/登录等待超时另行报告，不通过修改预期、忽略错误或自动重跑掩盖。

大批次证据保留在 `reports/metering260901/blackbox-20261015-135005-a942dc2b/`，结果为 `pre-prod-readonly-20261015.json`；成功的定向复核不会覆盖该批次。生产普通用户租户/菜单直链仍须以真实生产页面或生产画像确认。
