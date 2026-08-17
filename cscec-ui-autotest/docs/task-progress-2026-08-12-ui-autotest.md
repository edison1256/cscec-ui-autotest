# UI 自动化阶段进度快照（已过期）

> ⚠️ **本文件已过期，请勿作为当前状态依据。** 文中的「prod 24/52 selected、36 assets」已不再是现状。
> 当前准确状态由自动生成文档 **`docs/PROJECT_STATUS.md`** 维护（由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 派生）。
> 记录时间：2026-08-12（快照保留作历史参考）。

## 当前阶段

阶段 2/3 的数据资源导入自动化已完成到 A6。

## 已完成自动化资产

- M02 入口/模板合同：`UI-CAND-0001`、`UI-CAND-0068`
- M03/M04 入口/模板合同：`UI-CAND-0002`、`UI-CAND-0003`、`UI-CAND-0069`
- M03 列名不符：`UI-CAND-0006`
- M03 单行业务错误：`UI-CAND-0030`、`UI-CAND-0031`、`UI-CAND-0032`、`UI-CAND-0033`、`UI-CAND-0034`
- M04 单行业务错误：`UI-CAND-0045`、`UI-CAND-0046`、`UI-CAND-0047`、`UI-CAND-0048`、`UI-CAND-0049`、`UI-CAND-0050`
- M04 正向导入前校验：`UI-CAND-0051`、`UI-CAND-0053`
- M04 当前待稳定：`UI-CAND-0052`
- M03 正向导入前校验/未提前写入：`UI-CAND-0005`、`UI-CAND-0009`
- M03 多行错误/错误后重传：`UI-CAND-0007`、`UI-CAND-0008`

## 最近验证结果

- `python run_tests.py --env uat -p dataresources -v --no-html`：`20 passed, 1 xfailed`
- `python run_tests.py --env uat -p dataresources -k "m03_valid_xlsx" -v --no-html`：`1 passed`
- `python run_tests.py --env uat -p dataresources -k "A3PositiveContracts or A5PreImportContracts" -v --no-html`：`3 passed, 1 xfailed`
- `python run_tests.py --env uat -p dataresources -k "A6DialogState" -v --no-html`：`2 passed`
- `python -m pytest --collect-only`：`52 tests collected`
- `python run_tests.py --env uat --dry-run -p dataresources`：`21 tests collected`
- `python run_tests.py --env prod --dry-run`：默认仍只收集 `smoke and readonly`，`24/52 selected`
- `python tools/validate_ui_assets.py`：`Registry valid`，`Assets: 36`

## 当前约束

- 本 UI 自动化工程保持纯 UI 验证，不通过 API/DB 断言数据规则。
- UAT/PRE 可执行写入、上传、校验类用例；PROD 默认只跑 `smoke and readonly`。
- 数据资源导入类用例当前不点击最终“导入”，除非后续单独确认专项数据和回收策略。
- A5 新增 M03 正向 xlsx 仅校验到“校验通过/导入按钮可用”，关闭弹窗后前端搜索唯一表英文名为空，证明点击最终“导入”前未提前写入。
- A6 新增 M03 多行错误和错误后重传正确文件；只验证弹窗错误/通过态和前端搜索空态，不点击最终“导入”。
- 原始 `D:\AI\LM\.agents\skills\test-case-generator` 不修改。

## 临时任务

插入手工黑盒用例覆盖对比任务：

- 输入：`C:\Users\CFD\Desktop\数据资源导入功能优化以及性能优化V2.xmind`
- 目标：对比手工黑盒用例覆盖范围与当前已自动化覆盖，识别可不执行的手工用例、仍需手工验证的用例、以及可作为后续自动化候选的用例。
