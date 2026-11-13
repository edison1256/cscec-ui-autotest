"""精准探测：控制台左侧「订阅服务」「资源管理」展开后的子项。

前一次全量探测的差分逻辑有误（与 baseline 比而非上一轮比），
这里只针对两个一级菜单单独展开并 dump 全部文本与截图。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_menu_sub.json")
TARGETS = ["订阅服务", "资源管理", "计量统计"]


def dump(page, tag: str) -> dict:
    try:
        txt = page.locator("body").inner_text()
    except Exception:
        txt = ""
    lines = [x.strip() for x in txt.splitlines() if x.strip()]
    d = {
        "url": page.url[:180],
        "first60": lines[:60],
        "body_head": txt[:900],
    }
    try:
        page.screenshot(
            path=str(Path("reports/prod-keshang") / f"_menu-{tag}.png"), full_page=True
        )
    except Exception:
        pass
    return d


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {}
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

        for top in TARGETS:
            try:
                loc = page.get_by_text(top, exact=True).last
                if not loc.count():
                    r[top] = {"error": "menu not found"}
                    continue
                loc.click()
                page.wait_for_timeout(2500)
                r[top] = dump(page, top)
                print(f"\n[{top}] url={r[top]['url'][:110]}", flush=True)
                print("  lines:", r[top]["first60"][:30], flush=True)
            except Exception as exc:  # noqa: BLE001
                r[top] = {"error": f"{type(exc).__name__}: {exc}"[:180]}
                print(f"[{top}] ERR {r[top]['error']}", flush=True)

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
