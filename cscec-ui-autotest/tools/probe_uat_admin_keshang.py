"""用管理员后门登录态验证：客商管理菜单 + 租户审批入口是否可达（只读）。

前置：ENV=uat python tools/refresh_admin_auth.py 已生成 auth_states/admin-uat.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402

OUT = Path("reports/keshang/_admin_recon.json")
SHOT = Path("reports/keshang")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_admin-{tag}.png"), full_page=True)
    except Exception:
        pass


def body(page, n: int = 2000) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 2500) -> bool:
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_text(label, exact=True).last,
    ):
        try:
            loc = factory()
            if loc.count() and loc.is_visible(timeout=2500):
                loc.click()
                page.wait_for_timeout(wait)
                return True
        except Exception:
            continue
    return False


def main() -> None:
    if settings.ENV != "uat":
        raise SystemExit("必须 ENV=uat")

    state = settings.admin_auth_state_file
    if not state.exists():
        raise SystemExit(f"管理员登录态缺失: {state}")

    r = {"state_file": str(state)}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            viewport={"width": 1680, "height": 1100},
            ignore_https_errors=True,
            storage_state=str(state),
        )
        page = ctx.new_page()
        page.set_default_timeout(25000)

        page.goto(settings.CONSOLE_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        r["landing_url"] = page.url[:200]
        txt = body(page)
        r["logged_in"] = "cas/login" not in page.url.lower() and "登录" not in txt[:200]
        r["has_keshang_word"] = "客商" in txt

        # 权限管理 -> 客商管理
        r["perm_clicked"] = click_text(page, "权限管理", 2200)
        perm = body(page)
        r["perm_lines"] = [x.strip() for x in perm.splitlines() if x.strip()][:40]
        snap(page, "perm")

        r["keshang_clicked"] = click_text(page, "客商管理", 3500)
        if r["keshang_clicked"]:
            k = body(page, 2500)
            r["keshang_url"] = page.url[:220]
            r["keshang_body"] = k[:1500]
            r["keshang_lines"] = [x.strip() for x in k.splitlines() if x.strip()][:60]
            snap(page, "keshang")

        # 审批中心 / 审批流程 下是否有租户申请
        r["flow_clicked"] = click_text(page, "审批流程", 2500)
        flow = body(page, 2000)
        r["flow_lines"] = [x.strip() for x in flow.splitlines() if x.strip()][:40]
        r["has_tenant_apply"] = any(w in flow for w in ("租户申请", "创建租户", "租户审批"))
        snap(page, "flow")

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("logged_in:", r["logged_in"], "| has客商:", r["has_keshang_word"])
    print("权限管理展开:", r["perm_lines"][:20])
    print("客商管理 clicked:", r["keshang_clicked"], "->", r.get("keshang_url", "")[:110])
    print("客商页文本:", (r.get("keshang_body") or "")[:300].replace("\n", " / "))
    print("审批流程 has租户申请:", r["has_tenant_apply"])
    print("审批页文本:", " / ".join(r["flow_lines"][:15]))
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
