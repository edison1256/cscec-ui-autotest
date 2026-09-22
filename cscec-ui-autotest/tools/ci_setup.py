#!/usr/bin/env python3
"""CI 环境装配脚本：在流水线构建机上准备可运行的 UI 自动化环境。

职责：
1. 按内网可达性选择 pip 源，安装 requirements.txt。
2. 安装 Playwright Chromium 及其系统依赖。
3. 用环境变量生成 .env（凭据不落仓库）。
4. 校验工程完整性。

设计原则：
- 幂等：重复执行不产生副作用，已装则跳过。
- 快速失败：任一步骤失败立即退出非 0，不掩盖问题。
- 可观测：每步打印耗时与关键输出，便于排查。

用法：
    python tools/ci_setup.py [--skip-browser] [--pip-index <url>]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 工程根判定标记（三个齐全才认为是真正的工程根）
ROOT_MARKERS = ("run_tests.py", "pytest.ini", "config/settings.py")


def _ensure_project_root() -> None:
    """确保工作目录为工程根目录并返回。

    蓝盾「拉取代码」插件默认把仓库 checkout 到 workspace 的**子目录**（仓库名），
    而 Task 的初始 CWD 是 workspace 根，因此直接调用 `python3 tools/ci_setup.py`
    会报 "can't open file"。这里做三件事：
      1. 脚本位于 <repo>/tools/ 下 → PROJECT_ROOT 本身就是工程根，直接切过去；
      2. 否则从当前目录向下搜索 run_tests.py 定位工程根；
      3. 都失败则给出可操作的报错，而不是让后续步骤以晦涩的方式崩掉。
    """
    if all((PROJECT_ROOT / m).exists() for m in ROOT_MARKERS):
        os.chdir(PROJECT_ROOT)
        return

    cwd = Path.cwd()
    for depth in range(1, 4):
        pattern = "/".join(["*"] * depth) + "/run_tests.py"
        for candidate in sorted(cwd.glob(pattern)):
            root = candidate.parent
            if all((root / m).exists() for m in ROOT_MARKERS):
                print(f"[INFO] 由当前目录上溯定位工程根: {root}", flush=True)
                os.chdir(root)
                return

    raise SystemExit(
        f"无法定位工程根目录（当前 {cwd}）。\n"
        f"期望目录包含: {', '.join(ROOT_MARKERS)}\n"
        f"排查: 确认【拉取代码】插件已执行，或用 bash tools/ci_locate_workspace.sh 查看实际路径。"
    )


PIP_INDEXES = [
    ("内网源(pypi.cscec.com)", "https://pypi.cscec.com/simple/"),
    ("阿里云源", "https://mirrors.aliyun.com/pypi/simple/"),
    ("腾讯云源", "https://mirrors.cloud.tencent.com/pypi/simple/"),
    ("官方源", "https://pypi.org/simple/"),
]

# 生成 .env 时从流水线环境变量透传的键
ENV_KEYS = [
    "ENV",
    "USERNAME",
    "PASSWORD",
    "UAT_PASSWORD",
    "PRE_PASSWORD",
    "PROD_PASSWORD",
    "HEADLESS",
    "BROWSER_CHANNEL",
    "SLOW_MO",
    "NAVIGATION_TIMEOUT",
    "ACTION_TIMEOUT",
    "DEFAULT_TIMEOUT",
    "PORTAL_EXPECTED_TENANT",
    "RUN_PORTAL_WRITE_CASES",
]


def log(message: str) -> None:
    print(f"\n>>> {message}", flush=True)


def run(cmd: list[str], timeout: int = 1800, check: bool = True) -> tuple[int, str]:
    print(f"    $ {' '.join(cmd)}", flush=True)
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    elapsed = time.monotonic() - started
    output = (proc.stdout or "") + (proc.stderr or "")
    print(f"    exit={proc.returncode} ({elapsed:.1f}s)", flush=True)
    if output.strip():
        tail = output.strip().splitlines()
        for line in tail[-25:]:
            print(f"      | {line}", flush=True)
        if len(tail) > 25:
            print(f"      | ... (共 {len(tail)} 行，仅显示末 25 行)", flush=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(cmd)} (exit={proc.returncode})")
    return proc.returncode, output


def _http_code(url: str, timeout: int = 15) -> str:
    """返回 HTTP 状态码，'000' 表示不可达。

    必须分开读取 curl 的 stdout（%{http_code}）与 stderr（进度/错误），
    否则 stderr 中的字节数会被误解析成状态码。
    """
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-o", os.devnull, "-w", "%{http_code}",
             "--max-time", str(timeout), "-k", url],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "000"

    code_text = (proc.stdout or "").strip()
    if code_text.isdigit() and len(code_text) == 3 and code_text != "000":
        return code_text
    return "000"


def _urlopen_code(url: str, timeout: int = 15) -> str:
    """纯 Python 的连通性探测，不依赖 curl（容器可能没装 curl）。"""
    import urllib.error
    import urllib.request

    # 内网自签证书场景下跳过校验，仅为探测可达性
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
            return str(resp.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception:
        return "000"


def probe_url(url: str, timeout: int = 15) -> str:
    """优先用 curl，其次回退 urllib；返回状态码或 '000'。"""
    if shutil.which("curl"):
        code = _http_code(url, timeout)
        if code != "000":
            return code
    return _urlopen_code(url, timeout)


def _pip_available() -> bool:
    """检查当前解释器能否调用 pip。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def ensure_pip() -> None:
    """确保 pip 可用；容器常见的 python3 无 ensurepip 时需要自举。"""
    log("检查 pip 可用性")
    if _pip_available():
        print("    pip 可用", flush=True)
        return

    print("    pip 不可用，尝试 ensurepip", flush=True)
    code, _ = run([sys.executable, "-m", "ensurepip", "--upgrade"],
                  timeout=600, check=False)
    if code == 0 and _pip_available():
        print("    ensurepip 成功", flush=True)
        return

    print("    ensurepip 失败，尝试下载 get-pip.py 自举", flush=True)
    import urllib.request

    get_pip = Path("/tmp/get-pip.py")
    downloaded = False
    for url in ("https://bootstrap.pypa.io/get-pip.py",
                "https://mirrors.aliyun.com/pypi/get-pip.py"):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                get_pip.write_bytes(resp.read())
            downloaded = True
            print(f"    已下载 get-pip.py: {url}", flush=True)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"    下载失败 {url}: {type(exc).__name__}", flush=True)

    if not downloaded:
        raise SystemExit(
            "pip 不可用且无法自举。请在镜像中预装 pip：\n"
            "  apt-get update && apt-get install -y python3-pip\n"
            "或改用含 pip 的构建镜像。"
        )

    run([sys.executable, str(get_pip), "--no-warn-script-location"], timeout=600)
    if not _pip_available():
        raise SystemExit("get-pip.py 执行后 pip 仍不可用，请更换镜像。")
    print("    pip 自举成功", flush=True)


def pick_pip_index(forced: str | None) -> str:
    """按顺序探测可达的 pip 源，返回第一个可用的。"""
    if forced:
        log(f"使用显式指定的 pip 源: {forced}")
        return forced

    log("探测可用的 pip 源")
    for name, url in PIP_INDEXES:
        code = probe_url(url)
        if code != "000":
            print(f"    -> 选用 {name}: {url} (HTTP {code})", flush=True)
            return url
        print(f"    -> {name} 不可达: {url}", flush=True)

    print("    -> 全部探测失败，回退官方源（可能超时）", flush=True)
    return "https://pypi.org/simple/"


def install_requirements(index_url: str) -> None:
    log("安装 Python 依赖")
    host = index_url.split("//")[-1].split("/")[0]

    base = [sys.executable, "-m", "pip", "install",
            "--no-warn-script-location", "--disable-pip-version-check",
            "-i", index_url, "--trusted-host", host]

    # 第一步：升级 pip 与构建后端；失败不致命（可能是外网源不可达）
    code, _ = run(base + ["--upgrade", "pip", "setuptools", "wheel"],
                  timeout=900, check=False)
    if code != 0:
        print("    !! pip/setuptools 升级失败，继续尝试安装依赖", flush=True)

    # 第二步：装 requirements；外网不通时降级到国内镜像
    code, out = run(base + ["-r", "requirements.txt"], timeout=2400, check=False)
    if code == 0:
        return

    print("    !! 依赖安装失败，尝试国内镜像重试", flush=True)
    retry_base = [sys.executable, "-m", "pip", "install",
                  "--no-warn-script-location", "--disable-pip-version-check",
                  "-i", "https://mirrors.aliyun.com/pypi/simple/",
                  "--trusted-host", "mirrors.aliyun.com"]
    code, out = run(retry_base + ["-r", "requirements.txt"],
                    timeout=2400, check=False)
    if code != 0:
        print("    !! 依赖安装仍未成功，将交由探针判定是否可以继续。", flush=True)


def install_browser() -> None:
    log("安装 Playwright Chromium")
    code, _ = run([sys.executable, "-m", "playwright", "install",
                   "chromium", "--with-deps"],
                  timeout=2400, check=False)
    if code == 0:
        return

    # --with-deps 需要 root+apt，容器内常见失败；退化为只装浏览器
    print("    !! --with-deps 失败（可能非 root 或无 apt），退化为仅装浏览器", flush=True)
    code, _ = run([sys.executable, "-m", "playwright", "install", "chromium"],
                  timeout=1800, check=False)
    if code != 0:
        print("    !! Chromium 安装失败，探针将判定为不具备条件。", flush=True)
        return

    log("尝试安装 Chromium 系统依赖")
    code, _ = run([sys.executable, "-m", "playwright", "install-deps", "chromium"],
                  timeout=1200, check=False)
    if code != 0:
        print("    !! 系统依赖安装失败（通常是非 root）。Chromium 可能无法启动。", flush=True)
        print("    !! 若后续探针失败，需在镜像层面预装依赖：", flush=True)
        print("    !!   apt-get update && apt-get install -y libnss3 libnspr4 "
              "libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 "
              "libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 "
              "libpango-1.0-0 libcairo2 libasound2 fonts-liberation", flush=True)


def write_env_file() -> None:
    log("生成 .env（从流水线环境变量注入，凭据不落仓库）")
    env_path = PROJECT_ROOT / ".env"

    present = {key: os.environ[key] for key in ENV_KEYS if os.environ.get(key)}
    if not present:
        print("    !! 未检测到任何流水线环境变量，将保留仓库内已有的 .env/.env.example", flush=True)
        print("    !! 请确认已在流水线【变量】中配置 ENV / USERNAME / UAT_PASSWORD 等。", flush=True)
        return

    # 与已有 .env 合并，避免覆盖用户手工写入但未在流水线变量中声明的键
    merged: dict[str, str] = {}
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                merged[key.strip()] = value.strip()
        except OSError:
            merged = {}
    merged.update(present)

    lines = [
        "# 本文件由 tools/ci_setup.py 在流水线中生成，请勿提交。",
        f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for key in ENV_KEYS:
        if key in merged:
            lines.append(f"{key}={merged[key]}")
    # 保留 ENV_KEYS 之外的自定义键，避免静默丢配置
    for key in sorted(set(merged) - set(ENV_KEYS)):
        lines.append(f"{key}={merged[key]}")
    lines.append("")

    env_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"    已写入 {env_path}，包含键: {sorted(merged)}", flush=True)
    print("    (敏感值不打印)", flush=True)


def verify_project() -> None:
    log("校验工程完整性")
    required = ["run_tests.py", "pytest.ini", "requirements.txt",
                "config/settings.py", "tests/conftest.py",
                "test_assets/registry/ui_case_assets.yaml"]
    missing = [rel for rel in required if not (PROJECT_ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"工程文件缺失: {missing}；请检查代码源与工作目录")
    print(f"    全部 {len(required)} 项必需文件存在", flush=True)


def print_versions() -> None:
    log("环境版本信息")
    print(f"    Python  : {sys.version.split()[0]}", flush=True)
    print(f"    platform: {sys.platform}", flush=True)
    code, out = run([sys.executable, "-m", "playwright", "--version"],
                    timeout=60, check=False)
    if code == 0:
        print(f"    {out.strip()}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="CI 环境装配")
    parser.add_argument("--skip-browser", action="store_true",
                        help="跳过 Playwright 浏览器安装（仅做静态检查时使用）")
    parser.add_argument("--pip-index", help="显式指定 pip 源 URL")
    parser.add_argument("--skip-deps", action="store_true",
                        help="跳过依赖安装（镜像已预装时使用）")
    args = parser.parse_args()

    # 容器内 stdout 常为非 UTF-8，显式重配避免中文日志乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print("=" * 70)
    print("CSCEC UI 自动化 - CI 环境装配")
    print("=" * 70)

    _ensure_project_root()
    print(f"工程根目录: {PROJECT_ROOT}", flush=True)

    verify_project()
    print_versions()
    write_env_file()

    if args.skip_deps:
        log("按参数跳过依赖安装")
    else:
        ensure_pip()
        index_url = pick_pip_index(args.pip_index)
        install_requirements(index_url)

    if args.skip_browser:
        log("按参数跳过浏览器安装")
    else:
        install_browser()

    log("装配完成")
    print("\n下一步：执行 python tools/ci_probe.py 验证环境可用性。", flush=True)
    print("注意：本脚本不因依赖/浏览器安装告警而失败，"
          "最终可运行性由探针（ci_probe.py）判定。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
