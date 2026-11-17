"""探测：个人工作台下的「订单中心 → 被订阅的订单」，并取证数据归属。

背景（2026-11-17 用户走查）：
  个人工作台下「订单中心-被订阅的订单」返回了**全量**数据，而不是当前账户
  被订阅的订单。这是数据归属（越权）问题，与前两个 bug 不同维度。

历史线索：ui_case_assets.yaml 记「2026-09-09 移除无可复现控制台操作路径的
被订阅订单旧入口」—— 当年是在**控制台**找入口，可能本来就该在个人工作台。

取证重点：接口返回记录里出现多少个不同的租户/归属标识。
个人账号只应看到与自身相关的数据，出现多个租户即为越权。

只读：点导航、读响应，不提交任何表单。
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

OUT = Path("reports/coverage-gaps/_probe_scope.json")
SHOT = Path("reports/coverage-gaps")

# 可能表示归属的字段
OWNER_FIELDS = (
    "tenantNo", "tenantCode", "tenantName", "tenantId",
    "subscriberTenantNo", "subscriberId", "subscribeTenantNo",
    "ownerTenantNo", "orgCode", "creator", "creatorName",
)


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_scope-{tag}.png"), full_page=True)
    except Exception:
        pass


def text_of(page, n: int = 2000) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 3500) -> bool:
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

        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        # 全量捕获，事后按需筛
        all_resp: list[dict] = []

        def on_response(resp):
            url = resp.url
            low = url.lower()
            if not any(k in low for k in ("order", "subscribe", "subscri", "apply")):
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
                            # 归属字段分布
                            dist = {}
                            for f in OWNER_FIELDS:
                                values = [str(row.get(f)) for row in rows if row.get(f) is not None]
                                if values:
                                    counter = Counter(values)
                                    dist[f] = {
                                        "unique": len(counter),
                                        "top": counter.most_common(5),
                                    }
                            item["owner_distribution"] = dist
                elif isinstance(data, list):
                    item["list_len"] = len(data)
            except Exception:
                pass
            all_resp.append(item)

        page.on("response", on_response)

        try:
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)

            # 从登录态读显示名，hover 打开个人卡片
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

            name = (info or {}).get("userName")
            if name:
                loc = page.get_by_text(name, exact=True).first
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2200)
            r["card_opened"] = True

            # 个人工作台入口
            r["personal_wb_clicked"] = click_text(page, "个人工作台", 5000)
            r["url_after_personal"] = page.url[:220]
            r["personal_text"] = text_of(page, 1500)
            snap(page, "personal-wb")

            # 订单中心
            r["order_center_clicked"] = click_text(page, "订单中心", 3000)
            r["url_after_order_center"] = page.url[:220]
            r["order_center_text"] = text_of(page, 1200)
            snap(page, "order-center")

            # 被订阅的订单
            r["subscribed_clicked"] = click_text(page, "被订阅的订单", 6000)
            page.wait_for_timeout(3000)
            r["url_after_subscribed"] = page.url[:220]
            r["subscribed_text"] = text_of(page, 2000)
            snap(page, "subscribed-orders")

            r["interfaces"] = [
                x for x in all_resp
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

    print("登录身份:", json.dumps(r.get("login_info"), ensure_ascii=False))
    print("个人工作台:", r.get("personal_wb_clicked"), "->", (r.get("url_after_personal") or "")[:110])
    print("订单中心:", r.get("order_center_clicked"))
    print("被订阅的订单:", r.get("subscribed_clicked"), "->", (r.get("url_after_subscribed") or "")[:110])
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
