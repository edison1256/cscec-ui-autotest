"""探测：控制台顶栏消息铃铛点击后实际发出的接口。

用例 M3-04 等待 /message/messageReceiver/page? 超时 60s。
需判断是：接口路径变了 / 铃铛点击位置变了 / 无未读消息时不发请求。
只读（点开铃铛面板，不点任何消息跳转）。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_bell_probe.json")


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        urls = []
        page.on("response", lambda resp: urls.append(f"{resp.status} {resp.request.method} {resp.url}"))

        LoginPage(page).login()
        page.wait_for_timeout(3500)

        # 铃铛定位
        bell = page.get_by_role("img", name="bell", exact=True)
        r["bell_count"] = bell.count()
        r["bell_visible"] = bell.first.is_visible() if bell.count() else None

        # 不清空：消息列表可能在页面初始化时已请求过（点铃铛只展开面板）
        before = len(urls)
        try:
            if bell.count():
                bell.first.click()
                page.wait_for_timeout(6000)
        except Exception as exc:  # noqa: BLE001
            r["click_error"] = f"{type(exc).__name__}: {exc}"[:200]

        r["after_url"] = page.url[:180]
        r["urls_total"] = len(urls)
        r["urls_before_click"] = before
        msg_calls = [u for u in urls if "message" in u.lower() or "receiver" in u.lower()]
        r["message_calls"] = msg_calls[:25]
        r["all_calls_sample"] = [u for u in urls if "/irp-api/" in u][:25]

        # 面板是否出现
        body = page.locator("body").inner_text()
        r["has_approval_tab"] = "审批" in body
        r["has_tab_task"] = "任务" in body
        r["has_tab_notice"] = "通知" in body
        r["body_head"] = body[:600]

        page.screenshot(
            path=str(Path("reports/prod-keshang") / "_bell-panel.png"), full_page=True
        )

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"bell_count={r.get('bell_count')} visible={r.get('bell_visible')}", flush=True)
    print(f"click_error={r.get('click_error')}", flush=True)
    print(f"tabs: 审批={r.get('has_approval_tab')} 任务={r.get('has_tab_task')} 通知={r.get('has_tab_notice')}", flush=True)
    print(f"\n/message 相关请求({len(msg_calls)}):", flush=True)
    for u in msg_calls[:15]:
        print("  ", u[:180], flush=True)
    print(f"\n全部 irp-api 请求({len(r['all_calls_sample'])}):", flush=True)
    for u in (r["all_calls_sample"] or [])[:15]:
        print("  ", u[:180], flush=True)
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
