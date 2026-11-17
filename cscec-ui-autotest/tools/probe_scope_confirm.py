"""精查三个疑似越权的个人工作台列表。

上一轮扫描发现：
  - 被订阅的订单 → 无独立接口，渲染外壳预加载的 828 条 / 26 租户（已确认越权）
  - 云产品订阅   → /cloud/applyList，554 条 / 8 租户       ← 疑似
  - 数据资产订阅 → workbench/rsc/data/apply/history/list，16 条 / 2 租户 ← 疑似
  - 订单管理     → /order/page，2376 条，无 tenantNo，但有 creator/creatorName ← 疑似

本轮补 creator / creatorName 分布，并记录当前账号 userNo 用于比对。
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

OUT = Path("reports/coverage-gaps/_scope_confirm.json")

# (入口, 期望的列表接口片段)
CASES = [
    ("云产品订阅", "cloud/applylist"),
    ("数据资产订阅", "workbench/rsc/data/apply/history/list"),
    ("订单管理", "order/page"),
    ("被订阅的订单", "workbench/rsc/app/apply/history/list"),
]

FIELDS = ("tenantNo", "tenantName", "creator", "creatorName", "userName", "userNo")


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "cases": {}}

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
                            for f in FIELDS:
                                vals = [str(x.get(f)) for x in rows if x.get(f) is not None]
                                if vals:
                                    c = Counter(vals)
                                    dist[f] = {"unique": len(c), "top": c.most_common(5)}
                            item["dist"] = dist
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
            r["me"] = {
                k: (info or {}).get(k)
                for k in ("userNo", "userName", "tenantNo", "tenantName", "orgName")
            }

            home = settings.console_url(CONSOLE_WORKBENCH_ROUTE)
            for label, api_hint in CASES:
                bucket.clear()
                e: dict = {}
                try:
                    page.goto(home, wait_until="domcontentloaded",
                              timeout=settings.NAVIGATION_TIMEOUT)
                    page.wait_for_timeout(3500)
                    for _ in range(2):
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(400)
                    loc = page.get_by_text(label, exact=True).last
                    if not loc.count():
                        e["error"] = "入口不存在"
                    else:
                        loc.click()
                        page.wait_for_timeout(6500)
                        e["url"] = page.url[:190]
                        target = [
                            x for x in bucket
                            if api_hint in x["url"].lower() and (x.get("list_len") is not None)
                        ]
                        e["matched"] = target[-1] if target else None
                except Exception as exc:  # noqa: BLE001
                    e["error"] = f"{type(exc).__name__}: {exc}"[:160]
                r["cases"][label] = e
                m = e.get("matched")
                print(f"[{label}] total={(m or {}).get('total')} len={(m or {}).get('list_len')} "
                      f"{(e.get('error') or '')[:50]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n当前身份:", json.dumps(r.get("me"), ensure_ascii=False))
    for label, e in r["cases"].items():
        print(f"\n=== {label} ===")
        if e.get("error"):
            print("  ", e["error"])
            continue
        m = e.get("matched")
        if not m:
            print("   未捕获到目标接口")
            continue
        print(f"   {m['url'][:130]}")
        print(f"   total={m.get('total')} len={m.get('list_len')}")
        print(f"   fields={(m.get('row_fields') or [])[:16]}")
        for f, d in (m.get("dist") or {}).items():
            print(f"   {f}: unique={d['unique']} top={d['top'][:4]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
