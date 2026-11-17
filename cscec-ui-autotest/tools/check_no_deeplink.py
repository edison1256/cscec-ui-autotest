"""禁止直链功能页的静态检查（可进 CI）。

规则（用户 2026-11-17 明确，且此前多次强调）：
    **不要从不知道哪来的 URL 直链过去，必须模拟黑盒点击操作。**

背景：直链会绕过路由守卫与菜单渲染，进到该账号本不该有的套件/视图，
看到的可能是越权数据。用它下结论会得到相反答案。真实案例：
  - 直链 `#/sub/resource/subscription/app/appInfo?suitKey=1899...727`
    进入不该有的套件，看到其他租户数据
  - 直链 `#/portal/home/workbench?suitKey=portal`
    绕过了「门户 → 显示名 → 切换租户」的视图选择

判定：`goto` / `goto_url` 的目标若包含 SPA 路由片段（`#/`）或套件参数
（`suitKey=`），一律视为违规。允许的只有「登录入口」（等价于用户手动输入
网站地址进入系统）。

豁免方式：行尾加 `# noqa: deeplink  原因`。

用法：
    python tools/check_no_deeplink.py            # 检查，违规则 exit 1
    python tools/check_no_deeplink.py --verbose  # 输出每条调用
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("pages", "tests")
SCAN_FILES = ("run_tests.py", "conftest.py")

# goto 系列调用
CALL_RE = re.compile(r"\b(goto|goto_url|goto_path)\s*\(")
# 违规片段
DEEPLINK_RE = re.compile(r"#/|suitKey=")
# 登录入口白名单（等价于用户在浏览器输入站点地址）
LOGIN_WHITELIST = (
    "ADMIN_LOGIN_ROUTE",
    "ADMIN_LOGIN_URL",
    "/udpweb/portal/index.html#/login",
    "cas/login",
    "passport/login",
    "BASE_URL",
    "PORTAL_BASE_URL",
    "CONSOLE_BASE_URL",
)
NOQA = "# noqa: deeplink"


def route_constants() -> dict[str, str]:
    """收集工程里含路由片段的常量定义，供变量引用检测。"""
    found: dict[str, str] = {}
    pattern = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+)$", re.M)
    for path in list(PROJECT.glob("config/*.py")) + list(PROJECT.glob("pages/**/*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for name, value in pattern.findall(text):
            if DEEPLINK_RE.search(value) and "login" not in value.lower():
                found[name] = f"{path.relative_to(PROJECT)}:{name}"
    return found


def scan_file(path: Path, consts: dict[str, str], verbose: bool) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    problems: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if CALL_RE.search(line) is None:
            continue
        if NOQA in line:
            continue
        # 取调用语句（跨行拼接：从当前行到括号平衡或最多 6 行）
        snippet = " ".join(lines[idx - 1: idx + 5])
        if verbose:
            print(f"  [call] {path.relative_to(PROJECT)}:{idx}")

        is_login = any(w in snippet for w in LOGIN_WHITELIST)
        hit_literal = bool(DEEPLINK_RE.search(snippet))
        hit_const = [n for n in consts if n in snippet]

        if is_login and not hit_const:
            continue
        if hit_literal or hit_const:
            detail = []
            if hit_literal:
                detail.append("含 #/ 或 suitKey=")
            if hit_const:
                detail.append(f"引用了路由常量 {hit_const}")
            problems.append(
                f"{path.relative_to(PROJECT)}:{idx}  ->  {line.strip()[:110]}"
                f"\n      违规原因: {'；'.join(detail)}"
                f"\n      修法: 改为模拟点击（菜单/卡片/切换租户），登录入口除外"
            )
    return problems


def main() -> int:
    verbose = "--verbose" in sys.argv
    consts = route_constants()
    if verbose:
        print(f"发现 {len(consts)} 个路由常量: {sorted(consts)}\n")

    problems: list[str] = []
    targets: list[Path] = []
    for d in SCAN_DIRS:
        targets.extend(sorted((PROJECT / d).rglob("*.py")))
    for f in SCAN_FILES:
        p = PROJECT / f
        if p.exists():
            targets.append(p)

    print(f"扫描 {len(targets)} 个文件…\n")
    for path in targets:
        if "__pycache__" in str(path):
            continue
        problems.extend(scan_file(path, consts, verbose))

    if not problems:
        print("OK 未发现直链功能页的调用")
        return 0

    print(f"!! 发现 {len(problems)} 处直链违规：\n")
    for p in problems:
        print(p)
        print()
    print(
        "规则：黑盒测试必须模拟用户点击（菜单 / 卡片 / 切换租户 / 管理后台），\n"
        "      禁止拼接 SPA 路由或套件参数直达功能页。\n"
        "      确属登录入口才可豁免，写法：行尾加 `# noqa: deeplink 原因`。"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
