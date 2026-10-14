# 计量订阅 260901：执行与结果边界

本套件仅限 PRE。它按原始 XMind 编号收集 194 项，其中包含待角色、待数据、未实现及本轮范围外项；收集数量不代表自动化通过或完整覆盖。M11.1–M11.3 的代表性检查不能替代整个小节回归。

资产登记为 `new_requirement / candidate`，不纳入 UAT 或生产发布门禁。直接在其他环境运行时，在任何浏览器登录之前跳过。

2026-10-13 黑盒实测通过项的独立回放见 [黑盒自动化接入](metering-subscription-260901-blackbox-automation.md)。该套件使用本轮数据一致性断言，需单独选择 `metering_subscription_260901/verified`；不要把原有占位用例的收集或跳过算作自动化通过。

## 执行

在工程根目录使用现有虚拟环境，先确认 PRE 账号和环境配置。不要将账号密码写入测试或大纲。

```powershell
python run_tests.py --env pre --headless -m metering_subscription_260901
```

默认结果文件为 `reports/metering260901/results.json`。需要为 CI 作业指定独立文件时，可直接运行 pytest（确保当前进程 `ENV=pre`）：

```powershell
$env:ENV = 'pre'
$env:HEADLESS = 'true'
python -m pytest tests/metering_subscription_260901 --metering-results reports/metering260901/job-results.json
```

结果只记录本轮实际选择并执行的用例，不合并历史记录；包含 setup、call、teardown 阶段，支持 F12 和并行执行。收集检查不重写结果。只跑部分用例时，大纲中其余项显示未执行，不沿用旧的通过结果。认证失败记录为 setup 失败，不等于已完成业务断言。

## 失败与跳过

- `ENTRY_MISSING`：实时发现的大纲要求缺失，执行失败并留待产品/开发复核，不软化为通过或条件跳过。
- `ROLE_REQUIRED`：缺少明确权限或多账号对照，不据此判断权限功能正常。
- `DATA_REQUIRED`：缺少固定额度、非零计量、不同订单状态等可对照数据，不使用不限量、零调用或表头文字替代验证。
- `PENDING_IMPLEMENTATION`：可以自动化，但行为断言尚未实现；导出下载不属于天然不可自动化。
- `ENV_LIMITED`：环境故障待复核，不能算业务验证通过。
- `OUT_OF_SCOPE`：本轮范围外，不等于永久不可自动化。

已加强断言只匹配真实表格和数据行；控制台字段顺序按原始大纲检查。已识别的固定额度、累计计量、消息预警、角色隔离、收起用量、弹窗标题及遮挡测试不再用无关页面文字判通过。

仍需 PRE 复核：实际表格结构、账号角色、历史锚点是否有效、个人列表与租户聚合视图的产品口径，以及依赖调用/审批/履约流程的待验证项。这些不应仅凭静态代码审查定性为业务缺陷。

## 独立生成大纲

```powershell
python tools/generate_metering_outline_260901.py --source "D:/Doc/一体化/用例/计量订阅260901测试大纲.xmind" --output "D:/Doc/一体化/用例/计量订阅260901自动化测试大纲.xmind"
```

用 `--results` 指定其他本轮结果文件。没有结果文件时全部标注为未执行。旧版混合结果被拒绝，需重新执行后生成。汇总分别统计通过、失败、跳过和未执行，不将跳过计入通过。

生成器保留全部工作表、批注子节点、样式、关系、图片及已有备注，移除失效的旧缩略图。拒绝输出到原文件（包括同路径或硬链接），原文件只读；输出已有文件会先备份，再原子替换。
