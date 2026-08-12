"""Navigation and wait helpers for page objects."""

from __future__ import annotations

import time

from playwright.sync_api import Page

from config.settings import settings
from core.logger import get_logger


logger = get_logger("navigation")


class NavigationHelper:
    """Small wrapper around common navigation waits."""

    def __init__(self, page: Page):
        self.page = page

    def goto_path(self, path: str = "") -> "NavigationHelper":
        return self.goto_url(f"{settings.BASE_URL}{path}")

    def goto_url(self, url: str) -> "NavigationHelper":
        logger.info(f"[Navigation] {url}")
        self.page.goto(url, timeout=settings.NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        self.wait_ready()
        return self

    def wait_ready(self) -> "NavigationHelper":
        try:
            self.page.wait_for_load_state("networkidle", timeout=settings.NAVIGATION_TIMEOUT)
        except Exception:
            logger.debug("networkidle wait timed out; continuing")

        spinners = self.page.locator(".ant-spin-spinning")
        if spinners.count() > 0:
            try:
                spinners.last.wait_for(state="hidden", timeout=30000)
            except Exception:
                logger.debug("ant-spin wait timed out; continuing")
        return self

    def reload(self) -> "NavigationHelper":
        self.page.reload(timeout=settings.NAVIGATION_TIMEOUT)
        self.wait_ready()
        return self

    def wait_for_url_contains(self, text: str, timeout: int | None = None) -> "NavigationHelper":
        deadline = time.time() + (timeout or settings.NAVIGATION_TIMEOUT) / 1000
        while time.time() < deadline:
            if text.lower() in self.page.url.lower():
                return self
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for URL to contain {text}, current URL: {self.page.url}")
        return self

    def wait_for_network_idle(self, timeout: int = 30000) -> "NavigationHelper":
        self.page.wait_for_load_state("networkidle", timeout=timeout)
        return self

    def wait_until_hidden(self, selector: str, timeout: int = 5000) -> "NavigationHelper":
        self.page.locator(selector).wait_for(state="hidden", timeout=timeout)
        return self

    def wait_for_element_count(
        self,
        selector: str,
        count: int,
        timeout: int = 5000,
    ) -> "NavigationHelper":
        start = time.time()
        while time.time() - start < timeout / 1000:
            if self.page.locator(selector).count() == count:
                return self
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for {selector} count to become {count}")
