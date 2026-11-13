"""生产只读探测：控制台左侧菜单树完整结构。

目的：把「API列表 / API资源」这类入口从「常用模块卡片」（运营可配、会变）
改为「左侧菜单树」（权限驱动、稳定）之前，先拿到真实层级与子项名称。

只展开菜单、不进入业务操作页。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_menu_tree.json")

TOP_MENUS = [
    "资源管理",
    "订阅服务",
    "审批流程",
    "评价中心",
    "系统配置",
    "流程",
    "订单中心",
    "工单中心",
    "运维监控",
    "运营管理",
    "权限管理",
    "计量统计",
    "收藏夹",
]


def snap_menu(page) -> list[str]:
    """抓 body 前 45 行短文本（菜单在 DOM 前部，足够覆盖左侧树）。"""
    try:
        txt = page.locator("body").inner_text()
    except Exception:
        return []
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    return [x for x in lines[:45] if 2 <= len(x) <= 14]


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"menus": {}}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1200}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        LoginPage(page).login()
        page.wait_for_timeout(3000)
        print("login ok", flush=True)

        r["baseline_menu"] = snap_menu(page)
        print("baseline:", r["baseline_menu"], flush=True)

        for top in TOP_MENUS:
            try:
                loc = page.get_by_text(top, exact=True).last
                if not loc.count():
                    r["menus"][top] = {"error": "not found"}
                    continue
                loc.click()
                page.wait_for_timeout(1800)
                items = snap_menu(page)
                # 只保留该一级菜单之后的部分（近似：去掉 baseline 里已有的）
                new_items = [x for x in items if x not in r["baseline_menu"]]
                r["menus"][top] = {"all": items, "new": new_items}
                print(f"  [{top}] new={new_items[:12]}", flush=True)
            except Exception as exc:  # noqa: BLE001
                r["menus"][top] = {"error": f"{type(exc).__name__}: {exc}"[:150]}

        page.screenshot(
            path=str(Path("reports/prod-keshang") / "_diag-menu-tree.png"), full_page=True
        )
        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
