#!/usr/bin/env python3
"""CI daily test 执行入口：按流水线参数运行指定范围的 UI 自动化用例。

职责：
- 把流水线参数（环境、范围、重试）翻译成 pytest 命令。
- 刷新登录态（可选）。
- 汇总结果并输出到构建机日志与归档目录，保证退出码语义正确。

退出码：
    0 = 全部通过（允许有 skip / NOT_APPLICABLE）
    1 = 存在真实失败
    2 = 环境或参数错误（未真正执行用例）

用法：
    python tools/ci_daily_test.py --env uat --scope readonly
    python tools/ci_daily_test.py --env uat --scope smoke --refresh-auth
    python tools/ci_daily_test.py --env prod --scope mandatory
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 工程根判定标记（三个齐全才认为是真正的工程根）
ROOT_MARKERS = ("run_tests.py", "pytest.ini", "config/settings.py")


def _ensure_project_root() -> None:
    """确保工作目录为工程根目录。

    蓝盾「拉取代码」插件默认把仓库 checkout 到 workspace 的**子目录**（仓库名），
    而 Task 的初始 CWD 是 workspace 根，因此直接调用 `python3 tools/ci_daily_test.py`
    会报 "can't open file"。这里自动定位并切换，使脚本在任意层级被调用都能运行。
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


REPORTS_DIR = PROJECT_ROOT / "reports"
ARCHIVE_DIR = REPORTS_DIR / "ci"

SCOPES = {
    "static": {
        "markers": None,
        "dry_run": True,
        "description": "静态校验：只收集用例，不访问业务页面",
    },
    "smoke": {
        "markers": "smoke and readonly",
        "dry_run": False,
        "description": "冒烟：核心只读路径",
    },
    "readonly": {
        "markers": "readonly",
        "dry_run": False,
        "description": "全量只读回归：不产生业务写入",
    },
    "regression": {
        "markers": "regression and readonly",
        "dry_run": False,
        "description": "回归只读范围",
    },
    "mandatory": {
        "markers": "prod_mandatory and readonly",
        "dry_run": False,
        "description": "生产严格门禁（仅 prod 有意义）",
    },
    "conditional": {
        "markers": "prod_conditional and readonly",
        "dry_run": False,
        "description": "生产条件用例（仅 prod 有意义）",
    },
}


def log(message: str) -> None:
    print(f"\n>>> {message}", flush=True)


def run(cmd: list[str], timeout: int = 7200) -> int:
    print(f"    $ {' '.join(cmd)}", flush=True)
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    print(f"    exit={proc.returncode} ({time.monotonic() - started:.1f}s)", flush=True)
    return proc.returncode


def run_capture(cmd: list[str], timeout: int = 7200) -> tuple[int, str]:
    """执行命令，实时透传输出到构建日志，同时返回完整输出供解析。"""
    print(f"    $ {' '.join(cmd)}", flush=True)
    started = time.monotonic()
    proc = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    # 透传到构建日志，保留全部输出便于排查
    print(output, flush=True)
    print(f"    exit={proc.returncode} ({time.monotonic() - started:.1f}s)", flush=True)
    return proc.returncode, output


def project_python() -> str:
    """优先用工程 venv，其次当前解释器。"""
    if sys.platform == "win32":
        candidate = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def validate_env(target_env: str, scope: str) -> None:
    """执行前校验必需的环境变量与工程文件。

    static（dry-run 收集）不访问业务页面，因此不要求凭据。
    """
    log("执行前校验")

    for rel in ("run_tests.py", "pytest.ini", "tests"):
        if not (PROJECT_ROOT / rel).exists():
            raise SystemExit(f"环境错误: 工程文件缺失 {rel}")

    if SCOPES[scope]["dry_run"]:
        print(f"    范围 {scope} 为只收集模式，跳过凭据校验", flush=True)
        return

    if not os.getenv("USERNAME"):
        raise SystemExit("参数错误: 未设置 USERNAME（请在流水线环境变量中配置）")

    password_var = f"{target_env.upper()}_PASSWORD"
    if not (os.getenv(password_var) or os.getenv("PASSWORD")):
        raise SystemExit(f"参数错误: 未设置 {password_var} 或 PASSWORD")

    print(f"    ENV={target_env}，凭据已注入（值不打印）", flush=True)


def refresh_auth(env: str) -> int:
    log(f"刷新 {env.upper()} 登录态")
    return run([
        project_python(), "run_tests.py",
        "--env", env,
        "--refresh-auth",
        "-m", "login",
    ])


def execute(env: str, scope: str, extra_args: list[str]) -> tuple[int, int]:
    """执行 pytest，返回 (exit_code, 收集用例数)。"""
    config = SCOPES[scope]
    log(f"执行范围: {scope} — {config['description']}")

    collected_path = ARCHIVE_DIR / f"collected-{env}-{scope}.txt"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [project_python(), "run_tests.py", "--env", env]
    if config["markers"]:
        cmd.extend(["-m", config["markers"]])
    if config["dry_run"]:
        cmd.append("--dry-run")
    cmd.extend(extra_args)

    if not config["dry_run"]:
        cmd.extend([
            "--html", str(ARCHIVE_DIR / f"report-{env}-{scope}.html"),
            "--self-contained-html",
            f"--alluredir={ARCHIVE_DIR / 'allure-results'}",
        ])

    exit_code, output = run_capture(cmd)

    collected = _parse_collected(output)
    collected_path.write_text(
        f"collected={collected}\nexit_code={exit_code}\n", encoding="utf-8"
    )
    if collected is not None:
        print(f"    收集用例数: {collected}", flush=True)

    return exit_code, collected


def _parse_collected(output: str) -> int | None:
    """从 pytest 输出中解析收集用例数（形如 '513 tests collected'）。"""
    match = re.search(r"(\d+)\s+tests?\s+collected", output)
    if match:
        return int(match.group(1))
    match = re.search(r"collected\s+(\d+)\s+items?", output)
    return int(match.group(1)) if match else None


def summarize(env: str, scope: str, exit_code: int,
              collected: int | None = None) -> dict:
    """生成机器可读的 CI 摘要，供流水线后续步骤消费。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    contract_summary_path = REPORTS_DIR / "prod-console-contract-summary.json"
    contract_summary = None
    # dry-run（static）不执行用例，读残留摘要会把上次结果当成当前结果，必须跳过
    if not SCOPES[scope]["dry_run"] and contract_summary_path.exists():
        try:
            contract_summary = json.loads(
                contract_summary_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            contract_summary = None

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "env": env,
        "scope": scope,
        "scope_description": SCOPES[scope]["description"],
        "collected": collected,
        "exit_code": exit_code,
        "result": "PASSED" if exit_code == 0 else "FAILED",
        "pipeline": {
            "pipeline_id": os.getenv("BK_CI_PIPELINE_ID", ""),
            "build_id": os.getenv("BK_CI_BUILD_ID", ""),
            "build_num": os.getenv("BK_CI_BUILD_NUM", ""),
            "start_type": os.getenv("BK_CI_START_TYPE", ""),
            "trigger_user": os.getenv("BK_CI_PIPELINE_UPDATE_USER", ""),
        },
        "contract_summary": contract_summary,
    }

    out_path = ARCHIVE_DIR / f"ci-summary-{env}-{scope}.json"
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"    CI 摘要已写入: {out_path}", flush=True)

    # 打印到日志，便于在流水线页面直接看到结论
    print("\n" + "=" * 70, flush=True)
    print("CI 执行摘要", flush=True)
    print(f"  环境    : {env.upper()}", flush=True)
    print(f"  范围    : {scope} ({SCOPES[scope]['description']})", flush=True)
    if collected is not None:
        print(f"  收集用例: {collected}", flush=True)
    print(f"  结论    : {summary['result']}", flush=True)
    if contract_summary:
        for name, counts in contract_summary.get("classifications", {}).items():
            print(f"  契约[{name}]: passed={counts.get('passed', 0)} "
                  f"failed={counts.get('failed', 0)} "
                  f"n/a={counts.get('not_applicable', 0)} "
                  f"skipped={counts.get('skipped', 0)}", flush=True)
    print("=" * 70, flush=True)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="CI daily test 执行入口")
    parser.add_argument("--env", required=True, choices=["uat", "pre", "prod"],
                        help="目标环境")
    parser.add_argument("--scope", default="readonly", choices=sorted(SCOPES.keys()),
                        help="执行范围")
    parser.add_argument("--refresh-auth", action="store_true",
                        help="执行前强制刷新登录态")
    parser.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                        help="追加透传给 pytest 的参数")
    args = parser.parse_args()

    # 容器内 stdout 常为非 UTF-8，显式重配避免中文日志乱码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print("=" * 70)
    print("CSCEC UI 自动化 - CI daily test")
    print("=" * 70)

    try:
        _ensure_project_root()
    except SystemExit as exc:
        print(f"\n环境校验失败: {exc}", flush=True)
        return 2
    print(f"工程根目录: {PROJECT_ROOT}", flush=True)

    try:
        validate_env(args.env, args.scope)
    except SystemExit as exc:
        print(f"\n环境校验失败: {exc}", flush=True)
        return 2

    if args.refresh_auth:
        code = refresh_auth(args.env)
        if code != 0:
            print("\n登录态刷新失败，终止执行（避免用过期态跑出假失败）", flush=True)
            summarize(args.env, args.scope, code)
            return code

    exit_code, collected = execute(args.env, args.scope, args.extra)
    summarize(args.env, args.scope, exit_code, collected)

    # 收集数异常本身就是失败信号（用例被误删 / 标记错误）
    if collected is not None and collected == 0:
        print("\n结论: 收集到 0 条用例，选择器或标记配置有误。", flush=True)
        return 1

    if exit_code == 0:
        print("\n结论: 本次执行全部通过。", flush=True)
    else:
        print(f"\n结论: 存在失败用例（exit={exit_code}），请查看归档报告。", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
