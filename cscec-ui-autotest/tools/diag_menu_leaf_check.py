"""验证：从左侧菜单树进「订阅服务 → API列表」，看真实路由与接口。

同时验证「资源管理 → API管理」是否为 WB-007 期望的 API资源页。

判断标准：
  SUBSCRIPTION-API-001 期望 route=[#/]subscription/apiResource
                        api=/console/rsc/api/apply/history/list
  WB-007              期望 api=/irp-api/irp-portal-console/app/list-businessArea-app
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_menu_leaf_check.json")

CASES = [
    ("订阅服务", "API列表"),
    ("订阅服务", "应用列表"),
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

        for top, leaf in CASES:
            key = f"{top}>{leaf}"
            urls.clear()
            info = {}
            try:
                # 先确保一级菜单展开
                t = page.get_by_text(top, exact=True).last
                if t.count():
                    t.click()
                    page.wait_for_timeout(2000)
                leaf_loc = page.get_by_text(leaf, exact=True).last
                info["leaf_found"] = leaf_loc.count()
                if leaf_loc.count():
                    leaf_loc.click()
                    page.wait_for_timeout(7000)
                    info["url"] = page.url[:200]
                    info["body_head"] = page.locator("body").inner_text()[:600]
                    biz = [
                        u
                        for u in urls
                        if any(k in u for k in ("/irp-api/", "/workflow/", "/metrology/"))
                    ]
                    info["api_calls"] = biz[:20]
                    page.screenshot(
                        path=str(
                            Path("reports/prod-keshang")
                            / f"_leaf-{top}-{leaf}.png"
                        ),
                        full_page=True,
                    )
            except Exception as exc:  # noqa: BLE001
                info["error"] = f"{type(exc).__name__}: {exc}"[:200]
            r["cases"][key] = info
            print(f"\n[{key}] found={info.get('leaf_found')} url={(info.get('url') or '')[:120]}", flush=True)
            for u in (info.get("api_calls") or [])[:8]:
                print("   ", u[:150], flush=True)
            if info.get("error"):
                print("   ERR:", info["error"], flush=True)

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
