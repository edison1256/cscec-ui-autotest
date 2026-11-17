"""打通「进入某租户的工作台」黑盒链路，并取证「被订阅的订单」数据范围。

用户 2026-11-17 明确的空间架构：
  控制台空间 = irp 域，**与工作台空间不联通**，进不去工作台
  工作台空间 = cloud 域，进入方式**只有一种**：
      访问门户 → 右上角「管理后台」→ 选「工作台」→ 右上角显示名 → 切换租户

因此「被订阅的订单」这类工作台卡片，必须在**工作台空间的某个租户**下访问，
不能从 irp 控制台找（我上一版就错在这里）。

全程点击，只有登录与门户首页用 goto。
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/coverage-gaps/_workspace_chain.json")


def snap(page, tag: str) -> None:
    try:
        d = Path("reports/coverage-gaps")
        d.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(d / f"_ws-{tag}.png"), full_page=True)
    except Exception:
        pass


def info(page) -> dict:
    try:
        v = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


def brief(page) -> dict:
    i = info(page)
    return {
        "url": page.url[:160],
        "orgNo": i.get("orgNo"),
        "orgName": i.get("orgName"),
        "tenantNo": i.get("tenantNo"),
        "tenantName": i.get("tenantName"),
    }


def click_first(page, labels: list[str], wait: int = 3000) -> str | None:
    for lb in labels:
        for factory in (
            lambda l=lb: page.get_by_role("menuitem", name=l, exact=True).last,
            lambda l=lb: page.get_by_role("link", name=l, exact=True).last,
            lambda l=lb: page.get_by_text(l, exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=1800):
                    loc.click()
                    page.wait_for_timeout(wait)
                    return lb
            except Exception:
                continue
    return None



def click_dropdown_item(page, label: str, wait: int = 6000) -> bool:
    """点「管理后台」popover 里的菜单项。

    2026-11-17 DOM 实测：下拉是 Ant Design popover，
        .ant-popover-inner-content > .switch_all_wrap > span.rightItem(:text)
    页面其它区域也有同名文字（左侧导航、标题），按坐标或 .last 会点错，
    必须限定在 popover 容器内。
    """
    popover = page.locator(".ant-popover-inner-content").first
    if not popover.count():
        return False
    target = popover.get_by_text(label, exact=True).first
    if not target.count():
        return False
    try:
        target.click()
        page.wait_for_timeout(wait)
        return True
    except Exception:
        return False


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "steps": {}}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        captured: list[dict] = []

        def on_resp(resp):
            low = resp.url.lower()
            if "apply/history/list" not in low and "order/page" not in low:
                return
            item = {"url": resp.url[:190], "status": resp.status}
            try:
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else None
                if isinstance(data, dict):
                    rows = data.get("list") or data.get("records") or data.get("rows")
                    item["total"] = data.get("total")
                    if isinstance(rows, list):
                        item["len"] = len(rows)
                        dist = {}
                        for f in ("tenantNo", "tenantName", "creator", "userName"):
                            vals = [str(x.get(f)) for x in rows
                                    if isinstance(x, dict) and x.get(f) is not None]
                            if vals:
                                c = Counter(vals)
                                dist[f] = {"unique": len(c), "top": c.most_common(4)}
                        item["dist"] = dist
            except Exception:
                return
            captured.append(item)

        page.on("response", on_resp)

        try:
            # 1) 门户
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            r["steps"]["1_portal"] = brief(page)
            print("1) 门户:", json.dumps(r["steps"]["1_portal"], ensure_ascii=False))

            # 2) 右上角「管理后台」
            mgr = page.get_by_text("管理后台", exact=True).last
            r["steps"]["2_manager_found"] = bool(mgr.count())
            if mgr.count():
                try:
                    mgr.hover()
                except Exception:
                    mgr.click()
                page.wait_for_timeout(2200)
            try:
                body = page.locator("body").inner_text()
            except Exception:
                body = ""
            r["steps"]["2_dropdown"] = [
                x.strip() for x in body.splitlines()
                if x.strip() in ("控制台", "工作台", "开发者平台", "管理后台")
            ]
            snap(page, "02-manager")
            print("2) 管理后台下拉:", r["steps"]["2_dropdown"])

            # 3) 选「工作台」（可能新开标签页）
            pages_before = len(ctx.pages)
            picked = "工作台" if click_dropdown_item(page, "工作台", 7000) else None
            r["steps"]["3_pages_delta"] = len(ctx.pages) - pages_before
            if len(ctx.pages) > pages_before:
                page = ctx.pages[-1]
                # 换页签后必须重新挂监听，否则新页的响应全部漏掉
                page.on("response", on_resp)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)
            r["steps"]["3_picked_workbench"] = picked
            r["steps"]["3_after"] = brief(page)
            print("3) 点工作台:", picked, "->", json.dumps(r["steps"]["3_after"], ensure_ascii=False))
            snap(page, "03-workbench")

            # 4) 显示名 → 切换租户
            name = info(page).get("userName")
            if name:
                loc = page.get_by_text(name, exact=True).first
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2200)
            sw = click_first(page, ["切换租户"], 3500)
            r["steps"]["4_switch_clicked"] = sw
            try:
                body = page.locator("body").inner_text()
            except Exception:
                body = ""
            tenants = [x.strip() for x in body.splitlines()
                       if 3 <= len(x.strip()) <= 30 and ("租户" in x or "空间" in x)]
            r["steps"]["4_tenants"] = tenants[:10]
            snap(page, "04-switcher")
            print("4) 切换租户:", sw, "候选:", r["steps"]["4_tenants"][:6])

            # 5) 选一个工作台租户（跳过创建租户）
            target = None
            for t in r["steps"]["4_tenants"]:
                if "创建租户" in t or t == "切换租户":
                    continue
                target = t
                break
            r["steps"]["5_target_tenant"] = target
            if target:
                click_first(page, [target], 7000)
            r["steps"]["5_after"] = brief(page)
            print("5) 进租户:", target, "->", json.dumps(r["steps"]["5_after"], ensure_ascii=False))
            snap(page, "05-tenant")

            # 5.5) 切租户后会回到门户首页，需带着新租户身份重新进「工作台」
            page.wait_for_timeout(2500)
            try:
                body = page.locator("body").inner_text()
            except Exception:
                body = ""
            if "常用模块" not in body:
                mgr2 = page.get_by_text("管理后台", exact=True).last
                if mgr2.count():
                    try:
                        mgr2.hover()
                    except Exception:
                        mgr2.click()
                    page.wait_for_timeout(2000)
                pb2 = len(ctx.pages)
                again = "工作台" if click_dropdown_item(page, "工作台", 8000) else None
                if len(ctx.pages) > pb2:
                    page = ctx.pages[-1]
                    page.on("response", on_resp)
                    page.wait_for_timeout(3500)
                r["steps"]["5b_pages_delta"] = len(ctx.pages) - pb2
                r["steps"]["5b_reenter_workbench"] = again
                r["steps"]["5b_after"] = brief(page)
                print("5b) 重新进工作台:", again, "->", json.dumps(r["steps"]["5b_after"], ensure_ascii=False))

            # 6) 等常用模块，点「被订阅的订单」
            for _ in range(30):
                try:
                    body = page.locator("body").inner_text()
                except Exception:
                    body = ""
                if "常用模块" in body:
                    break
                page.wait_for_timeout(500)
            r["steps"]["6_has_modules"] = "常用模块" in body
            captured.clear()
            picked2 = click_first(page, ["被订阅的订单"], 7000)
            r["steps"]["6_clicked_subscribed"] = picked2
            page.wait_for_timeout(3000)
            r["steps"]["6_after"] = brief(page)
            r["steps"]["6_apis"] = captured[:4]
            snap(page, "06-subscribed")
            print("6) 被订阅的订单:", picked2, "->", json.dumps(r["steps"]["6_after"], ensure_ascii=False))
            for a in r["steps"]["6_apis"]:
                print("   api:", a["url"][:110], "total=", a.get("total"), "len=", a.get("len"))
                for f, d in (a.get("dist") or {}).items():
                    print(f"     {f}: unique={d['unique']} top={d['top'][:3]}")

        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
            r["url_at_failure"] = page.url[:180]
            snap(page, "99-failed")
            print("!! 异常:", r["error"])
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
