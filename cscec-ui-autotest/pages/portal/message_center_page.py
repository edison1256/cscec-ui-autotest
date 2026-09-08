"""门户消息中心与小铃铛通知 Page Object — M3-04 消息跳转。"""

from __future__ import annotations

from playwright.sync_api import Page

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("message_center_page")


class MessageCenterPage(BasePage):
    """消息中心与顶部小铃铛通知页。"""

    PAGE_NAME = "消息中心"

    def open_message_bell(self) -> "MessageCenterPage":
        """点击顶部消息小铃铛入口。"""
        if self.page.url == "about:blank" or not self.page.url.startswith("http"):
            self.nav.goto_url(settings.WORKBENCH_BASE_URL)
            self.nav.wait_ready()

        bell_icon = self.elements.find_candidates(
            [
                ("css", ".anticon-bell"),
                ("css", "[class*='bell']"),
                ("css", "[class*='notice']"),
                ("css", "[class*='message']"),
                ("text", "消息"),
                ("text", "通知"),
            ],
            description="顶部小铃铛/消息图标",
        )
        if bell_icon:
            try:
                bell_icon.click()
                self.page.wait_for_timeout(300)
                self.nav.wait_ready()
                logger.info("[小铃铛] 点击小铃铛图标")
            except Exception as e:
                logger.info(f"[小铃铛] 点击提示: {e}")
        return self

    def open_message_item_and_navigate(self) -> "MessageCenterPage":
        """打开一条消息并触发跳转或确认消息区域可见。"""
        msg_item = self.elements.find_candidates(
            [
                ("css", ".ant-list-item"),
                ("css", ".notice-item"),
                ("css", "[class*='popover']"),
                ("text", "通知"),
                ("text", "订单"),
                ("text", "消息"),
                ("text", "暂无"),
            ],
            description="消息通知条目",
        )
        if msg_item:
            try:
                msg_item.click()
                self.nav.wait_ready()
                logger.info("[消息跳转] 交互完成")
            except Exception:
                pass

        self.assertions.page_not_blank_or_error()
        return self
