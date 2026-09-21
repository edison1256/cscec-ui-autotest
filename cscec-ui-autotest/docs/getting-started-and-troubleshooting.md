# 快速开始与失败排查

本文面向第一次接触本工程的执行人员和开发人员。所有命令都在 `D:\Automation\cscec-ui-autotest` 下运行。

## 1. 开始前确认

准备以下环境：

- Windows PowerShell。
- Python 3.12。
- Google Chrome。
- 可以访问对应的中建云 UAT、PRE 或 PROD 网络。
- 有效的测试账号及各环境密码。

生产环境默认套件只执行只读用例。不要用生产环境作为新人的首次调试环境，也不要在未明确授权时执行 `write`、`destructive` 或 `controlled-write` 用例。

## 2. 首次安装

```powershell
cd D:\Automation\cscec-ui-autotest

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chrome
```

如果 PowerShell 禁止激活脚本，不必修改系统策略，可以直接使用 `.\.venv\Scripts\python.exe` 执行后续命令。

复制环境配置模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少确认以下配置：

```dotenv
ENV=uat
USERNAME=<账号>
UAT_PASSWORD=<UAT 密码>
PRE_PASSWORD=<PRE 密码>
PROD_PASSWORD=<PROD 密码>
HEADLESS=true
BROWSER_CHANNEL=chrome
```

`.env`、`auth_states/`、`logs/`、`reports/` 和 `screenshots/` 都是本地文件或运行产物，禁止提交到 Git。

## 3. 第一次运行

先做静态收集，确认依赖、Python 导入和用例结构正常：

```powershell
.\.venv\Scripts\python.exe run_tests.py --env uat --dry-run
```

该命令只收集用例，不打开业务页面。当前基线应收集 513 条；数量会随新增用例变化，应同时参考 `docs/PROJECT_STATUS.md`。

首次执行需要生成独立的 UAT 登录态：

```powershell
.\.venv\Scripts\python.exe run_tests.py --env uat --refresh-auth -m smoke
```

登录成功后会生成 `auth_states/uat.json`。后续运行会复用它：

```powershell
.\.venv\Scripts\python.exe run_tests.py --env uat -m smoke
```

PRE 和 PROD 分别使用 `auth_states/pre.json` 与 `auth_states/prod.json`，登录态不能跨环境复用。

## 4. 常用运行命令

```powershell
# 查看全部参数
.\.venv\Scripts\python.exe run_tests.py --help

# 按模块目录运行
.\.venv\Scripts\python.exe run_tests.py --env uat -p console

# 按 pytest marker 运行
.\.venv\Scripts\python.exe run_tests.py --env uat -m "smoke and readonly"

# 按测试名称关键字运行
.\.venv\Scripts\python.exe run_tests.py --env uat -k "ticket"

# 打开浏览器，便于观察定向失败
.\.venv\Scripts\python.exe run_tests.py --env uat --headed -k "完整或部分测试名称"
```

`-p`、`-m` 和 `-k` 可以组合缩小范围。排查时优先定向运行单个失败用例，不要一开始反复运行全套。

## 5. 生产环境运行

```powershell
# 当前 115 条 PC + 移动端只读发布走查
.\.venv\Scripts\python.exe run_tests.py --env prod

# 44 条控制台严格 Mandatory 门禁
.\.venv\Scripts\python.exe run_tests.py --env prod --prod-suite mandatory

# 69 条依赖业务前置条件的 Conditional 用例
.\.venv\Scripts\python.exe run_tests.py --env prod --prod-suite conditional
```

首次运行或登录态失效时，先定向刷新：

```powershell
.\.venv\Scripts\python.exe run_tests.py --env prod --refresh-auth -p tests/login/test_login.py
```

生产默认套件当前为 115 条，但不是固定上限。以实际收集结果、`docs/PROJECT_STATUS.md` 和生产发布走查文档为准。

## 6. 先看哪些结果

每次执行后按以下顺序查看：

1. 终端末尾的 `passed`、`failed`、`skipped` 和环境汇总。
2. `reports/report.html`：自包含 HTML 报告，可直接用浏览器打开。
3. `logs/pytest.log`：完整调试日志，先搜索第一个 `FAILED` 或异常堆栈。
4. `screenshots/FAIL_*.png`：测试正文失败时自动保存的全页截图。
5. `reports/prod-console-contract-summary.json`：生产控制台责任套件的分类统计。

使用 `--report` 时，只有测试通过后才会调用本机 Allure 命令生成 `reports/allure-report/`。日常排查直接使用 HTML 报告即可，不要求安装 Allure CLI。

## 7. 失败排查流程

### 7.1 先排除连锁失败

从执行顺序中最早出现的失败开始。登录、浏览器退出、公共导航失败经常会让后续多个用例一起失败，后面的报错可能只是结果，不是根因。

用测试名称定向复现，并显示浏览器：

```powershell
.\.venv\Scripts\python.exe run_tests.py --env uat --headed -k "失败测试名称"
```

不要先使用 `--reruns` 掩盖问题。确认属于偶发网络或页面加载波动后，才可用 `--reruns 1` 辅助判断稳定性。

### 7.2 按现象分类

| 现象 | 常见原因 | 首要检查 |
| --- | --- | --- |
| 提示 auth state missing or stale | 登录态不存在、过期或环境不匹配 | 使用对应环境的 `--refresh-auth` |
| 跳到 IAM/CAS 登录页 | 登录态失效或跨域认证失败 | 当前 URL、`auth_states/<env>.json`、接口业务码 |
| 找不到按钮、输入框或文本 | 页面改版、权限差异、定位范围错误 | 失败截图和有界面定向复现 |
| 页面已打开但断言对象不一致 | 测试数据变化、接口与 UI 渲染不一致 | 日志里的动态 ID/编码及页面可见对象 |
| HTTP 404/5xx 或业务码失败 | 部署、网关、权限或后端业务异常 | 请求 URL、状态码、响应业务码和错误消息 |
| `pageerror`、`console.error`、白屏 | 前端运行时或资源加载问题 | 浏览器错误、失败截图、关键网络响应 |
| `NOT_APPLICABLE` | Conditional 用例缺少已登记的业务前置条件 | 终端中的 Case ID 和前置条件说明 |
| `SKIPPED` | 测试主动跳过，不一定等于条件不适用 | pytest skip 原因；不要与 `NOT_APPLICABLE` 混淆 |
| 本地通过、整套失败 | 共享状态、执行顺序、数据竞争或资源压力 | 最早失败、前一用例残留、并行设置 |

`NOT_APPLICABLE` 不是通过，也不是产品失败。它只允许出现在已登记的 Conditional 前置条件不满足场景；Mandatory 用例不允许用它规避失败。

### 7.3 判断是测试问题还是产品问题

更可能是测试代码问题：

- 页面实际正常，但定位器未命中可见控件。
- 用例固定依赖已经变化的生产记录、ID 或 URL。
- 单独运行稳定通过，且整套执行前一用例遗留了页面或弹窗状态。
- 断言与页面当前真实语义不一致。

更可能是环境或产品问题：

- 页面可稳定复现白屏、关键区域缺失或前端异常。
- 关键接口返回 404/5xx 或 HTTP 200 但业务码失败。
- 接口返回的当前对象和页面展示对象稳定不一致。
- 干净登录态和单用例定向复跑仍稳定失败。

不要通过增加固定等待、放宽所有网络错误、硬编码生产记录或无条件跳过来让失败变绿。应保留截图、日志、请求地址、业务码、动态对象身份和复现命令。

## 8. 常见安装问题

### 找不到 Python 或版本不符

```powershell
python --version
.\.venv\Scripts\python.exe --version
```

工程 CI 使用 Python 3.12，新环境优先保持一致。

### Chrome 启动失败

确认 `.env` 中 `BROWSER_CHANNEL=chrome`，本机已安装 Chrome，并重新安装 Playwright 对应浏览器支持：

```powershell
.\.venv\Scripts\python.exe -m playwright install chrome
```

### 依赖导入失败

确认当前使用的是项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_tests.py --env uat --dry-run
```

### 页面加载超时

先确认 VPN/内网、目标域名和账号权限，再用单用例有界面模式观察。不要直接增大所有超时；如果接口持续失败，应按环境或产品问题保留证据。

## 9. 修改用例前

先阅读：

- `AGENTS.md`：生产门禁和 Git 安全规则。
- `docs/ui-asset-governance.md`：用例资产、环境和写入风险分层。
- `docs/prod-release-mandatory-walkthrough-suite.md`：生产发布执行标准。
- `docs/devops-maintenance-guide.md`：校验、提交和双远程同步流程。

本项目是 `D:\Automation` 大仓库中的子目录。所有 Git 操作都必须限定在 `D:\Automation\cscec-ui-autotest`，禁止在父目录执行宽泛暂存或提交。
