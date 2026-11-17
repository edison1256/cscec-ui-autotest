"""探测工作台 3 个列表的真实数据量（为 102/103/104 定量级基线）。

方法同 101：
  门户 → 管理后台 → 工作台（正确套件 suitKey=1899427585366003727）
  → 逐个点「常用模块」卡片 → 读分页文案「总共 N 条」+ 抓该轮全部 /irp-api/ 响应

入口名按生产实测：
  云产品订阅 / 数据资产订阅 / 订单管理（「我的订单」对应「订单管理」卡片）
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/coverage-gaps/_baseline_103.json")
SHOT = Path("reports/coverage-gaps")

ENTRIES = ["云产品订阅", "数据资产订阅", "订单管理"]


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_base-{tag}.png"), full_page=True)
    except Exception:
        pass


def info(page) -> dict:
    try:
        v = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


def pager_total(page) -> int:
    """读分页文案总数：生产实测「第 1-13 条/总共 13 条」。"""
    try:
        body = page.locator("body").inner_text()
    except Exception:
        return -1
    compact = re.sub(r"\s+", "", body)
    for pat in (r"总共(\d+)条", r"共(\d+)条", r"总计(\d+)条", r"合计(\d+)条"):
        m = re.search(pat, compact)
        if m:
            return int(m.group(1))
    return -1


def click_popover_workbench(page) -> bool:
    """管理后台 → 工作台（限定在 ant-popover 内）。"""
    mgr = page.get_by_text("管理后台", exact=True).last
    if not mgr.count():
        return False
    try:
        mgr.hover()
    except Exception:
        mgr.click()
    page.wait_for_timeout(2400)
    pop = page.locator(".ant-popover-inner-content").first
    if not pop.count():
        return False
    item = pop.get_by_text("工作台", exact=True).first
    if not item.count():
        return False
    item.click()
    page.wait_for_timeout(6500)
    return True


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "entries": {}}
    bucket: list[dict] = []

    def on_resp(resp):
        if "/irp-api/" not in resp.url:
            return
        item = {"url": resp.url[:190], "method": resp.request.method}
        try:
            body = resp.json()
            data = body.get("data") if isinstance(body, dict) else None
            if isinstance(data, dict):
                rows = data.get("list") or data.get("records") or data.get("rows")
                if isinstance(rows, list):
                    item["total"] = data.get("total")
                    item["len"] = len(rows)
                    if rows and isinstance(rows[0], dict):
                        item["fields"] = list(rows[0].keys())[:20]
                    bucket.append(item)
            elif isinstance(data, list):
                item["len"] = len(data)
                bucket.append(item)
        except Exception:
            return

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

            before = len(ctx.pages)
            ok = click_popover_workbench(page)
            r["workbench_opened"] = ok
            if len(ctx.pages) > before:
                page = ctx.pages[-1]
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(3500)
            page.on("response", on_resp)
            r["workbench_url"] = page.url[:180]
            r["login_info"] = info(page)
            print("工作台:", r["workbench_url"][:110])
            print("orgNo:", r["login_info"].get("orgNo"))

            for entry in ENTRIES:
                bucket.clear()
                res: dict = {}
                try:
                    # 每个入口前先回工作台首页：上一轮点击已经离开首页，
                    # 卡片元素虽然还在 DOM 里但不可点（会 click timeout）。
                    try:
                        page.go_back(wait_until="domcontentloaded")
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    body = ""
                    for _ in range(30):
                        try:
                            body = page.locator("body").inner_text()
                        except Exception:
                            body = ""
                        if "常用模块" in body:
                            break
                        page.wait_for_timeout(500)
                    if "常用模块" not in body:
                        tab = page.get_by_text("工作台", exact=True).first
                        if tab.count():
                            try:
                                tab.click()
                                page.wait_for_timeout(4000)
                            except Exception:
                                pass

                    loc = page.get_by_text(entry, exact=True).last
                    if not loc.count():
                        res["error"] = "入口不存在"
                        r["entries"][entry] = res
                        print(f"[{entry}] 入口不存在")
                        continue
                    loc.click()
                    page.wait_for_timeout(8000)
                    res["url"] = page.url[:180]
                    res["pager_total"] = pager_total(page)
                    res["apis"] = bucket[:4]
                    snap(page, entry)
                except Exception as exc:  # noqa: BLE001
                    res["error"] = f"{type(exc).__name__}: {exc}"[:160]
                r["entries"][entry] = res
                print(f"[{entry}] total={res.get('pager_total')} "
                      f"url={(res.get('url') or '')[:90]} {res.get('error') or ''}")
                for a in (res.get("apis") or []):
                    print(f"   api: {a['url'][:95]} total={a.get('total')} len={a.get('len')}")
                    print(f"        fields={(a.get('fields') or [])[:14]}")

            # 回工作台，供下一轮复用
            page.wait_for_timeout(500)
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
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
