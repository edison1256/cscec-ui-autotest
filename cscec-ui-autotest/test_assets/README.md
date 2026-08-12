# UI 自动化资产流转

本目录用于承接 `test-case-generator` 产出的黑盒测试用例，并管理其进入 UI 自动化、UAT/PRE 验证、上线后沉淀为生产回归的生命周期。

## 目录

```text
test_assets/
├── incoming/                 # 从详细测试用例数据.json 生成的候选清单
├── registry/
│   └── ui_case_assets.yaml   # 已登记的 UI 自动化资产
└── schema/
    └── ui-case-asset.schema.json
```

## 流转

1. 新需求测试阶段，继续使用原始 `test-case-generator` 生成黑盒用例。
2. 将 `详细测试用例数据.json` 放入临时位置或直接指定路径，运行适配器脚本生成候选清单：

```powershell
.\.venv\Scripts\python.exe .\tools\test-case-generator-ui-adapter\scripts\select_ui_assets.py --input "D:\AI\LM\...\详细测试用例数据.json" --output ".\test_assets\incoming\<需求名>.ui-assets.yaml" --requirement "<需求名>"
```

3. 人工评审候选清单，确认哪些进入 UI 自动化。
4. 自动化落地后，在 `registry/ui_case_assets.yaml` 登记测试路径、marker、环境策略和验证证据。
5. UAT 通过后状态可变更为 `uat_automated`；PRE 通过后变更为 `pre_verified`；上线后稳定只读路径可沉淀为 `prod_regression`。

## 生产规则

- PROD 默认只执行 `smoke + readonly`。
- 写入或破坏性用例只允许显式 marker/path 执行。
- 新需求上线后沉淀为生产回归前，必须有 UAT/PRE 验证证据。
