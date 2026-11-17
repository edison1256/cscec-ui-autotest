"""探测：个人工作台（suitKey=portal）下「订单中心 → 被订阅的订单」的数据归属。

背景（2026-11-17 用户走查）：
  个人工作台下该页返回**全量**数据，而不是当前账户被订阅的订单 —— 越权。

上一版探针的错误：在 cloud 域找入口。个人工作台其实在**控制台域**
（`/udpweb/portal/index.html#/portal/home/workbench?suitKey=portal`），
登录态实测 `orgName=个人工作台`。

导航边界：只直链到「工作台首页」（等价于用户点入口进系统），
之后一律靠点击菜单/卡片，绝不拼二级页路由。

只读。
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
from pages.portal.portal_home_page import CONSOLE_WORKBENCH_ROUTE  # noqa: E402

OUT = Path("reports/coverage-gaps/_probe_scope2.json")
SHOT = Path("reports/coverage-gaps")

OWNER_FIELDS = (
    "tenantNo", "tenantCode", "tenantName", "tenantId",
    "subscriberTenantNo", "subscriberId", "subscribeTenantNo",
    "ownerTenantNo", "orgCode", "creator", "creatorName", "resourceOwner",
)


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_scope2-{tag}.png"), full_page=True)
    except Exception:
        pass


def text_of(page, n: int = 2500) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 3500) -> bool:
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
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {"checked_at": datetime.now().isoformat(timespec="seconds")}
    captured: list[dict] = []

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        def on_response(resp):
            low = resp.url.lower()
            if not any(k in low for k in ("order", "subscri", "apply")):
                return
            item = {"url": resp.url[:210], "status": resp.status, "method": resp.request.method}
            try:
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else None
                if isinstance(data, dict):
                    rows = data.get("list") or data.get("records") or data.get("rows")
                    item["total"] = data.get("total")
                    if isinstance(rows, list):
                        item["list_len"] = len(rows)
                        if rows and isinstance(rows[0], dict):
                            item["row_fields"] = list(rows[0].keys())[:30]
                            dist = {}
                            for f in OWNER_FIELDS:
                                vals = [str(row.get(f)) for row in rows if row.get(f) is not None]
                                if vals:
                                    c = Counter(vals)
                                    dist[f] = {"unique": len(c), "top": c.most_common(6)}
                            item["owner_distribution"] = dist
                elif isinstance(data, list):
                    item["list_len"] = len(data)
            except Exception:
                pass
            captured.append(item)

        page.on("response", on_response)

        try:
            LoginPage(page).login()
            page.wait_for_timeout(2500)
            r["login_url"] = page.url[:200]

            # 只直链到「工作台首页」，之后靠点击
            page.goto(
                settings.console_url(CONSOLE_WORKBENCH_ROUTE),
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(4000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            try:
                info = page.evaluate(
                    "() => { const s = localStorage.getItem('__login_info__');"
                    " return s ? JSON.parse(s) : null; }"
                )
            except Exception:
                info = None
            r["login_info"] = {
                k: (info or {}).get(k)
                for k in ("userNo", "userName", "tenantNo", "tenantName", "orgName")
            }
            r["workbench_url"] = page.url[:220]
            body = text_of(page, 3000)
            r["workbench_text"] = body
            r["has_order_center"] = "订单中心" in body
            r["has_subscribed"] = "被订阅" in body
            snap(page, "workbench")

            r["order_center_clicked"] = click_text(page, "订单中心", 3000)
            r["url_after_oc"] = page.url[:220]
            r["oc_text"] = text_of(page, 1500)
            snap(page, "order-center")

            r["subscribed_clicked"] = click_text(page, "被订阅的订单", 6000)
            page.wait_for_timeout(3000)
            r["url_after_sub"] = page.url[:220]
            r["sub_text"] = text_of(page, 2500)
            r["sub_status_words"] = [w for w in ("暂无数据", "共", "条") if w in r["sub_text"]]
            snap(page, "subscribed")

            r["interfaces"] = [
                x for x in captured
                if x.get("list_len") is not None or x.get("total") is not None
            ][:12]
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
            r["url_at_failure"] = page.url[:200]
            snap(page, "failed")
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("身份:", json.dumps(r.get("login_info"), ensure_ascii=False))
    print("工作台:", (r.get("workbench_url") or "")[:120])
    print("  有订单中心:", r.get("has_order_center"), "| 有被订阅:", r.get("has_subscribed"))
    print("订单中心点击:", r.get("order_center_clicked"))
    print("被订阅点击:", r.get("subscribed_clicked"), "->", (r.get("url_after_sub") or "")[:110])
    print("错误:", r.get("error"))
    print("\n=== 接口与归属分布 ===")
    for it in (r.get("interfaces") or []):
        print(f"\n{it['method']} {it['status']} {it['url'][:130]}")
        print(f"  total={it.get('total')} len={it.get('list_len')}")
        print(f"  fields={(it.get('row_fields') or [])[:18]}")
        for f, d in (it.get("owner_distribution") or {}).items():
            print(f"  归属 {f}: unique={d['unique']} top={d['top'][:3]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
