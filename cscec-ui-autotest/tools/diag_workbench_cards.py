"""生产只读诊断：工作台卡片清单 + 「API订阅」实际调用的接口。

目的：
  1. 取工作台「常用模块」实际卡片标签，与契约 expected 比对（WB-007）
  2. 点「API订阅」后记录全部响应 URL，判断契约登记的
     /console/rsc/api/apply/history/list 是否真的没被调用、实际调用的是什么（WB-004）
只读，不点任何表单/提交按钮。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_diag_workbench_cards.json")


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"responses": []}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1050}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        urls = []
        page.on("response", lambda resp: urls.append(f"{resp.status} {resp.request.method} {resp.url}"))

        LoginPage(page).login()
        page.wait_for_timeout(3000)
        print("login ok", flush=True)

        # 工作台卡片清单：DOM 里 .moduleList .moduleItem 的文本
        cards = []
        try:
            # 与 ConsoleWorkbenchPage.open() 完全一致的选择器：
            # .moduleList .moduleItem 内的 .itemLabel
            lists = page.locator(".moduleList")
            r["modulelist_count"] = lists.count()
            cards = [
                t.strip()
                for t in page.locator(".moduleList .moduleItem").locator(".itemLabel").all_inner_texts()
                if t.strip()
            ]
        except Exception as exc:  # noqa: BLE001
            r["cards_error"] = str(exc)[:200]
        r["module_cards"] = cards
        print(f"cards({len(cards)}): {cards}", flush=True)
        page.screenshot(
            path=str(Path("reports/prod-keshang") / "_diag-workbench-cards.png"),
            full_page=True,
        )

        # 点「API订阅」
        attempts = {}
        clicked = None
        for label in ("API订阅", "API资源", "API列表"):
            urls.clear()
            info = {"in_labels": label in cards}
            try:
                card = page.locator(".moduleList .moduleItem").filter(
                    has=page.get_by_text(label, exact=True)
                ).first
                info["dom_count"] = card.count()
                if card.count():
                    info["visible"] = card.is_visible()
                    card.click(timeout=8000)
                    page.wait_for_timeout(6000)
                    info["after_url"] = page.url[:160]
                    info["api_calls"] = [
                        u for u in urls
                        if any(k in u for k in ("/irp-api/", "/workflow/", "/metrology/"))
                    ][:25]
                    clicked = label
            except Exception as exc:  # noqa: BLE001
                info["error"] = f"{type(exc).__name__}: {exc}"[:150]
            attempts[label] = info
            print(f"try {label}: {info.get('dom_count')} {info.get('error','')}"[:160], flush=True)
            if clicked:
                break
        r["attempts"] = attempts

        r["clicked_card"] = clicked
        r["after_click_url"] = page.url[:200]
        r["after_click_body"] = page.locator("body").inner_text()[:800]

        # 只保留业务接口（排除静态资源）
        biz = [u for u in urls if any(k in u for k in ("/irp-api/", "/workflow/", "/metrology/", "/api/"))]
        r["api_calls"] = biz[:60]
        page.screenshot(
            path=str(Path("reports/prod-keshang") / "_diag-after-click.png"), full_page=True
        )

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nclicked: {clicked} -> {r['after_click_url'][:120]}", flush=True)
    print(f"\n业务接口调用（{len(biz)}）:", flush=True)
    for u in biz[:40]:
        print("  ", u[:190], flush=True)
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
