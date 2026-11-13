"""逐个采集订阅服务/资源管理叶子的真实路由与列表接口。

每轮先回工作台首页，保证左侧菜单回到初始态，避免上一次点击后页面切走导致
后续定位失败（上一轮实测「应用列表」「API管理」均因此超时）。

输出用于更新 SUBSCRIPTION_LEAVES 的 route_pattern / list_api_pattern。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_leaf_matrix.json")

CASES = [
    ("订阅服务", "应用列表"),
    ("订阅服务", "云产品列表"),
    ("订阅服务", "API列表"),
    ("订阅服务", "组件列表"),
    ("订阅服务", "数据资产列表"),
    ("资源管理", "API管理"),
]


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"cases": {}}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1200}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        urls = []
        page.on(
            "response",
            lambda resp: urls.append(f"{resp.status} {resp.request.method} {resp.url}"),
        )

        LoginPage(page).login()
        page.wait_for_timeout(3000)
        home = page.url

        for top, leaf in CASES:
            key = f"{top}>{leaf}"
            urls.clear()
            info = {}
            try:
                # 每轮回首页，保证菜单状态干净
                page.goto(home, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3500)
                t = page.get_by_text(top, exact=True).last
                if t.count():
                    t.click()
                    page.wait_for_timeout(1800)
                leaf_loc = page.get_by_text(leaf, exact=True).last
                if not leaf_loc.count():
                    info["error"] = "leaf not found"
                else:
                    leaf_loc.click(timeout=8000)
                    page.wait_for_timeout(6000)
                    info["url"] = page.url[:220]
                    info["api_calls"] = [
                        u
                        for u in urls
                        if any(k in u for k in ("/irp-api/", "/workflow/", "/metrology/"))
                    ][:12]
            except Exception as exc:  # noqa: BLE001
                info["error"] = f"{type(exc).__name__}: {exc}"[:160]
            r["cases"][key] = info
            u = (info.get("url") or "")
            frag = u.split("#", 1)[1].split("?", 1)[0] if "#" in u else ""
            print(f"[{key}] route={frag} apis={len(info.get('api_calls') or [])}", flush=True)
            for a in (info.get("api_calls") or [])[:3]:
                print("    ", a[:140], flush=True)
            if info.get("error"):
                print("    ERR:", info["error"], flush=True)

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
