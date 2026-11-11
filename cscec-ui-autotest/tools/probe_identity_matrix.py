#!/usr/bin/env python3
"""身份矩阵只读盘点（阶段 0）。

用途：在环境数据重刷后，确认「谁能管哪些租户、有什么角色、菜单什么形态、
      业务锚点是否还在」。**全程只读，不产生任何写请求。**

用法：
    python tools/probe_identity_matrix.py --env uat --account admin
    python tools/probe_identity_matrix.py --env uat --account main

设计要点：
- 复用 ``auth_states/admin-<env>.json`` 或 ``auth_states/<env>.json`` 登录态。
- 所有网络请求挂在 page.on("response") 上被动采集，不主动调写接口。
- 菜单形态用页面文本判定，与 tests/metering_subscription_260901/helpers.py
  的 workbench_tenant_shape 保持同一判据。
- 失败时落截图 + HTML 到 reports/identity-matrix/ 下，不靠猜。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ROOT_MARKERS = ("run_tests.py", "pytest.ini", "config/settings.py")


def _ensure_project_root() -> None:
    import os

    if all((PROJECT_ROOT / m).exists() for m in ROOT_MARKERS):
        os.chdir(PROJECT_ROOT)
        return
    cwd = Path.cwd()
    for depth in range(1, 4):
        pattern = "/".join(["*"] * depth) + "/run_tests.py"
        for candidate in sorted(cwd.glob(pattern)):
            root = candidate.parent
            if all((root / m).exists() for m in ROOT_MARKERS):
                os.chdir(root)
                return
    raise SystemExit("无法定位工程根目录")


_ensure_project_root()

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402

OUT_DIR = settings.REPORTS_DIR / "identity-matrix"

# 业务锚点（来自 tests/metering_subscription_260901/helpers.py）
ANCHORS = {
    "ANCHOR_RESOURCE_WPS": "WPS服务组件",
    "ANCHOR_RESOURCE_TAG": "标签中心",
    "ANCHOR_RESOURCE_PERMANENT": "中建云0731组件",
    "ANCHOR_TENANT_NAME": "技术与大数据平台项目组",
    "ANCHOR_TENANT_NO": "ZH_01_0000_0001_0001",
    "ANCHOR_ORDER_ID": "PO2025103015352000",
    "ANCHOR_APPLY_APP": "IRP_中建云项目",
    "CS_ANCHOR_RESOURCE": "实际控制人",
    "CS_ANCHOR_APP": "国资委审计专用",
}

# 菜单形态判据（与 helpers.workbench_tenant_shape 一致）
SHAPE_MARKERS = {
    "sz": "订阅中心",      # 租户管理员形态
    "zjy": "我的订阅",     # 普通成员形态
    "console": "订阅服务",  # 控制台平台运营形态
}
EXTRA_MENU_TOKENS = ("管理后台", "系统管理", "权限管理", "租户管理", "角色管理", "运营中心")


def _dump(page, diag: Path, tag: str) -> None:
    try:
        (diag / f"{tag}.png").write_bytes(page.screenshot(full_page=True))
    except Exception:  # noqa: BLE001
        pass
    try:
        (diag / f"{tag}.html").write_text(page.content(), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _collect_tenant_list(page) -> dict:
    """打开右上角账号 hover → 切换租户，抓取租户列表（只读点击）。"""
    result = {"opened": False, "tenants": [], "hover_labels": []}
    # 账号 hover 面板可能的锚点
    for cand in ("[class*='avatar']", "[class*='user']", "[class*='header']"):
        try:
            loc = page.locator(cand).first
            if not loc.count() or not loc.is_visible(timeout=1500):
                continue
            loc.hover(timeout=3000)
            page.wait_for_timeout(1200)
            labels = loc.evaluate(
                "e => [e, e.parentElement, e.parentElement && e.parentElement.parentElement]"
                " .filter(Boolean).map(n => n.innerText)"
            )
            result["hover_labels"] = [str(x)[:400] for x in labels if x]
            break
        except Exception:  # noqa: BLE001
            continue

    # 点开「切换租户」
    try:
        sw = page.get_by_text("切换租户", exact=True).first
        if sw.count() and sw.is_visible(timeout=2000):
            sw.click()
            page.wait_for_timeout(2000)
            result["opened"] = True
    except Exception:  # noqa: BLE001
        pass

    if result["opened"]:
        try:
            items = page.locator("[class*='tenant_item_text']").all()
            for it in items:
                try:
                    txt = (it.inner_text() or "").strip()
                    if txt:
                        result["tenants"].append(txt)
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
    return result


def _shape_of(body: str) -> list[str]:
    return [k for k, token in SHAPE_MARKERS.items() if token in body]


def run_probe(env: str, account: str, headless: bool = True) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    diag = OUT_DIR / f"diag-{env}-{account}-{stamp}"
    diag.mkdir(parents=True, exist_ok=True)

    state_file = (
        settings.admin_auth_state_file if account == "admin" else settings.auth_state_file
    )
    if not state_file.exists():
        raise SystemExit(f"登录态不存在: {state_file}（先登录一次再盘点）")

    report: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "env": env,
        "account_kind": account,
        "auth_state": str(state_file),
        "anchors": ANCHORS,
        "pages": {},
        "api": {},
        "menus": {},
        "write_affordances": {},
    }

    api_hits: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport=settings.VIEWPORT,
            ignore_https_errors=True,
            storage_state=str(state_file),
        )
        page = ctx.new_page()

        def on_resp(resp):
            url = resp.url
            interesting = any(
                k in url
                for k in (
                    "/tenant/view", "/tenant/findAll", "/tenant/viewBatch",
                    "/tenant-role/pageConsole", "/tenant-role/pageMembers",
                    "/basedata/user/getUserInfoForPortal",
                    "/tenant-member/page",
                )
            )
            if not interesting:
                return
            try:
                body = resp.text()[:4000]
            except Exception:  # noqa: BLE001
                body = "<unreadable>"
            api_hits.append({"status": resp.status, "url": url[:300], "body": body})

        page.on("response", on_resp)

        # ---- 1. 工作台 ----
        wb = settings.WORKBENCH_BASE_URL
        try:
            page.goto(wb, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text()
            report["pages"]["workbench"] = {
                "url": page.url,
                "shapes": _shape_of(body),
                "menus_found": [t for t in EXTRA_MENU_TOKENS if t in body],
                "body_head": body[:1500],
            }
            report["login_info"] = page.evaluate(
                "() => { try { return JSON.parse(localStorage.getItem('__login_info__')) } catch(e) { return null } }"
            )
            report["menus"]["tenants"] = _collect_tenant_list(page)
            _dump(page, diag, "01-workbench")
        except Exception as exc:  # noqa: BLE001
            report["pages"]["workbench"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            _dump(page, diag, "01-workbench-error")

        # ---- 2. 控制台 ----
        try:
            page.goto(settings.CONSOLE_BASE_URL, wait_until="domcontentloaded",
                      timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text()
            report["pages"]["console"] = {
                "url": page.url,
                "menus_found": [t for t in EXTRA_MENU_TOKENS if t in body],
                "body_head": body[:1500],
            }
            _dump(page, diag, "02-console")
        except Exception as exc:  # noqa: BLE001
            report["pages"]["console"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            _dump(page, diag, "02-console-error")

        # ---- 3. 租户管理页：确认能否进入 + 写按钮是否可用 ----
        try:
            page.goto(
                settings.CONSOLE_BASE_URL.rstrip("/")
                + "/udpweb/portal/index.html#/sub/resource/systemManage/tenantManage",
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(5000)
            body = page.locator("body").inner_text()
            afford = {}
            for label in ("添加租户成员", "待加入成员", "批量移出", "添加成员", "创建角色", "添加"):
                try:
                    loc = page.get_by_role("button", name=label, exact=True).first
                    if loc.count():
                        afford[label] = {
                            "visible": loc.is_visible(),
                            "enabled": loc.is_enabled(),
                        }
                except Exception:  # noqa: BLE001
                    continue
            report["write_affordances"]["tenant_manage"] = afford
            report["pages"]["tenant_manage"] = {
                "url": page.url,
                "body_head": body[:2000],
                "hit_expected_tenant": "中建云（ZH_01_0000）" in body,
            }
            _dump(page, diag, "03-tenant-manage")
        except Exception as exc:  # noqa: BLE001
            report["pages"]["tenant_manage"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            _dump(page, diag, "03-tenant-manage-error")

        # ---- 4. 锚点存活初判（只在工作台正文里找，不发起业务查询）----
        try:
            page.goto(wb, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_timeout(3000)
            body = page.locator("body").inner_text()
            report["anchors_seen_on_workbench"] = {
                k: (v in body) for k, v in ANCHORS.items()
            }
        except Exception:  # noqa: BLE001
            pass

        ctx.close()
        browser.close()

    report["api"] = {"hits": api_hits[:80]}
    report["diag_dir"] = str(diag)

    out = OUT_DIR / f"identity-matrix-{env}-{account}-{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["_out"] = str(out)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="身份矩阵只读盘点")
    parser.add_argument("--env", default=None, choices=["uat", "pre", "prod"])
    parser.add_argument("--account", default="admin", choices=["admin", "main"])
    parser.add_argument("--headed", action="store_true", help="有头模式，便于观察")
    args = parser.parse_args()

    if args.env:
        import importlib
        import os

        os.environ["ENV"] = args.env
        # 注意：config 包的 __init__ 会导出 settings 实例，遮蔽同名子模块，
        # 因此不能用 `import config.settings as _s`，必须用 import_module 取模块本体。
        mod = importlib.import_module("config.settings")
        mod = importlib.reload(mod)
        globals()["settings"] = mod.settings

    report = run_probe(settings.ENV, args.account, headless=not args.headed)

    print("=" * 70)
    print(f"身份盘点 {settings.ENV} / {args.account}")
    print("=" * 70)
    info = report.get("login_info") or {}
    print(f"  账号    : {info.get('userNo')} / {info.get('userName')}")
    print(f"  组织    : {info.get('orgNo')} / {info.get('orgName')}")
    print(f"  租户    : {info.get('tenantId')} / {info.get('tenantNo')} / {info.get('tenantName')}")
    wb = report["pages"].get("workbench", {})
    print(f"  工作台形态: {wb.get('shapes')} 菜单: {wb.get('menus_found')}")
    tenants = (report["menus"].get("tenants") or {})
    print(f"  可切换租户: {tenants.get('tenants')}")
    cs = report["pages"].get("console", {})
    print(f"  控制台菜单: {cs.get('menus_found')}")
    tm = report["pages"].get("tenant_manage", {})
    print(f"  租户管理页: {tm.get('url', tm.get('error'))}")
    print(f"  期望租户命中: {tm.get('hit_expected_tenant')}")
    print(f"  写按钮能力: {json.dumps(report['write_affordances'], ensure_ascii=False)}")
    seen = report.get("anchors_seen_on_workbench") or {}
    print(f"  锚点命中: {[k for k, v in seen.items() if v] or '无'}")
    print(f"  诊断目录: {report['diag_dir']}")
    print(f"  结果文件: {report['_out']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
