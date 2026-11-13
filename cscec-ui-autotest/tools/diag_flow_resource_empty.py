"""生产只读诊断：流程监控 / 资源概览「接口未返回有效记录」细查。

对每个目标接口记录：请求方法、请求参数、HTTP 状态、业务 code、
data 的类型与键、list 长度、total 值、首条记录字段名（不含业务值）。

只做导航与读取，不点任何提交/保存/删除按钮。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_diag_flow_resource.json")

TARGETS = {
    "/workflow/process/getProcessedMonitor": "flow_monitor",
    "/workflow/process/getProcessFlow": "flow_management",
    "/metrology/resource/overview/page": "resource_overview",
    "/metrology/tenant/apply/list": "subscription_overview",
}


def shape(payload):
    """只描述结构，不落业务值。"""
    info = {"root_type": type(payload).__name__}
    if not isinstance(payload, dict):
        return info
    info["code"] = payload.get("code")
    info["msg"] = str(payload.get("message") or payload.get("msg") or "")[:60]
    data = payload.get("data")
    info["data_type"] = type(data).__name__
    if isinstance(data, dict):
        info["data_keys"] = list(data.keys())[:12]
        rows = data.get("list") or data.get("records") or data.get("rows")
        if isinstance(rows, list):
            info["list_len"] = len(rows)
            info["total"] = data.get("total")
            info["pages"] = data.get("pages")
            info["pageNum"] = data.get("pageNum") or data.get("current")
            info["pageSize"] = data.get("pageSize") or data.get("size")
            if rows and isinstance(rows[0], dict):
                info["row_fields"] = list(rows[0].keys())[:20]
    elif isinstance(data, list):
        info["list_len"] = len(data)
        if data and isinstance(data[0], dict):
            info["row_fields"] = list(data[0].keys())[:20]
    return info


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"targets": {}}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            viewport={"width": 1680, "height": 1050}, ignore_https_errors=True
        )
        page = ctx.new_page()
        page.set_default_timeout(25000)

        seen = {}

        def on_response(resp):
            url = resp.url
            for pat, key in TARGETS.items():
                if pat not in url:
                    continue
                if key in seen:
                    continue
                item = {
                    "url": url[:220],
                    "method": resp.request.method,
                    "status": resp.status,
                }
                # 请求参数：GET 看 query，POST 看 post_data
                try:
                    if resp.request.method.upper() == "POST" and resp.request.post_data:
                        pd = resp.request.post_data
                        item["post_data"] = pd[:500]
                except Exception:
                    pass
                if "?" in url:
                    item["query"] = url.split("?", 1)[1][:300]
                try:
                    body = resp.json()
                    item["shape"] = shape(body)
                except Exception:
                    item["shape"] = {"note": "非 JSON 响应"}
                seen[key] = item

        page.on("response", on_response)

        LoginPage(page).login()
        page.wait_for_timeout(2500)
        print("console login ok", flush=True)

        def click_path(*labels, wait=3000):
            for lb in labels:
                ok = False
                for factory in (
                    lambda: page.get_by_role("menuitem", name=lb, exact=True).last,
                    lambda: page.get_by_text(lb, exact=True).last,
                ):
                    try:
                        loc = factory()
                        if loc.count() and loc.is_visible(timeout=2500):
                            loc.click()
                            page.wait_for_timeout(wait)
                            ok = True
                            break
                    except Exception:
                        continue
                print(f"   click {lb}: {ok}", flush=True)

        # ---- 流程监控 ----
        print("\n[1] 审批流程 -> 流程监控", flush=True)
        try:
            click_path("审批流程", "流程监控")
            page.wait_for_timeout(4000)
            r["flow_monitor_url"] = page.url[:200]
            r["flow_monitor_body"] = page.locator("body").inner_text()[:900]
            page.screenshot(
                path=str(Path("reports/prod-keshang") / "_diag-flow-monitor.png"),
                full_page=True,
            )
        except Exception as exc:  # noqa: BLE001
            r["flow_monitor_error"] = f"{type(exc).__name__}: {exc}"[:250]

        # ---- 资源概览 ----
        print("\n[2] 计量统计 -> 租户的资源 -> 资源概览", flush=True)
        try:
            click_path("计量统计", "租户的资源", "资源概览")
            page.wait_for_timeout(4000)
            r["resource_url"] = page.url[:200]
            r["resource_body"] = page.locator("body").inner_text()[:900]
            page.screenshot(
                path=str(Path("reports/prod-keshang") / "_diag-resource-overview.png"),
                full_page=True,
            )
        except Exception as exc:  # noqa: BLE001
            r["resource_error"] = f"{type(exc).__name__}: {exc}"[:250]

        r["targets"] = seen
        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n===== 接口实测 =====", flush=True)
    for key, item in seen.items():
        print(f"\n[{key}] {item['method']} {item['status']}", flush=True)
        print("  url:", item["url"][:150], flush=True)
        if item.get("post_data"):
            print("  post:", item["post_data"][:200], flush=True)
        if item.get("query"):
            print("  query:", item["query"][:200], flush=True)
        print("  shape:", json.dumps(item["shape"], ensure_ascii=False)[:400], flush=True)

    missing = [k for k in TARGETS.values() if k not in seen]
    if missing:
        print(f"\n未捕获到: {missing}", flush=True)
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
