"""扫描「申请历史」族接口的数据归属分布（越权面）。

背景：个人工作台「被订阅的订单」实测返回 26 个租户 / 828 条（越权）。
怀疑同一族接口（`*/apply/history/list`、`*/applyList`、`*/aggregateForConsole`）
共用后端查询，可能整族都有同样问题。

做法：
  1. 进个人工作台（suitKey=portal），先不点击，等页面自身把磁贴数据加载完
  2. 抓所有响应，筛出列表型接口
  3. 对每个接口统计 total 与归属字段（tenantNo 等）的去重分布

只读：不点击任何会产生写操作的按钮。
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

OUT = Path("reports/coverage-gaps/_apply_family_scope.json")

OWNER_FIELDS = (
    "tenantNo", "tenantCode", "tenantId", "tenantName",
    "subscriberTenantNo", "subscriberId", "ownerTenantNo", "orgCode",
)

# 关注接口族
FAMILY_HINTS = ("apply/history/list", "applyList", "aggregateForConsole", "apply/info")


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "interfaces": []}
    seen_urls: set[str] = set()

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        def on_response(resp):
            url = resp.url
            low = url.lower()
            if not any(h.lower() in low for h in FAMILY_HINTS):
                return
            key = url.split("?")[0]
            if key in seen_urls:
                return
            item = {"url": url[:210], "status": resp.status, "method": resp.request.method}
            try:
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else None
                if isinstance(data, dict):
                    rows = data.get("list") or data.get("records") or data.get("rows")
                    item["total"] = data.get("total")
                    if isinstance(rows, list):
                        item["list_len"] = len(rows)
                        if rows and isinstance(rows[0], dict):
                            item["row_fields"] = list(rows[0].keys())[:28]
                            dist = {}
                            for f in OWNER_FIELDS:
                                vals = [str(x.get(f)) for x in rows if x.get(f) is not None]
                                if vals:
                                    c = Counter(vals)
                                    dist[f] = {"unique": len(c), "top": c.most_common(4)}
                            item["owner_distribution"] = dist
                elif isinstance(data, list):
                    item["list_len"] = len(data)
            except Exception:
                return
            seen_urls.add(key)
            r["interfaces"].append(item)

        page.on("response", on_response)

        try:
            LoginPage(page).login()
            page.wait_for_timeout(2000)
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

            # 个人工作台：只到首页，靠页面自身加载磁贴数据
            page.goto(
                settings.console_url(CONSOLE_WORKBENCH_ROUTE),
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(9000)
            r["workbench_url"] = page.url[:200]
            try:
                r["workbench_text"] = page.locator("body").inner_text()[:1500]
            except Exception:
                r["workbench_text"] = ""

            # 再进入几个只读列表页，触发各自接口
            for label in ("被订阅的订单", "我的订阅", "订单管理", "API列表", "应用列表"):
                loc = page.get_by_text(label, exact=True).last
                if loc.count():
                    try:
                        loc.click()
                        page.wait_for_timeout(5000)
                    except Exception:
                        continue
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("身份:", json.dumps(r.get("login_info"), ensure_ascii=False))
    print(f"捕获接口: {len(r['interfaces'])}\n")
    for it in r["interfaces"]:
        print(f"{it['method']} {it['status']} {it['url'][:120]}")
        print(f"   total={it.get('total')} len={it.get('list_len')}")
        for f, d in (it.get("owner_distribution") or {}).items():
            print(f"   归属 {f}: unique={d['unique']} top={d['top'][:3]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
