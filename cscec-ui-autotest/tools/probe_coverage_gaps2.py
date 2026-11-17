"""精确取证：开发者社区真实跳转元素 + 订单列表接口原文。

上一版探针的两个问题：
  1. 点「开发者社区」命中的是卡片标题（页面停在原地显示「敬请期待」），
     真正的跳转入口可能是卡片本身或「立即前往」类按钮，需枚举 DOM 链接。
  2. 订单接口过滤条件过严（要求 URL 同时含 order + page/list），
     实际一个都没捕获到，改为捕获全部响应事后筛选。

只读。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/coverage-gaps/_probe2.json")
SHOT = Path("reports/coverage-gaps")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_gap2-{tag}.png"), full_page=True)
    except Exception:
        pass


def links_on(page) -> list[dict]:
    """枚举页面所有 a 标签及其 href/文本。"""
    try:
        return page.evaluate(
            """() => Array.from(document.querySelectorAll('a')).map(a => ({
                 text: (a.innerText || '').trim().slice(0, 60),
                 href: a.getAttribute('href') || '',
                 target: a.getAttribute('target') || ''
               })).filter(x => x.text || x.href).slice(0, 120)"""
        )
    except Exception:
        return []


def clickable_texts(page) -> list[str]:
    """枚举可点击元素文本（含卡片/按钮）。"""
    try:
        return page.evaluate(
            """() => Array.from(document.querySelectorAll(
                 "button,[role='button'],.card,[class*='card'],[class*='item'],img"))
               .map(e => (e.innerText || e.getAttribute('alt') || '').trim().slice(0,40))
               .filter(Boolean).slice(0, 150)"""
        )
    except Exception:
        return []


def probe_zone(browser) -> dict:
    info: dict = {}
    ctx = browser.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(25000)
    try:
        LoginPage(page).login_portal()
        page.wait_for_timeout(3000)
        for _ in range(2):
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
        # 进入开发者平台（走导航，不拼直链）
        for label in ("开发者平台",):
            loc = page.get_by_text(label, exact=True).last
            if loc.count():
                loc.click()
                page.wait_for_timeout(3500)
        info["url"] = page.url[:200]

        links = links_on(page)
        info["links_total"] = len(links)
        info["zone_links"] = [x for x in links if "zone" in x["href"].lower()]
        info["community_links"] = [x for x in links if "社区" in x["text"]]
        info["external_links"] = [
            x for x in links
            if x["href"].startswith("http") and "cscec.com" not in x["href"]
        ][:15]
        info["clickable_sample"] = clickable_texts(page)[:40]

        # 若存在 zone 链接，直接点它（元素级点击，仍属可见入口）
        target = ctx.pages[-1]
        before_pages = len(ctx.pages)
        clicked = False
        if info["zone_links"]:
            href = info["zone_links"][0]["href"]
            try:
                page.locator(f"a[href='{href}']").first.click()
                page.wait_for_timeout(6000)
                clicked = True
            except Exception as exc:  # noqa: BLE001
                info["zone_click_error"] = str(exc)[:160]
        info["zone_clicked"] = clicked

        if len(ctx.pages) > before_pages:
            target = ctx.pages[-1]
            info["new_tab"] = True
        else:
            info["new_tab"] = False
        try:
            target.wait_for_load_state("domcontentloaded", timeout=25000)
        except Exception:
            pass
        target.wait_for_timeout(3000)
        body = target.locator("body").inner_text()[:2000]
        info["landing_url"] = target.url[:220]
        info["landing_host"] = target.url.split("/")[2] if "://" in target.url else ""
        info["landing_text"] = body[:1200]
        info["biz_error_words"] = [
            w for w in ("租户错误", "租户不存在", "请选择租户", "无权限", "无权访问",
                        "未开通", "数据不存在", "操作失败", "系统繁忙")
            if w in body
        ]
        snap(target, "zone")
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        snap(page, "zone-failed")
    finally:
        ctx.close()
    return info


def probe_orders(browser) -> dict:
    """控制台订单管理：捕获全部响应，事后筛 order。"""
    info: dict = {}
    ctx = browser.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(25000)

    all_resp: list[dict] = []

    def on_response(resp):
        url = resp.url
        low = url.lower()
        if not any(k in low for k in ("order", "bizorder", "trade")):
            return
        item = {"url": url[:200], "status": resp.status, "method": resp.request.method}
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
                        item["first_time_fields"] = {
                            k: rows[0][k] for k in
                            ("createTime", "createdAt", "createDt", "gmtCreate",
                             "insertDt", "orderTime", "submitTime")
                            if rows[0].get(k)
                        }
            elif isinstance(data, list):
                item["list_len"] = len(data)
        except Exception:
            pass
        all_resp.append(item)

    page.on("response", on_response)

    try:
        LoginPage(page).login()
        page.wait_for_timeout(3000)
        for label in ("订单中心", "订单管理"):
            loc = page.get_by_text(label, exact=True).last
            if loc.count():
                loc.click()
                page.wait_for_timeout(4500)
        info["url"] = page.url[:200]
        page.wait_for_timeout(2000)
        info["body_text"] = page.locator("body").inner_text()[:1500]
        # 只保留像列表接口的
        info["order_apis"] = [
            x for x in all_resp
            if x.get("list_len") is not None or x.get("total") is not None
        ][:10]
        info["all_order_urls"] = [x["url"] for x in all_resp][:20]
        snap(page, "orders")
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        snap(page, "orders-failed")
    finally:
        ctx.close()
    return info


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {"checked_at": datetime.now().isoformat(timespec="seconds")}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)

        r["zone"] = probe_zone(b)
        z = r["zone"]
        print("=== 开发者社区 ===")
        print(" url:", z.get("url", "")[:110])
        print(" zone_links:", z.get("zone_links"))
        print(" community_links:", z.get("community_links"))
        print(" clicked:", z.get("zone_clicked"), "new_tab:", z.get("new_tab"))
        print(" landing:", z.get("landing_url", "")[:130])
        print(" biz_errors:", z.get("biz_error_words"))
        print(" text:", (z.get("landing_text") or "")[:300].replace("\n", " / "))

        r["orders"] = probe_orders(b)
        o = r["orders"]
        print("\n=== 订单管理 ===")
        print(" url:", (o.get("url") or "")[:120])
        print(" 列表接口:")
        for api in (o.get("order_apis") or []):
            print("   ", api["url"][:110])
            print("     status=", api["status"], "total=", api.get("total"),
                  "len=", api.get("list_len"))
            print("     time=", api.get("first_time_fields"))
            print("     fields=", (api.get("row_fields") or [])[:16])

        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
