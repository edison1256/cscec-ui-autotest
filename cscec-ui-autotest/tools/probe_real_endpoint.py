"""在正确的工作台套件下，反查「被订阅的订单」的真实列表接口。

上一轮的教训：
  直链 suitKey=portal 属于另一个套件，那里被订阅订单走
  workbench/rsc/app/apply/history/list（828 条 / 26 租户）。
  真实工作台是 suitKey=1899427585366003727，接口名未知。

做法：
  门户 → 管理后台 → 工作台（点击，新页签）→ 确认 orgNo → 点「被订阅的订单」
  抓该页**全部** /irp-api/ 响应，事后筛出列表型（含 list/records/total），
  不预设任何接口名。

只读，只点列表入口。
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

OUT = Path("reports/coverage-gaps/_real_endpoint.json")
SHOT = Path("reports/coverage-gaps")

OWNER_FIELDS = ("tenantNo", "tenantName", "orgNo", "creator", "creatorName", "userName")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_ep-{tag}.png"), full_page=True)
    except Exception:
        pass


def login_info(page) -> dict:
    try:
        v = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


def click_popover_item(page, label: str, wait: int = 6000) -> bool:
    """点「管理后台」popover 里的项（必须限定在 .ant-popover-inner-content）。"""
    pop = page.locator(".ant-popover-inner-content").first
    if not pop.count():
        return False
    t = pop.get_by_text(label, exact=True).first
    if not t.count():
        return False
    t.click()
    page.wait_for_timeout(wait)
    return True


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds")}
    bucket: list[dict] = []

    def on_resp(resp):
        if "/irp-api/" not in resp.url:
            return
        item = {"url": resp.url[:200], "method": resp.request.method, "status": resp.status}
        try:
            body = resp.json()
        except Exception:
            return
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            rows = data.get("list") or data.get("records") or data.get("rows")
            if not isinstance(rows, list):
                return
            item["total"] = data.get("total")
            item["len"] = len(rows)
            if rows and isinstance(rows[0], dict):
                item["fields"] = list(rows[0].keys())[:30]
                dist = {}
                for f in OWNER_FIELDS:
                    vals = [str(x.get(f)) for x in rows
                            if isinstance(x, dict) and x.get(f) is not None]
                    if vals:
                        c = Counter(vals)
                        dist[f] = {"unique": len(c), "top": c.most_common(5)}
                item["dist"] = dist
        elif isinstance(data, list):
            item["len"] = len(data)
        else:
            return
        bucket.append(item)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        try:
            # 1) 门户
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            r["portal"] = {"url": page.url[:120], "info": login_info(page)}
            print("1) 门户 orgNo:", r["portal"]["info"].get("orgNo"))

            # 2) 管理后台 → 工作台（新页签）
            mgr = page.get_by_text("管理后台", exact=True).last
            assert mgr.count(), "未找到管理后台"
            try:
                mgr.hover()
            except Exception:
                mgr.click()
            page.wait_for_timeout(2500)

            before = len(ctx.pages)
            ok = click_popover_item(page, "工作台", 7000)
            r["workbench_clicked"] = ok
            r["pages_delta"] = len(ctx.pages) - before
            if len(ctx.pages) > before:
                page = ctx.pages[-1]
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(3500)
            page.on("response", on_resp)
            r["workbench"] = {"url": page.url[:200], "info": login_info(page)}
            print("2) 工作台:", r["workbench"]["url"][:110])
            print("   orgNo:", r["workbench"]["info"].get("orgNo"),
                  "orgName:", r["workbench"]["info"].get("orgName"))
            snap(page, "workbench")

            # 3) 等常用模块渲染
            body = ""
            for _ in range(40):
                try:
                    body = page.locator("body").inner_text()
                except Exception:
                    body = ""
                if "常用模块" in body:
                    break
                page.wait_for_timeout(500)
            r["has_modules"] = "常用模块" in body
            print("3) 常用模块:", r["has_modules"])

            # 4) 点「被订阅的订单」，抓全部响应
            bucket.clear()
            loc = page.get_by_text("被订阅的订单", exact=True).last
            r["entry_found"] = bool(loc.count())
            if loc.count():
                loc.click()
                page.wait_for_timeout(9000)
            r["after_url"] = page.url[:200]
            r["after_info"] = login_info(page)
            print("4) 点被订阅的订单:", r["entry_found"], "->", r["after_url"][:110])
            snap(page, "subscribed")

            # 5) 按体积排序，最大的最可能是目标列表
            apis = sorted(bucket, key=lambda x: -(x.get("len") or 0))
            r["apis"] = apis[:8]
            print(f"\n=== 捕获列表型接口 {len(apis)} 个 ===")
            for a in apis[:8]:
                print(f"\n{a['method']} {a['status']} {a['url'][:140]}")
                print(f"  total={a.get('total')} len={a.get('len')}")
                print(f"  fields={(a.get('fields') or [])[:16]}")
                for f, d in (a.get("dist") or {}).items():
                    print(f"  {f}: unique={d['unique']} top={d['top'][:4]}")

        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
            r["url_at_failure"] = page.url[:180]
            snap(page, "99-failed")
            print("!! 异常:", r["error"])
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
