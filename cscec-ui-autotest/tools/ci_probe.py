#!/usr/bin/env python3
"""CI 环境探针：在流水线构建机上验证能否跑通 UI 自动化。

用途：作为蓝盾流水线的第一个 Task，快速判定构建机是否具备运行条件。
退出码 0 = 具备条件；非 0 = 不具备，并给出具体缺失项。

设计原则：
- 只读探测，不访问业务页面以外的任何写操作。
- 不依赖 pytest / 项目 conftest，可在裸 Python 环境直接运行。
- 分阶段输出，任一阶段失败立即给出修复命令。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def _ensure_project_root() -> None:
    """确保工作目录为工程根目录。

    蓝盾「拉取代码」插件默认把仓库 checkout 到 workspace 的子目录（仓库名），
    因此从 workspace 根直接调用 tools/xxx.py 会失败。这里自动上溯定位并切换，
    使脚本在任意层级被调用都能正确运行。
    """
    markers = ("run_tests.py", "pytest.ini", "config/settings.py")
    if all((PROJECT_ROOT / m).exists() for m in markers):
        os.chdir(PROJECT_ROOT)
        return

    # 兜底：从当前目录向下搜索
    cwd = Path.cwd()
    for depth in range(1, 4):
        for candidate in cwd.glob("/".join(["*"] * depth) + "/run_tests.py"):
            root = candidate.parent
            if all((root / m).exists() for m in markers):
                print(f"[INFO] 自动定位工程根: {root}", flush=True)
                os.chdir(root)
                return

    raise SystemExit(
        f"无法定位工程根目录（当前 {cwd}）。\n"
        f"期望包含: {', '.join(markers)}\n"
        f"请在 Task 开头显式 cd 到工程目录，或确认【拉取代码】插件已正确执行。"
    )


class Probe:
    """收集探针结果并决定退出码。"""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def ok(self, message: str) -> None:
        print(f"{PASS} {message}")

    def fail(self, message: str, fix: str = "") -> None:
        self.failures.append(message)
        print(f"{FAIL} {message}")
        if fix:
            print(f"       修复建议: {fix}")

    def warn(self, message: str, note: str = "") -> None:
        self.warnings.append(message)
        print(f"{WARN} {message}")
        if note:
            print(f"       提示: {note}")


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    """执行命令并返回 (exit_code, 合并输出)。"""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: {' '.join(cmd)}"


def probe_system(p: Probe) -> None:
    print("\n=== 1. 系统与运行时 ===")
    print(f"     OS       : {platform.platform()}")
    print(f"     Python   : {sys.version.split()[0]} ({sys.executable})")
    print(f"     CWD      : {os.getcwd()}")
    print(f"     WORKSPACE: {os.getenv('WORKSPACE', '(未设置)')}")
    print(f"     CI 环境变量: BK_CI_PIPELINE_ID={os.getenv('BK_CI_PIPELINE_ID', '-')} "
          f"BK_CI_BUILD_ID={os.getenv('BK_CI_BUILD_ID', '-')}")

    if sys.version_info < (3, 10):
        p.fail(f"Python 版本过低: {sys.version.split()[0]}，需要 >= 3.10",
               "更换构建机镜像，或在 Task 中安装 python3.10+")
    else:
        p.ok(f"Python 版本满足要求: {sys.version.split()[0]}")

    # git 仅用于诊断代码拉取，缺失不阻塞（代码已由插件拉好）
    if shutil.which("git"):
        code, out = run(["git", "--version"])
        version = out.strip().splitlines()[0] if out.strip() else "unknown"
        p.ok(f"git 可用: {version}")
    else:
        p.warn("git 不存在", "代码已由【拉取代码】插件检出，通常不影响执行")

    # curl 非必需：本探针与 ci_setup 都有纯 Python 回退
    if shutil.which("curl"):
        code, out = run(["curl", "--version"])
        version = out.strip().splitlines()[0] if out.strip() else "unknown"
        p.ok(f"curl 可用: {version}")
    else:
        p.warn("curl 不存在", "网络探测将回退到纯 Python urllib，不影响结论")


def _http_code(url: str, timeout: int = 20) -> tuple[str, str]:
    """返回 (状态码, 错误信息)。状态码为 '000' 表示不可达。

    关键：必须把 curl 的 stdout（%{http_code} 专用输出）与 stderr（进度/错误）
    分开读取。若合并，stderr 中的字节数会被误解析成状态码。
    """
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-o", os.devnull, "-w", "%{http_code}",
             "--max-time", str(timeout), "-k", url],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
    except FileNotFoundError:
        return "000", "curl not found"
    except subprocess.TimeoutExpired:
        return "000", f"timeout after {timeout}s"

    code_text = (proc.stdout or "").strip()
    err_text = (proc.stderr or "").strip().replace("\n", " ")[:200]

    if code_text.isdigit() and len(code_text) == 3 and code_text != "000":
        return code_text, ""
    return "000", err_text or f"exit={proc.returncode}"


def _urlopen_code(url: str, timeout: int = 20) -> tuple[str, str]:
    """不依赖 curl 的连通性探测（容器可能没有 curl）。"""
    import ssl
    import urllib.error
    import urllib.request

    ctx = ssl.create_default_context()
    # 内网自签证书场景：仅探测可达性，不做身份校验
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    request = urllib.request.Request(url, headers={"User-Agent": "cscec-ui-probe/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ctx) as resp:
            return str(resp.status), ""
    except urllib.error.HTTPError as exc:
        # 401/403/302 也算"可达"——说明网络通、证书握手成功
        return str(exc.code), ""
    except Exception as exc:  # noqa: BLE001
        return "000", f"{type(exc).__name__}: {str(exc)[:150]}"


def probe_url(url: str, timeout: int = 20) -> tuple[str, str]:
    """优先 curl，其次 urllib 回退，返回 (状态码, 错误信息)。"""
    if shutil.which("curl"):
        code, err = _http_code(url, timeout)
        if code != "000":
            return code, ""
        fallback_code, fallback_err = _urlopen_code(url, timeout)
        if fallback_code != "000":
            return fallback_code, ""
        return "000", err or fallback_err
    return _urlopen_code(url, timeout)


def probe_network(p: Probe) -> None:
    print("\n=== 2. 网络连通性 ===")
    # (名称, URL, 是否阻塞项)
    # 业务域名不可达 → daily test 无从谈起，属阻塞
    # pip 源不可达 → 只影响依赖安装，脚本已有多源回退，属警告
    targets = [
        ("UAT 控制台", "https://irp-uat.cscec.com/", True),
        ("UAT 门户", "https://cloud-uat.cscec.com/", True),
        ("PyPI 内网源", "https://pypi.cscec.com/simple/", False),
        ("PyPI 阿里源", "https://mirrors.aliyun.com/pypi/simple/", False),
        ("PyPI 官方源", "https://pypi.org/simple/", False),
    ]

    if not shutil.which("curl"):
        print("    (curl 不存在，使用纯 Python urllib 探测)")

    reachable_pip = 0
    for name, url, blocking in targets:
        code, err = probe_url(url)
        if code != "000":
            p.ok(f"{name} 可达 (HTTP {code}) {url}")
            if "PyPI" in name:
                reachable_pip += 1
        elif blocking:
            p.fail(f"{name} 不可达 {url}" + (f" | {err}" if err else ""),
                   "业务域名必须可达，否则 daily test 无法执行；"
                   "若为 DNS/代理问题，需在构建机层面放通 *.cscec.com")
        else:
            p.warn(f"{name} 不可达 {url}" + (f" | {err}" if err else ""),
                   "pip 源不可达时 ci_setup.py 会自动回退其他源")

    if reachable_pip == 0:
        p.fail("所有 PyPI 源均不可达",
               "依赖无法安装。需在构建机开通外网出口，或配置内网 PyPI 镜像")


def probe_dependencies(p: Probe) -> None:
    print("\n=== 3. Python 依赖 ===")
    required = {
        "pytest": "pytest",
        "playwright": "playwright",
        "dotenv": "python-dotenv",
        "yaml": "PyYAML",
    }
    missing = []
    for module, package in required.items():
        code, _ = run([sys.executable, "-c", f"import {module}"])
        if code == 0:
            p.ok(f"{module} 已安装")
        else:
            missing.append(package)
            p.fail(f"{module} 未安装", f"pip install {package}")

    if missing:
        print(f"\n    一次性安装命令：")
        print(f"    {sys.executable} -m pip install -r requirements.txt "
              f"-i https://mirrors.aliyun.com/pypi/simple/ "
              f"--trusted-host mirrors.aliyun.com")
        print(f"    或直接重跑装配脚本：{sys.executable} tools/ci_setup.py", flush=True)


def probe_playwright_browser(p: Probe) -> None:
    print("\n=== 4. Playwright 浏览器 ===")
    # playwright 未安装时不再重复报 FAIL（第 3 节已报过），只给提示
    if run([sys.executable, "-c", "import playwright"])[0] != 0:
        p.warn("playwright 未安装，跳过浏览器检查", "依赖未装成功，见第 3 节")
        return

    code, out = run([
        sys.executable, "-c",
        "from importlib.metadata import version; print(version('playwright'))",
    ])
    if code == 0 and out.strip():
        p.ok(f"playwright 版本: {out.strip().splitlines()[-1]}")

    # 浏览器缓存目录：仅作诊断信息，不作为通过判据。
    # Linux 默认 ~/.cache/ms-playwright；Windows 默认 %USERPROFILE%\AppData\Local\ms-playwright
    env_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    cache_candidates = [
        Path(env_path) if env_path else None,
        Path.home() / ".cache" / "ms-playwright",
        Path("/root/.cache/ms-playwright",
             ) if os.name != "nt" else None,
        Path(os.getenv("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt" else None,
    ]
    found_dir = None
    for cand in cache_candidates:
        if cand and cand.exists():
            found_dir = cand
            break

    if found_dir:
        entries = sorted(x.name for x in found_dir.iterdir() if x.is_dir())
        chromium = [e for e in entries if e.startswith("chromium")]
        print(f"     浏览器缓存目录: {found_dir}")
        print(f"     已下载浏览器: {chromium if chromium else '(无 chromium)'}")
    else:
        print("     未探测到浏览器缓存目录（不阻塞，以实际启动结果为准）")

    # 真正启动一次浏览器，这是唯一可信的验证
    print("     正在尝试真实启动 Chromium ...")
    launch_code = """
import sys
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page()
        page.goto("about:blank")
        print("LAUNCH_OK title=", repr(page.title()))
        browser.close()
except Exception as exc:
    print("LAUNCH_FAIL", type(exc).__name__, str(exc)[:600])
    sys.exit(1)
"""
    code, out = run([sys.executable, "-c", launch_code], timeout=240)
    if code == 0 and "LAUNCH_OK" in out:
        p.ok(f"Chromium 可成功启动 ({out.strip().splitlines()[-1][:80]})")
    else:
        p.fail(f"Chromium 启动失败: {out.strip()[-700:]}",
               "常见原因：缺少系统库。执行 python -m playwright install-deps chromium "
               "（需 root 权限）；若容器不允许，需在 Dockerfile 预装依赖")


def probe_auth_state(p: Probe) -> None:
    print("\n=== 5. 登录态与配置 ===")
    env_file = PROJECT_ROOT / ".env"
    example_file = PROJECT_ROOT / ".env.example"

    if env_file.exists():
        p.ok(f".env 存在: {env_file}")
    elif example_file.exists():
        p.warn(".env 不存在，将回退读取 .env.example",
               "生产建议用流水线环境变量注入密码，不依赖仓库内文件")

    auth_dir = PROJECT_ROOT / "auth_states"
    uat_state = auth_dir / "uat.json"
    if uat_state.exists():
        size = uat_state.stat().st_size
        p.ok(f"UAT 登录态存在 ({size} 字节): {uat_state}")
    else:
        p.warn("UAT 登录态不存在，首次执行需 --refresh-auth",
               "日志类流水线建议每次 refresh-auth，避免态过期")

    for var in ("USERNAME", "UAT_PASSWORD"):
        if os.getenv(var):
            p.ok(f"环境变量 {var} 已注入")
        elif env_file.exists() or example_file.exists():
            p.warn(f"环境变量 {var} 未注入（若仓库内有 .env 可忽略）")
        else:
            p.fail(f"环境变量 {var} 缺失", f"在流水线环境变量中配置 {var}")


def probe_project_structure(p: Probe) -> None:
    print("\n=== 6. 工程结构 ===")
    required = [
        "run_tests.py",
        "pytest.ini",
        "requirements.txt",
        "config/settings.py",
        "tests/conftest.py",
    ]
    for rel in required:
        path = PROJECT_ROOT / rel
        if path.exists():
            p.ok(f"{rel} 存在")
        else:
            p.fail(f"{rel} 缺失", "检查代码源是否拉取完整 / 工作目录是否正确")


def main() -> int:
    # 容器内 stdout 常为非 UTF-8，显式重配避免中文日志乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    _ensure_project_root()

    print("=" * 70)
    print("CSCEC UI 自动化 - CI 环境探针")
    print("=" * 70)
    print(f"工程根目录: {PROJECT_ROOT}", flush=True)

    p = Probe()
    probe_system(p)
    probe_network(p)
    probe_dependencies(p)
    probe_playwright_browser(p)
    probe_auth_state(p)
    probe_project_structure(p)

    print("\n" + "=" * 70)
    print(f"总结: 失败 {len(p.failures)} 项, 警告 {len(p.warnings)} 项")
    if p.failures:
        print("\n阻塞项:")
        for i, item in enumerate(p.failures, 1):
            print(f"  {i}. {item}")
        print("\n结论: 构建机当前不具备运行条件，请按上方修复建议处理后重试。")
        return 1
    if p.warnings:
        print("\n警告项（不阻塞，但建议关注）:")
        for i, item in enumerate(p.warnings, 1):
            print(f"  {i}. {item}")
    print("\n结论: 构建机具备运行 UI 自动化的条件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
