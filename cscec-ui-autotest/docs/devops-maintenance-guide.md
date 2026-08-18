# CSCEC UI 自动化工程 DevOps 维护与 Git 联动指南

本文档规定 `cscec-ui-autotest` 本地工程与远程 Git 仓库（GitHub / 企业内部 GitLab）的联动机制，以及每次进行关键业务/用例更新时的 **DevOps 维护标准流程**。

---

## 1. 本地工程与 Git 远程仓库关联架构

```text
[ 本地工作区 d:\Automation\cscec-ui-autotest ]
       │
       ├── 1. 本地开发 / 用例编写 / 调试
       ├── 2. 本地资产校验: python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml
       ├── 3. 本地干跑校验: python run_tests.py --env uat --dry-run
       │
       ▼ Git 提交 (commit) & 推送 (push)
 [ 远程 Git 仓库 ] (GitHub: edison1256/cscec-ui-autotest)
       │
       ▼ 触发 GitHub Actions / CI 流水线 (自动门禁)
 ┌────────────────────────────────────────────────────────┐
 │ 1. 资产 Schema 结构校验 (validate_ui_assets.py)       │
 │ 2. UAT 用例收集与语法检查 (run_tests.py --dry-run)     │
 │ 3. PROD 生产防护策略过滤校验 (-m "smoke and readonly") │
 └────────────────────────────────────────────────────────┘
```

### 远程仓库配置说明

本地已绑定远程仓库配置：
- **GitHub 仓库**：`https://github.com/edison1256/cscec-ui-autotest.git` (Remote 名称: `github`)
- **内部 GitLab 仓库**（可选）：`https://git.cscec.com/20431644/jacoco.git` (Remote 名称: `origin`)

通过 `gh auth setup-git` 已完成凭据自动托管，推送代码无需重复输入密码。

---

## 2. 每次关键更新的 DevOps 维护标准流程（5 步法）

当有新需求上线、生产冒烟 Checklist 变更、或修复既有用例时，请严格按以下步骤操作：

### 步骤 1：本地用例与 Page Object 编写
- 在 `pages/` 下更新/新建 Page Object；
- 在 `tests/` 下编写对应的 pytest 测试用例；
- 必须按规范标记 `markers`（如 `smoke`, `readonly`, `write`, `destructive`）。

### 步骤 2：更新 UI 资产登记池 (`ui_case_assets.yaml`)
- 在 `test_assets/registry/ui_case_assets.yaml` 中追加/更新用例的资产描述：
  - `asset_id`
  - `module`
  - `title`
  - `lifecycle` (如 `uat_automated` / `prod_regression`)
  - `markers`
  - `env_policy` (写明 `prod_default` 是否为 true/false)

### 步骤 3：本地合规性与预检校验 (Pre-commit Check)
在终端运行以下两条指令，确保代码和资产结构无误：

```powershell
# 1. 校验资产 YAML 登记合规性
python tools/validate_ui_assets.py --registry test_assets/registry/ui_case_assets.yaml

# 2. 校验 pytest 用例可正常收集
python run_tests.py --env uat --dry-run
```

### 步骤 4：标准化 Git 提交 (Commit)
> **作用域约束**：本工程是 `D:/Automation` 更大 git 仓库的子目录。所有 git 操作必须限定到本工程子树，绝不可在父目录作用域执行 `git add` / `git commit` / `git push`。定义 `$PROJECT_DIR = D:/Automation/cscec-ui-autotest`。

使用 Angular/Conventional Commit 格式提交（仅暂存受监控路径，绝不使用 `git add .` 或 `git add -A`）：

```powershell
# 提交前护栏：确认暂存路径全部位于本工程子树内
git -C "$PROJECT_DIR" diff --cached --name-only | Where-Object { $_ -notmatch '^cscec-ui-autotest/' } | ForEach-Object { throw "越界文件: $_" }

# 仅暂存受监控路径（目录 + 根目录治理文件）
git -C "$PROJECT_DIR" add pages tests core config test_assets docs tools utils AGENTS.md README.md .gitignore requirements.txt run_tests.py pytest.ini

git -C "$PROJECT_DIR" commit -m "feat(scope): 描述本次修改的关键业务功能/用例"
```

**Common Commit Prefixes**:
- `feat`: 新增用例、Page Object 或自动化场景
- `fix`: 修复已失配的定位元素、选择器或断言
- `chore`: 维护配置文件、依赖包或测试数据
- `ci`: 维护 CI 流水线或 GitHub Actions 脚本
- `docs`: 维护架构、治理规范或运维文档

### 步骤 5：推送至 Git 远程仓库 (Push)

```powershell
# 推送到 GitHub（限定本工程子树）
git -C "$PROJECT_DIR" push github master
```

---

## 3. 自动化 DevOps CI 门禁机制 (`.github/workflows/ci.yml`)

推送完成后，GitHub Actions 会自动触发执行以下任务：

1. **自动检出代码并初始化 Python 3.12 环境**；
2. **资产治理校验 (Asset Validation)**：自动运行 `validate_ui_assets.py`，若资产 YAML 结构损坏或缺失必填字段，CI 自动拉红报警；
3. **UAT 测试套件收集 (Dry-Run)**：确保代码无 Python 语法错误，导入未断裂；
4. **PROD 生产防护校验**：验证生产环境下 `smoke and readonly` 能否正常且安全地剥离写操作用例。

可以通过 GitHub 仓库页面查看每次 Commit 的 CI 运行状态绿勾标志。

---

## 4. 生产上线当天必测走查套件执行 (Release Day Walkthrough)

每次新版本部署上线后，必须执行全量 49 条走查套件：

```powershell
# 1. 刷新生产登录态 (如需)
python run_tests.py --env prod --refresh-auth -p tests/login/test_login.py

# 2. 一键执行 PC + 移动端 49 条必测走查套件
python run_tests.py --env prod
```

详细规范请查阅：[`docs/prod-release-mandatory-walkthrough-suite.md`](prod-release-mandatory-walkthrough-suite.md)

