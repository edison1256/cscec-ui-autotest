"""定位「管理后台」下拉项的正确选择器（只诊断，不做业务断言）。

上一版问题：页面有多个「工作台」文本，按坐标打分仍点错，命中了左侧「开发者平台」。
本脚本打印所有同名元素的坐标与祖先 class，以及下拉面板候选容器。
"""

import json
import sys

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        try:
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            mgr = page.get_by_text("管理后台", exact=True).last
            print(f"管理后台 count={mgr.count()} box={mgr.bounding_box()}")
            mgr.hover()
            page.wait_for_timeout(2500)

            print("\n=== 所有「工作台」元素 ===")
            locs = page.get_by_text("工作台", exact=True)
            n = locs.count()
            print(f"count={n}")
            for i in range(n):
                el = locs.nth(i)
                try:
                    vis = el.is_visible()
                    box = el.bounding_box()
                    ancestors = el.evaluate(
                        "e => { const out=[]; let p=e; for(let k=0;k<4&&p;k++){"
                        " out.push(p.tagName+(p.className&&typeof p.className==='string'"
                        " ? '.'+p.className.trim().split(/\\s+/).join('.') : '')); p=p.parentElement;}"
                        " return out; }"
                    )
                    print(f" [{i}] visible={vis} box={box}")
                    print(f"      ancestors={ancestors}")
                except Exception as exc:  # noqa: BLE001
                    print(f" [{i}] err {exc}")

            print("\n=== 含「控制台」的祖先容器（下拉面板候选）===")
            ctrl = page.get_by_text("控制台", exact=True)
            print(f"控制台 count={ctrl.count()}")
            for i in range(min(ctrl.count(), 4)):
                el = ctrl.nth(i)
                try:
                    box = el.bounding_box()
                    ancestors = el.evaluate(
                        "e => { const out=[]; let p=e; for(let k=0;k<5&&p;k++){"
                        " out.push(p.tagName+(p.className&&typeof p.className==='string'"
                        " ? '.'+p.className.trim().split(/\\s+/).join('.') : '')); p=p.parentElement;}"
                        " return out; }"
                    )
                    print(f" [{i}] visible={el.is_visible()} box={box}")
                    print(f"      ancestors={ancestors}")
                except Exception as exc:  # noqa: BLE001
                    print(f" [{i}] err {exc}")

            page.screenshot(path="reports/coverage-gaps/_diag-dropdown.png", full_page=True)
            print("\n截图: reports/coverage-gaps/_diag-dropdown.png")

        finally:
            ctx.close()
            b.close()


if __name__ == "__main__":
    main()
