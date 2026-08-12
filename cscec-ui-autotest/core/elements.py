"""Element lookup, click, upload, and screenshot helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page

from config.settings import settings
from core.locator_strategy import find_first_visible
from core.logger import get_logger


logger = get_logger("elements")


class ElementHelper:
    """Operations built on the candidate locator strategy."""

    def __init__(self, page: Page):
        self.page = page

    def find_candidates(
        self,
        candidates: list[tuple[str, str]],
        description: str = "",
        timeout: int = 5000,
    ) -> Optional[Locator]:
        return find_first_visible(self.page, candidates, timeout, description)

    def click_candidates(
        self,
        candidates: list[tuple[str, str]],
        description: str = "",
        timeout: int = 5000,
        required: bool = True,
    ) -> Optional[Locator]:
        locator = self.find_candidates(candidates, description=description, timeout=timeout)
        if locator:
            locator.click()
            logger.info(f"[Click] {description}")
            return locator
        if required:
            raise AssertionError(f"No clickable element found: {description or candidates}")
        return None

    def upload_file(
        self,
        button_candidates: list[tuple[str, str]],
        file_path: str,
    ) -> "ElementHelper":
        locator = self.find_candidates(button_candidates, description="upload button")
        if not locator:
            raise AssertionError(f"Upload button not found for file: {file_path}")

        with self.page.expect_file_chooser(timeout=10000) as chooser_info:
            locator.click()
        chooser_info.value.set_files(file_path)
        logger.info(f"[Upload] {file_path}")
        return self

    def safe_screenshot(self, filename: str) -> "ElementHelper":
        try:
            settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            path = Path(settings.SCREENSHOTS_DIR) / filename
            self.page.screenshot(path=str(path), full_page=True)
            logger.info(f"[Screenshot] {path}")
        except Exception as exc:
            logger.warning(f"[Screenshot failed] {exc}")
        return self
