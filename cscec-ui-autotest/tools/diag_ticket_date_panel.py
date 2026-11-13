"""探测：工单发起时间日期面板里 td[title="YYYY-MM-DD"] 的实际数量。

用例 filter_by_existing_creation_day 断言 to_have_count(1)，实际失败。
判断是「同一天在面板出现多次」还是「选择器属性已变」。
只读（点开日期面板，不提交查询）。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_ticket_date_probe.json")


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1200}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(20000)

        LoginPage(page).login()
        page.wait_for_timeout(3000)

        # 工单中心 -> 工单管理
        for lb in ("工单中心", "工单管理"):
            try:
                loc = page.get_by_text(lb, exact=True).last
                if loc.count():
                    loc.click()
                    page.wait_for_timeout(3000)
                    print(f"clicked {lb}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"click {lb} err: {exc}"[:120], flush=True)

        r["url"] = page.url[:200]
        body = page.locator("body").inner_text()
        r["body_head"] = body[:700]

        # 找开始时间输入框
        start = page.get_by_placeholder("开始时间", exact=True)
        r["start_count"] = start.count()
        if start.count():
            start.click()
            page.wait_for_timeout(2500)
            # 统计所有 td[title]
            cells = page.locator("td[title]")
            n = cells.count()
            r["td_title_count"] = n
            titles = []
            for i in range(min(n, 60)):
                t = cells.nth(i).get_attribute("title")
                if t:
                    titles.append(t)
            r["titles"] = titles
            # 按月统计重复
            from collections import Counter
            dup = {k: v for k, v in Counter(titles).items() if v > 1}
            r["duplicate_days"] = dup
            r["unique_days"] = len(set(titles))
            # 面板容器数量（双月/单月）
            for sel in (".ant-picker-dropdown", "[class*='picker-panel']", "[class*='date-picker']"):
                try:
                    r[f"panel_{sel}"] = page.locator(sel).count()
                except Exception:
                    pass
            page.screenshot(
                path=str(Path("reports/prod-keshang") / "_ticket-date-panel.png"),
                full_page=True,
            )

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"url={r.get('url','')[:120]}", flush=True)
    print(f"start_count={r.get('start_count')} td_title_count={r.get('td_title_count')}", flush=True)
    print(f"unique_days={r.get('unique_days')}", flush=True)
    print(f"duplicate_days={r.get('duplicate_days')}", flush=True)
    print(f"titles_head={ (r.get('titles') or [])[:12] }", flush=True)
    for k, v in r.items():
        if k.startswith("panel_"):
            print(f"{k}={v}", flush=True)
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
