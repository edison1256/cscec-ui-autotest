"""生产只读探针：跨域跳转落地页健康 + 列表数据新鲜度。

针对两个走查漏掉的 bug 取证：
  1. 门户「开发者平台 → 开发者社区」跳 zone.cscec.com 后出现「租户错误」
  2. 工作台/控制台「订单中心 → 订单管理」近期订单不显示

只读：点导航、读文本、读接口响应；不提交任何表单。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/coverage-gaps/_probe.json")
SHOT = Path("reports/coverage-gaps")

# 业务级错误提示（当前 page_not_blank_or_error 未覆盖的词）
BIZ_ERROR_WORDS = (
    "租户错误", "租户不存在", "请选择租户", "无权限", "没有权限",
    "无权访问", "开通后访问", "未开通", "数据不存在", "操作失败",
)

TIME_FIELDS = ("createTime", "createdAt", "createDt", "gmtCreate", "insertDt", "orderTime")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_gap-{tag}.png"), full_page=True)
    except Exception:
        pass


def text_of(page, n: int = 2500) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 3000) -> bool:
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_role("link", name=label, exact=True).last,
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


def probe_zone(browser) -> dict:
    """门户 → 开发者平台 → 开发者社区，看跨域落地页。"""
    info: dict = {}
    ctx = browser.new_context(viewport={"width": 1680, "height": 1050}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(25000)
    # 捕获跳转后的新标签页
    pages_before = len(ctx.pages)
    try:
        LoginPage(page).login_portal()
        page.wait_for_timeout(3000)
        for _ in range(2):
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)

        info["portal_ok"] = "cloud" in page.url
        # 开发者平台
        info["dev_platform_clicked"] = click_text(page, "开发者平台", 3000)
        info["dev_platform_url"] = page.url[:200]
        info["dev_platform_text"] = text_of(page, 1200)

        # 开发者社区（可能新开标签页）
        target = None
        clicked = click_text(page, "开发者社区", 5000)
        info["community_clicked"] = clicked
        if len(ctx.pages) > pages_before:
            target = ctx.pages[-1]
            info["opened_new_tab"] = True
        else:
            target = page
            info["opened_new_tab"] = False

        if target is not None:
            try:
                target.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            target.wait_for_timeout(3000)
            body = text_of(target, 2500)
            info["landing_url"] = target.url[:220]
            info["landing_host"] = target.url.split("/")[2] if "://" in target.url else ""
            info["landing_text"] = body[:1500]
            info["biz_errors_found"] = [w for w in BIZ_ERROR_WORDS if w in body]
            info["body_length"] = len(body)
            snap(target, "zone")
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        info["url_at_failure"] = page.url[:200]
        snap(page, "zone-failed")
    finally:
        ctx.close()
    return info


def probe_orders(browser, entry: str) -> dict:
    """订单中心 → 订单管理，抓 total 与首条记录时间。"""
    info: dict = {"entry": entry}
    ctx = browser.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(25000)

    captured: list[dict] = []

    def on_response(resp):
        url = resp.url
        if "/order" not in url.lower():
            return
        if not any(k in url for k in ("page", "list", "Page", "List")):
            return
        try:
            body = resp.json()
        except Exception:
            return
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return
        rows = data.get("list") or data.get("records") or data.get("rows")
        if not isinstance(rows, list):
            return
        first = rows[0] if rows and isinstance(rows[0], dict) else {}
        times = {k: first.get(k) for k in TIME_FIELDS if first.get(k)}
        captured.append({
            "url": url[:180],
            "total": data.get("total"),
            "list_len": len(rows),
            "first_record_time_fields": times,
            "row_fields": list(first.keys())[:25] if first else [],
        })

    page.on("response", on_response)

    try:
        if entry == "console":
            LoginPage(page).login()
            page.wait_for_timeout(3000)
            namespace = "console"
        else:
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)
            namespace = "workbench"
            # 工作台里的订单入口
            info["workbench_entry"] = click_text(page, "订单管理", 4000)

        if namespace == "console":
            info["order_center_clicked"] = click_text(page, "订单中心", 2500)
            info["order_mgmt_clicked"] = click_text(page, "订单管理", 5000)
            page.wait_for_timeout(3000)

        info["final_url"] = page.url[:200]
        info["body_text"] = text_of(page, 1200)
        info["order_apis"] = captured[:6]
        snap(page, f"orders-{entry}")
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        info["url_at_failure"] = page.url[:200]
        snap(page, f"orders-{entry}-failed")
    finally:
        ctx.close()
    return info


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod（复现走查发现的问题）")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "env": settings.ENV}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)

        r["zone"] = probe_zone(b)
        print("=== 开发者社区 ===")
        print(" clicked:", r["zone"].get("community_clicked"),
              "| new_tab:", r["zone"].get("opened_new_tab"))
        print(" landing:", r["zone"].get("landing_url", "")[:120])
        print(" 业务错误词:", r["zone"].get("biz_errors_found"))
        print(" body 摘要:", (r["zone"].get("landing_text") or "")[:260].replace("\n", " / "))

        for entry in ("console", "workbench"):
            r[f"orders_{entry}"] = probe_orders(b, entry)
            o = r[f"orders_{entry}"]
            print(f"\n=== 订单管理（{entry}）===")
            print(" url:", (o.get("final_url") or "")[:110])
            for api in (o.get("order_apis") or [])[:3]:
                print("  api:", api["url"][:90])
                print("       total=", api["total"], "len=", api["list_len"],
                      "time=", api["first_record_time_fields"])

        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
