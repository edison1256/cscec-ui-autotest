"""个人工作台（suitKey=portal）通用列表捕获。

背景（2026-11-17 用户走查）：个人工作台下多个列表返回了全量数据。
实测四个越权点：

  被订阅的订单  workbench/rsc/app/apply/history/list  828 条 / 26 租户 / 57 用户
  云产品订阅    cloud/applyList                        554 条 / 8 租户 / 10 用户
  数据资产订阅  workbench/rsc/data/apply/history/list   16 条 / 2 租户 / 6 用户
  订单管理      order/page                           2376 条 / creator 12 人

前三个用 tenantNo 判归属，「订单管理」没有 tenantNo，只有 creator（用户账号）。

导航边界：只直链到「工作台首页」（等价于用户点入口进系统），
之后一律点击「常用模块」卡片，绝不拼二级页路由。
"""

from __future__ import annotations

import re

from playwright.sync_api import Response

from config.settings import settings
from core.base_page import BasePage
from pages.portal.portal_home_page import CONSOLE_WORKBENCH_ROUTE


class PersonalWorkbenchPage(BasePage):
    """个人工作台列表页对象。"""

    PAGE_NAME = "个人工作台"

    def open_home(self) -> "PersonalWorkbenchPage":
        """打开个人工作台首页。"""
        self.page.goto(
            settings.console_url(CONSOLE_WORKBENCH_ROUTE),
            wait_until="domcontentloaded",
            timeout=settings.NAVIGATION_TIMEOUT,
        )
        self.page.wait_for_timeout(3500)
        for _ in range(2):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)
        return self

    def login_info(self) -> dict:
        """读当前登录态（userNo / tenantNo / orgName）。"""
        try:
            info = self.page.evaluate(
                "() => { const s = localStorage.getItem('__login_info__');"
                " return s ? JSON.parse(s) : null; }"
            )
        except Exception:
            return {}
        return info if isinstance(info, dict) else {}

    def capture_list(
        self,
        entry_label: str,
        api_hint: str,
        *,
        timeout_s: float = 15.0,
    ) -> tuple[list[dict], int | None]:
        """点开「常用模块」里的入口，捕获匹配 api_hint 的列表响应。

        api_hint 用子串匹配（大小写不敏感），因为它只需要区分同一轮里
        工作台外壳预加载的数据与页面自身的列表请求。

        注意：个人工作台任何页面都会先调
        `workbench/rsc/app/apply/history/list`（外壳预加载，828 条 / 26 租户），
        所以匹配必须精确到目标接口，不能只等「任意列表响应」。
        """
        captured: dict[str, Response] = {}
        pattern = re.compile(re.escape(api_hint), re.I)

        def _on_response(response: Response) -> None:
            if not pattern.search(response.url):
                return
            # 只存 Response，回调内不读 body（sync API 下读 body 会死锁）
            captured["response"] = response

        self.page.on("response", _on_response)
        try:
            self.open_home()
            loc = self.page.get_by_text(entry_label, exact=True).last
            assert loc.count(), f"个人工作台未找到入口「{entry_label}」"
            loc.click()
            waited = 0.0
            while "response" not in captured and waited < timeout_s:
                self.page.wait_for_timeout(500)
                waited += 0.5
        finally:
            self.page.remove_listener("response", _on_response)

        response = captured.get("response")
        assert response is not None, (
            f"未捕获到「{entry_label}」的列表接口（hint={api_hint}）；"
            "接口路径可能已变更"
        )
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        assert isinstance(data, dict), f"「{entry_label}」返回结构异常（data 不是对象）"
        rows = data.get("list") or data.get("records") or data.get("rows")
        assert isinstance(rows, list), f"「{entry_label}」未返回 list 字段"
        total = data.get("total")
        return rows, (int(total) if str(total).isdigit() else None)
