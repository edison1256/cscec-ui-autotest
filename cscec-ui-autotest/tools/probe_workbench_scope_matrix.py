"""逐个入口扫描个人工作台列表的数据归属（越权面）。

个人工作台「常用模块」实测 12 项，其中订阅类 5 个 + 订单管理 + 被订阅的订单，
都是「我的」语义，理论上只能看到当前账号的数据。

做法：每个入口单独一轮 —— 回首页 → 点击 → 记录该轮触发的列表接口与
tenantNo 去重分布，避免上一轮的接口混进结果。

只读：只点列表入口，不点任何提交/删除/审批按钮。
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

OUT = Path("reports/coverage-gaps/_workbench_scope_matrix.json")

ENTRIES = [
    "应用订阅",
    "API订阅",
    "组件订阅",
    "云产品订阅",
    "数据资产订阅",
    "订单管理",
    "被订阅的订单",
]

OWNER_FIELDS = ("tenantNo", "tenantCode", "tenantId", "tenantName",
                "subscriberTenantNo", "ownerTenantNo", "orgCode")
LIST_HINTS = ("apply/history/list", "applylist", "aggregateforconsole",
              "order/page", "apply/info", "subscription")


def is_list_payload(item: dict) -> bool:
    return item.get("list_len") is not None or item.get("total") is not None


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "entries": {}}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        bucket: list[dict] = []

        def on_response(resp):
            low = resp.url.lower()
            if not any(h in low for h in LIST_HINTS):
                return
            item = {"url": resp.url[:200], "status": resp.status, "method": resp.request.method}
            try:
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else None
                if isinstance(data, dict):
                    rows = data.get("list") or data.get("records") or data.get("rows")
                    item["total"] = data.get("total")
                    if isinstance(rows, list):
                        item["list_len"] = len(rows)
                        if rows and isinstance(rows[0], dict):
                            item["row_fields"] = list(rows[0].keys())[:26]
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
            bucket.append(item)

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

            home = settings.console_url(CONSOLE_WORKBENCH_ROUTE)
            for label in ENTRIES:
                bucket.clear()
                info_entry: dict = {"clicked": False}
                try:
                    page.goto(home, wait_until="domcontentloaded",
                              timeout=settings.NAVIGATION_TIMEOUT)
                    page.wait_for_timeout(3500)
                    for _ in range(2):
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(400)

                    loc = page.get_by_text(label, exact=True).last
                    if not loc.count():
                        info_entry["error"] = "入口不存在"
                        r["entries"][label] = info_entry
                        continue
                    loc.click()
                    page.wait_for_timeout(6000)
                    info_entry["clicked"] = True
                    info_entry["url"] = page.url[:200]
                    info_entry["apis"] = [x for x in bucket if is_list_payload(x)][:4]
                except Exception as exc:  # noqa: BLE001
                    info_entry["error"] = f"{type(exc).__name__}: {exc}"[:160]
                r["entries"][label] = info_entry
                n = len(info_entry.get("apis") or [])
                print(f"[{label}] clicked={info_entry.get('clicked')} apis={n} "
                      f"{(info_entry.get('error') or '')[:60]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n身份:", json.dumps(r.get("login_info"), ensure_ascii=False))
    for label, e in r["entries"].items():
        print(f"\n=== {label} ===")
        if e.get("error"):
            print("  ", e["error"])
            continue
        print("   url:", (e.get("url") or "")[:110])
        for a in (e.get("apis") or []):
            print(f"   {a['method']} {a['url'][:110]}")
            print(f"     total={a.get('total')} len={a.get('list_len')}")
            for f, d in (a.get("owner_distribution") or {}).items():
                print(f"     归属 {f}: unique={d['unique']} top={d['top'][:3]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
