# 蓝盾（BK-CI）流水线配置指南 — UI 自动化 Daily Test

> 目标流水线：`https://devops.cscec.com/osc/irp/new-ipipe/pipelines/9784/current`
> 项目：`irp`　代码源：`git@devops.cscec.com:30004/osc/irp/irp-ui-autotest.git`
> 本文只针对流水线 9784，不改动任何其他流水线。

## 0. 背景与关键约束

蓝盾（BK-CI，腾讯蓝鲸持续集成，代号"蓝盾"）与 GitHub Actions 的**执行模型完全不同**：

| 维度 | GitHub Actions | 蓝盾 BK-CI |
| --- | --- | --- |
| 配置载体 | 仓库内 `.github/workflows/*.yml` | **页面可视化编排**，配置存服务端 |
| 生效方式 | 提交文件即生效 | 需在页面保存/启用，代码仓库不携带配置 |
| 执行单元 | Job / Step | Pipeline → Stage → Container(Job) → Element(Task) |
| 构建环境 | `runs-on` 选 runner | Job 的"构建类型"选容器镜像或私有构建机 |

**因此：本工程现有的 `.github/workflows/ci.yml` 对蓝盾无效**，它保留给 GitHub 侧使用。
蓝盾的 daily test 必须在页面上按本文档编排。

同时注意：`tools/sync_project_remotes.ps1` 在生成内网镜像时会**主动删除 `.github/`**，
所以内网仓库里本来就没有 GitHub Actions 配置，这是设计如此，不是缺陷。

## 1. 前置条件（必须先确认）

在执行任何配置前，确认以下三项：

- [ ] **A. 构建机镜像** — Job 的"构建类型"能选到含 Python 3.10+ 的镜像。
      蓝盾官方 `bkci/ci:latest` 基于 Debian/Ubuntu，预置 gcc/make/JDK/Maven 及 Python。
      若页面只提供受限镜像，需先在 Task 里验证 Python 可用性（见第 3 节 Step 1）。
- [ ] **B. 网络出口** — 构建机能访问 `irp-uat.cscec.com` 与 `cloud-uat.cscec.com`。
      用户已确认可达。
- [ ] **C. 环境变量功能** — 流水线变量配置入口可用（用于注入账号密码）。用户已确认存在。

## 2. 需要的流水线变量

在流水线【编辑】→【变量与缓存】/【流水线变量】中新增以下变量。
密码类变量应勾选**「运行时保密」/「密文」**（不同版本叫法不同），避免在日志中明文显示。

| 变量名 | 值 | 说明 |
| --- | --- | --- |
| `ENV` | `uat` | 目标环境 |
| `USERNAME` | （测试账号） | 登录账号，建议按流水线环境配置 |
| `UAT_PASSWORD` | （UAT 密码） | 必须设为密文 |
| `HEADLESS` | `true` | 流水线必须无头运行 |
| `BROWSER_CHANNEL` | `chromium` | **关键**：容器内无 Chrome，必须用 Playwright 自带 Chromium |

> **`BROWSER_CHANNEL` 为什么必须改成 `chromium`**（2026-09-22 实测依据）：
>
> 工程 `settings.py` 默认值是 `chrome`，`tests/conftest.py` 会把它直接传给 Playwright 的
> `channel` 参数。实测三种取值的行为差异：
>
> | 取值 | 实际浏览器版本 | 来源 |
> | --- | --- | --- |
> | 不设 / 空 | 145.0.7632.6 | Playwright 自带 Chromium |
> | `chromium` | 145.0.7632.6 | **与不设完全等价**，用自带 Chromium |
> | `chrome` | 153.0.8010.48 | 系统安装的 Google Chrome |
>
> 本机因装了 Chrome 所以 `chrome` 也能用；**容器镜像通常不含 Chrome**，
> 保持默认值会导致启动失败。设为 `chromium` 后走 Playwright 自带 Chromium，
> 配合 `python -m playwright install chromium` 即可稳定运行。

## 3. 流水线编排（Stage 结构）

建议三个 Stage，串行。任一步失败即中止，避免"用坏环境跑出一堆假失败"。

### 3.0 通用前导片段（每个 Task 都粘贴这段开头）

> **为什么必须加这段**：蓝盾【拉取代码】插件把仓库 checkout 到 workspace 的
> **子目录**（通常是仓库名），而 Task 的初始 CWD 是 workspace 根。
> 所以 `python3 tools/ci_setup.py` 会报 `can't open file 'tools/ci_setup.py'`。
> 下面的片段自动定位工程根，**不需要你知道 checkout 到哪一层**。

```bash
set -e

# ---- 通用前导：定位工程根 + 选择解释器 ----
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "!! 镜像内既无 python3 也无 python，必须更换构建机镜像"; exit 1
fi

# 自上而下找 run_tests.py，并校验同目录有 pytest.ini
ROOT=""
for f in $(find . -maxdepth 4 -name run_tests.py 2>/dev/null); do
  d=$(dirname "$f")
  if [ -f "$d/pytest.ini" ]; then ROOT="$d"; break; fi
done
if [ -z "$ROOT" ]; then
  echo "!! 未找到工程根（当前目录 $(pwd)）"
  echo "---- 当前目录内容 ----"; ls -la
  echo "---- 二级目录内容 ----"; ls -la */ 2>/dev/null || true
  exit 1
fi
ROOT=$(cd "$ROOT" && pwd)
cd "$ROOT"
echo "工程根: $ROOT"
echo "解释器: $PY ($($PY --version 2>&1))"
# ---- 前导结束 ----
```

> **脚本层已内置同名自举逻辑**：`tools/ci_setup.py`、`tools/ci_probe.py`、
> `tools/ci_daily_test.py` 三个脚本在入口处都会自动定位工程根（标记为
> `run_tests.py` + `pytest.ini` + `config/settings.py` 三者齐全），
> 因此**即使前导片段失效，脚本自身也能纠正 CWD**。前导片段的价值是让
> 日志里能立刻看到真实路径，便于排查。

### Stage 1 — 环境装配（Environment Setup）

**Container(Job) 1：`装配测试环境`**，构建类型选容器构建机（或私有构建机）。

按顺序添加 Task（均用「执行 Shell 脚本」插件）：

**Step 1.1 — 打印环境信息，确认镜像具备 Python**

```bash
# 此步故意不加 set -e，目的是无论如何都把环境信息打全
echo "=== 构建机环境 ==="
uname -a
cat /etc/os-release 2>/dev/null || true
echo "whoami : $(id -un 2>/dev/null || echo unknown) (uid=$(id -u 2>/dev/null || echo '?'))"
echo "python3: $(command -v python3 || echo 缺失)"
echo "python : $(command -v python || echo 缺失)"
python3 --version 2>/dev/null || python --version 2>/dev/null || {
  echo "!! 镜像内无 Python，请更换构建机镜像"; exit 1;
}
echo "pip    : $(python3 -m pip --version 2>/dev/null || python -m pip --version 2>/dev/null || echo '缺失（脚本会尝试自举）')"
echo "git    : $(git --version 2>/dev/null || echo 缺失)"
echo "curl   : $(curl --version 2>/dev/null | head -1 || echo '缺失（将回退纯 Python 探测）')"
echo "apt    : $(command -v apt-get || echo 缺失)"
echo "=== WORKSPACE ==="
echo "CWD=$PWD  WORKSPACE=${WORKSPACE:-未设置}"
ls -la
echo "=== 定位工程根 ==="
find . -maxdepth 4 -name run_tests.py 2>/dev/null || true
```

> **看这一屏就能判定 R1/R2 是否成立**：
> - 出现 `!! 镜像内无 Python` → 必须换镜像（脚本层无法解决）
> - `pip 缺失` → 可继续，`ci_setup.py` 会用 `ensurepip` / `get-pip.py` 自举
> - `apt 缺失` 或 `whoami` 不是 root → Chromium 系统依赖装不上，
>   需镜像预装（见 Step 1.4 的说明）
> - `定位工程根` 输出的路径就是后续 Task 应该 `cd` 进去的地方

**Step 1.2 — 执行环境装配脚本**

粘贴 3.0 的通用前导，然后：

```bash
$PY tools/ci_setup.py
```

该脚本会自动完成：

1. 校验工程文件完整性
2. **确保 pip 可用**（不可用时依次尝试 `ensurepip` → 下载 `get-pip.py`）
3. 按可达性**自动选择 pip 源**（内网源 → 阿里云 → 腾讯云 → 官方源）
4. 安装 `requirements.txt`（失败时自动换阿里云源重试）
5. 安装 Playwright Chromium（先试 `--with-deps`，失败则退化为仅装浏览器）
6. **从流水线环境变量生成 `.env`**（凭据不落仓库）

> **设计要点**：本脚本**不因安装告警而失败**。能否运行由 Step 1.3 的探针判定。
> 这样即使某一步装不上，你仍能看到探针给出的完整诊断，而不是被一个
> 中途异常截断——这正是上一次卡住的原因。

可选参数：
- `--skip-browser`：仅做静态校验时跳过浏览器安装
- `--skip-deps`：镜像已预装依赖时跳过安装
- `--pip-index <url>`：强制指定 pip 源

**Step 1.3 — 环境探针（可行性门禁）**

粘贴 3.0 的通用前导，然后：

```bash
$PY tools/ci_probe.py
```

探针是**整个方案能否成立的关键验证**，会逐项检查：

| 检查项 | 失败含义 | 是否阻塞 |
| --- | --- | --- |
| 系统与运行时 | Python 版本 < 3.10 | 阻塞 |
| 系统与运行时 | 缺 git / curl | **不阻塞**（仅警告，有其他回退） |
| 网络连通性 | `irp-uat` / `cloud-uat` 不可达 | 阻塞 |
| 网络连通性 | PyPI 源不可达 | 警告（可换其他源） |
| 网络连通性 | 所有 PyPI 源都不可达 | 阻塞 |
| Python 依赖 | 包未装成功 | 阻塞 |
| Playwright 浏览器 | **真实启动 Chromium**，失败说明缺系统库 | 阻塞 |
| 登录态与配置 | 凭据/登录态就绪情况 | 警告 |
| 工程结构 | 代码未拉全 | 阻塞 |

退出码 0 = 具备条件；1 = 不具备，并打印具体修复命令。

> **Step 1.4（仅当探针在"Chromium 启动失败"处失败时才需要）**
>
> 说明容器缺 `libnss3`、`libgbm` 等系统库。按以下顺序处理：
>
> 1. 若容器是 root 且有 apt，直接补装：
>    ```bash
>    apt-get update && apt-get install -y \
>      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
>      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
>      libgbm1 libpango-1.0-0 libcairo2 libasound2 fonts-liberation
>    ```
> 2. 若第 1 步的 `apt-get update` 报网络错误 → 内网无 apt 源，**必须换镜像**
> 3. 若 `id -u` 不是 0 → 无权限，**必须换镜像**或申请带这些库的镜像
>
> 蓝盾官方 `bkci/ci:latest` 镜像通常已含大部分依赖；若页面提供该镜像，
> 优先选它可省去整个 Step 1.4。

### Stage 2 — 静态校验（Static Validation）

**Container(Job) 2：`资产与契约校验`**。此阶段不访问业务页面，秒级完成，先跑可快速失败。

> 每个 Task 都先粘贴 **3.0 的通用前导片段**（定位工程根 + 选解释器），再执行下面的命令。

**Step 2.1 — 资产登记表校验**

```bash
$PY tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml
```

预期输出：`Registry valid` + `Assets: 183`

**Step 2.2 — 生产契约校验**

```bash
$PY tools/validate_prod_console_contracts.py
```

预期输出：`Cases: 113` + `Classifications: conditional=69, mandatory=44`

**Step 2.3 — 用例收集数校验**

```bash
$PY tools/ci_daily_test.py --env uat --scope static
```

预期：`521 tests collected`。收集数与基线不符说明用例被误删或标记错误。

> 基线数字（2026-09-22 本机实测）：用例收集 **521**；生产契约 **113**（44 mandatory + 69 conditional）；
> 资产登记 **183**。三个数字是本工程当前的真实基线，脚本与文档若与之不符以实测为准。

### Stage 3 — 真实用例执行（Daily Test 主体）

**Container(Job) 3：`UAT 只读回归`**。

> 每个 Task 都先粘贴 **3.0 的通用前导片段**。

**Step 3.1 — 刷新登录态**

```bash
$PY tools/ci_daily_test.py --env uat --scope smoke --refresh-auth
```

> **为什么要每次刷新**：登录态 JSON 有过期时间，且容器是**无状态**的（每次构建都是干净
> 环境，`auth_states/` 不会从上次构建继承）。若不刷新，会因登录态缺失直接失败。
> `--refresh-auth` 会先用 `login` 标记跑登录用例重写 `auth_states/uat.json`。

**Step 3.2 — 全量只读回归**

```bash
$PY tools/ci_daily_test.py --env uat --scope readonly
```

`--scope readonly` 等价于 `-m readonly`，即**所有只读用例**，不含 `write`/`destructive`。
这是 daily test 的推荐范围：覆盖广、零写入风险。

**Step 3.3 — 归档测试报告**

用蓝盾的「归档构件」插件，归档路径填：

```
reports/ci/report-uat-readonly.html
reports/ci/ci-summary-uat-readonly.json
```

> 归档路径是**相对工程根**的。若归档插件也报找不到文件，说明它按 workspace 根解析，
> 此时改用 `**/reports/ci/*` 这类通配写法。

## 4. 定时触发配置

入口：流水线页面**右上角【编辑】** → 切到【触发方式】/【定时触发】页签。

BK-CI 的定时触发使用 **Cron 表达式**，通常为 5 位或 6 位：

```
# 每个工作日 08:30 执行（周一到周五）
0 30 8 * * 1-5
```

> 不同版本字段顺序可能为 `分 时 日 月 周` 或 `秒 分 时 日 月 周`，
> **以页面上的提示为准**，不要照抄。配置后建议先手动点一次「执行」验证，
> 再等一个周期确认自动触发生效。

建议：
- 定时任务同样要**传变量**（`ENV=uat` 等），在触发配置里绑定第 2 节的变量
- 时间避开业务低峰期的数据变更窗口，减少环境本身带来的抖动
- 首次上线先设 `每日 1 次`，稳定后再考虑增加频率

## 5. 执行范围速查

`tools/ci_daily_test.py` 支持的 `--scope`：

| scope | 实际 marker | 用途 |
| --- | --- | --- |
| `static` | （dry-run） | 只收集，不执行 |
| `smoke` | `smoke and readonly` | 核心冒烟，最快 |
| `readonly` | `readonly` | **daily test 推荐**：全量只读 |
| `regression` | `regression and readonly` | 回归只读范围 |
| `mandatory` | `prod_mandatory and readonly` | 生产严格门禁 |
| `conditional` | `prod_conditional and readonly` | 生产条件用例 |

退出码语义：
- `0` = 全部通过（允许 skip / NOT_APPLICABLE）
- `1` = 存在真实失败
- `2` = 环境或参数错误（未真正执行用例）

## 6. 已知风险与待验证项

| # | 风险 | 影响 | 处置 | 本方案的对策 |
| --- | --- | --- | --- | --- |
| R1 | 容器缺 Chromium 系统依赖 | **阻塞**，用例全挂 | 优先跑探针验证；失败则改镜像 | 探针真实启动 Chromium 判定；`install-deps` 失败给出 apt 命令 |
| R2 | 构建机无 Python 或版本 < 3.10 | 阻塞 | 换镜像或脚本内装 | Step 1.1 先探测；探针判定版本 |
| R3 | 内网 PyPI 源不可达 | 降级 | 脚本自动回退其他源 | 四源依次探测 + 阿里云二次重试 |
| R4 | 登录态过期 | 假失败 | 每次构建带 `--refresh-auth` | 已内置；刷新失败即中止不发假报告 |
| R5 | 仓库内 `.env.example` 含明文密码 | **安全债** | 见第 7 节 | 未处理（需用户决策） |
| R6 | 用例耗时超出流水线超时 | 中断 | 先跑 `smoke` 估时，再放开 `readonly` | 见第 8 节落地顺序 |
| **R7** | **代码 checkout 到 workspace 子目录，`tools/xxx.py` 找不到** | **阻塞** | 已在脚本层根治 | 三个脚本入口均自动定位工程根；Task 前导片段同步定位并打印真实路径 |
| R8 | 容器内 `pip` 不可用（无 `ensurepip`） | 阻塞 | 脚本自举 | `ensurepip` → 下载 `get-pip.py` 两级回退 |
| R9 | 容器内无 `curl` | 误报网络不可达 | 用纯 Python 探测 | 探针与 setup 均回退 `urllib`，curl 缺失只警告不阻塞 |
| R10 | 容器非 root，`--with-deps` / `install-deps` 失败 | 可能阻塞 R1 | 退化 + 明确提示 | 先 `--with-deps`，失败退化为仅装浏览器；提示需镜像预装 |

> **R7 是上一次构建实际踩到的坑**（2026-09-22 10:46:15 的日志）：
> workspace 是 `/data/pipe/workspace/a9125231-...`，而工程在其子目录，
> 因此 `python3 tools/ci_setup.py` 报 `can't open file`。现已从脚本层根治。

## 7. 安全债：仓库内的明文密码

**当前状态**：`.env.example` 已改为占位符，不再保存可用账号密码。流水线必须通过密文变量注入真实凭据：

```
USERNAME=<账号>
PASSWORD=<兼容兜底密码，可留空>
UAT_PASSWORD=<UAT 密码>
PROD_PASSWORD=<PROD 密码>
```

`config/settings.py` 在 `.env` 不存在时会回退读取 `.env.example`，但占位符不能用于登录。
因此真实用例执行前必须由 `ci_setup.py` 根据流水线密文变量生成 `.env`。

后续安全处置：

1. 在流水线变量中配置 `USERNAME` / `UAT_PASSWORD`（密文），由 `ci_setup.py` 生成 `.env`。
2. 轮换曾写入仓库的账号密码。
3. 是否从 Git 历史中清理旧值需单独评审；该操作会重写历史，不在日常提交中执行。

> **注意**：`ci_setup.py` 生成 `.env` 时会与已有 `.env` **合并**而非覆盖，
> 且会保留 `ENV_KEYS` 之外的自定义键，避免静默丢配置。

## 8. 落地顺序（建议）

1. **先只配 Step 1.1**（环境信息打印 + 定位工程根），手动执行一次
   - 目的：确认镜像有没有 Python/pip/apt/root，以及工程被 checkout 到哪一层
   - 这一步零失败风险，输出信息量最大
2. 追加 **Step 1.2 + 1.3**（装配 + 探针），手动执行
   - 跑完看探针输出，确认 R1/R2/R8/R9/R10 哪些成立
   - 全部 PASS → 继续第 3 步
   - 失败在"Chromium 启动失败" → 按 Step 1.4 处理或换镜像
3. 追加 **Stage 2**（静态校验），手动执行，确认 183 / 113 / 521 三个数字
4. 追加 **Stage 3**，先只跑 `--scope smoke`，确认能跑通真实用例并看到报告
5. 稳定后把范围放开为 `readonly`，并配置定时触发
6. 观察若干天，按失败率决定是否升级为阻断式门禁

> **遇到问题时优先看什么**：
> - `定位工程根` 没输出 → 代码没拉下来，检查【拉取代码】插件
> - 探针"阻塞项"列表 → 按它给的修复命令逐条处理，不要猜
> - `tools/ci_locate_workspace.sh` → **专门用来诊断 workspace 目录结构**。
>   作为独立 Task 跑一次即可：
>   ```bash
>   bash tools/ci_locate_workspace.sh
>   ```
>   它会打印：当前 CWD、蓝盾变量值、向上/向下搜索命中的路径、深度 3 的完整
>   目录树（标注哪里含 `run_tests.py`），并直接给出可粘贴的 `cd` 命令。
>   该脚本自身**不会失败**（不用 `set -e`，不依赖 `head`/`sed`/`grep`）。

---

**最后提醒**：本文档描述的脚本（`tools/ci_setup.py`、`tools/ci_probe.py`、
`tools/ci_daily_test.py`）已在本地 Windows 环境通过语法校验与实跑验证，
**并且已验证「从父目录调用」场景**（模拟流水线 workspace 布局）能自动定位工程根。
但仍**尚未在蓝盾构建机上验证过**——第 8 节的顺序就是为了一次只引入一个变量，
避免多处同时出错难以定位。

**环境无关性设计小结**（针对容器环境做的防御）：

| 不确定因素 | 防御手段 |
| --- | --- |
| CWD 不是工程根 | 三个脚本入口自动定位（`run_tests.py`+`pytest.ini`+`config/settings.py` 三重标记） |
| `python3` 不存在 | 前导片段 `command -v python3 \|\| command -v python`，两者都无则明确报错 |
| `pip` 不存在 | `ensurepip` → `get-pip.py` 两级自举 |
| pip 源不可达 | 四源依次探测 + 阿里云二次重试 |
| 无外网 | 探针把业务域名（阻塞）与 pip 源（警告）分级判定 |
| 无 `curl` | 回退纯 Python `urllib` 探测 |
| 非 root / 无 apt | `install-deps` 失败不中断，转为明确提示 + 打印需预装的包名 |
| stdout 非 UTF-8 | 脚本内 `sys.stdout.reconfigure(encoding="utf-8")` |
| 安装部分失败 | `ci_setup.py` 不因告警失败，交由探针给出完整诊断 |
