# 中建云 UI 自动化测试

基于 `pytest`、`pytest-playwright` 和 Page Object 的 UI 自动化工程。当前阶段只迁移和稳定现有登录、控制台、文档中心、运维巡检用例，不新增业务场景。

## 工程结构

```text
cscec-ui-autotest/
├── config/
│   ├── environments.py      # uat/pre/prod URL
│   └── settings.py          # 运行配置、账号、环境密码、登录态路径
├── core/
│   ├── base_page.py         # Page Object helper 组合入口
│   ├── navigation.py        # 导航与等待
│   ├── elements.py          # 候选定位、点击、上传、截图
│   ├── assertions.py        # 页面断言
│   ├── antd.py              # Ant Design 表单、表格、弹窗、消息
│   └── locator_strategy.py  # 多候选定位策略
├── pages/                   # Page Object
├── tests/                   # pytest 用例与模块 fixtures
├── test_assets/             # UI 自动化资产池与生命周期登记
├── tools/                   # 用例适配、资产校验等辅助工具
├── auth_states/             # 按环境保存登录态，运行时生成
├── run_tests.py             # 项目运行入口
├── pytest.ini
└── requirements.txt
```

## 环境配置

`.env` 中按环境维护密码：

```dotenv
ENV=uat
USERNAME=20431644
PASSWORD=Infoshare1!
UAT_PASSWORD=Infoshare1!
PRE_PASSWORD=Infoshare1!
PROD_PASSWORD=Infoshare1!!
HEADLESS=true
BROWSER_CHANNEL=chrome
```

运行时根据 `ENV` 自动选择密码：

| ENV | 使用密码 |
| --- | --- |
| `uat` | `UAT_PASSWORD`，当前为 `Infoshare1!` |
| `pre` | `PRE_PASSWORD`，当前为 `Infoshare1!` |
| `prod` | `PROD_PASSWORD`，当前为 `Infoshare1!!` |

`PASSWORD` 只作为兜底兼容配置，不作为优先密码来源。

## 登录态

登录态按环境隔离保存：

```text
auth_states/uat.json
auth_states/pre.json
auth_states/prod.json
```

需要刷新登录态时显式加 `--refresh-auth`：

```powershell
python run_tests.py --env uat --refresh-auth -m smoke
```

如果用例需要登录态，但对应环境的登录态不存在或已失效，非交互执行会直接退出并提示刷新命令。

## 运行规则

生产环境默认保护规则：

- `python run_tests.py --env prod` 默认只跑 `smoke and readonly`。
- `python run_tests.py --env prod --dry-run` 只收集 `smoke and readonly`。
- 如果显式传入 `-m`、`-p` 或 `-k`，按用户指定执行，不额外阻断写操作。

UAT/PRE 不限制写入类用例：

```powershell
python run_tests.py --env uat -m smoke
python run_tests.py --env pre -m regression
python run_tests.py --env uat -m write
```

常用命令：

```powershell
python -m pytest --collect-only
python run_tests.py --env uat --dry-run
python run_tests.py --env prod --dry-run
python run_tests.py --env uat --refresh-auth -m smoke
python run_tests.py --env prod -m "write or destructive"
```

## Marker 规范

| Marker | 含义 |
| --- | --- |
| `readonly` | 只读，不产生业务写入或状态变更 |
| `write` | 新增、保存、上传、提交等写入动作 |
| `destructive` | 删除、撤回、审批流转等不可轻易恢复的动作 |
| `smoke` | 核心冒烟验证 |
| `regression` | 回归验证 |
| `e2e` | 端到端流程 |
| `login` | 登录模块 |
| `console` | 控制台模块 |
| `doccenter` | 文档中心模块 |
| `ops` | 运维巡检模块 |

写入用例必须显式标记 `write` 或 `destructive`。生产默认只会收集同时具备 `smoke` 和 `readonly` 的用例。

## Page Object 写法

`BasePage` 不再承载大而全的旧方法。页面对象通过 helper 调用基础能力：

```python
self.nav.goto_url(settings.BASE_URL)
self.elements.click_candidates([("text", "控制台")], description="控制台入口")
self.assertions.any_text_visible(["控制台", "工作台"])
self.antd.click_save_button()
```

新增页面对象时优先复用 `nav`、`elements`、`assertions`、`antd`，不要把业务无关的通用能力重新塞回 `BasePage`。

## 当前用例范围

- 登录：成功登录、门户首页可访问、登出、异常登录。
- 控制台：首页可访问、服务供给入口。
- 文档中心：页面可访问、工作台可见、我的文档导航。
- 运维巡检：巡检页面可访问、巡检保存流程。

当前核心 smoke 只包含稳定只读路径：登录成功、门户首页可访问、控制台入口页、文档中心入口、文档中心工作台。服务供给二级页、我的文档、运维巡检入口和巡检保存保留在 regression 范围，其中巡检保存流程为 `write + regression`，不属于只读 smoke。

## 阶段2资产流转

原始 `D:\AI\LM\.agents\skills\test-case-generator` 不在本工程内修改。工程内的 `tools/test-case-generator-ui-adapter` 是它的副本和适配层，只消费 `详细测试用例数据.json`，用于筛选 UI 自动化候选资产。

生成候选清单：

```powershell
.\.venv\Scripts\python.exe .\tools\test-case-generator-ui-adapter\scripts\select_ui_assets.py --input "D:\AI\LM\...\详细测试用例数据.json" --output ".\test_assets\incoming\<需求名>.ui-assets.yaml" --requirement "<需求名>"
```

校验资产登记：

```powershell
.\.venv\Scripts\python.exe .\tools\validate_ui_assets.py --registry .\test_assets\registry\ui_case_assets.yaml
```

资产登记文件：

- `test_assets/registry/ui_case_assets.yaml`：当前已自动化、候选、待稳定和写入类资产。
- `test_assets/incoming/`：新需求黑盒用例转换出的候选清单。
- `test_assets/schema/ui-case-asset.schema.json`：资产字段约束。

## 清理策略

可直接清理的运行产物：

```text
debug/
logs/
reports/
screenshots/
.pytest_cache/
__pycache__/
auth_state.json
```

`.env`、`.venv`、源码和测试数据不是绝对保留项，但删除前必须先用 `rg` 查引用，确认属于旧结构、脏数据或可再生成文件。
