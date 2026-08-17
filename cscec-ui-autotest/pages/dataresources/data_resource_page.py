"""Data resource management page object."""

from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger


logger = get_logger("data_resource_page")


_IMPORT_DIALOGS = {
    "M02": {
        "button_pattern": r"导入数据分层清单(?:\(M02\))?",
        "title": "导入数据分层清单",
    },
    "M03": {
        "button_pattern": r"导入数据实体清单",
        "title": "导入数据实体清单",
    },
    "M04": {
        "button_pattern": r"导入数据属性清单",
        "title": "导入数据属性清单",
    },
}


class DataResourcePage(BasePage):
    """控制台数据资源管理页。"""

    PAGE_NAME = "数据资源管理"
    PAGE_URL_PATTERN = "dataResources"

    def open_from_console_home(self) -> "DataResourcePage":
        """从控制台工作台进入数据资源管理。"""
        self.dismiss_visible_modals()
        self._click_exact_text("数据资源管理")
        try:
            self.page.wait_for_url(re.compile(r"dataResources"), timeout=settings.NAVIGATION_TIMEOUT)
        except PlaywrightTimeoutError:
            pass
        self.nav.wait_ready()
        self.assertions.any_text_visible(["数据资源列表", "导入数据实体清单", "导入实体", "导入数据实体"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 数据资源管理")
        return self

    def open_layer_settings_from_console_home(self) -> "DataResourcePage":
        """从控制台工作台进入数据分层设置。"""
        self.dismiss_visible_modals()
        entry = self.page.get_by_text("数据分层设置", exact=True).last
        entry.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        entry.click()
        try:
            self.page.wait_for_url(re.compile(r"layerSet"), timeout=settings.NAVIGATION_TIMEOUT)
        except PlaywrightTimeoutError:
            pass
        self.nav.wait_ready()
        self.assertions.any_text_visible(["数据分层设置", "导入数据分层清单"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 数据分层设置")
        return self

    def dismiss_visible_modals(self) -> "DataResourcePage":
        """Close visible Ant Design modals that block console navigation."""
        for _ in range(5):
            modal_wraps = self.page.locator(".ant-modal-wrap:visible")
            if modal_wraps.count() == 0:
                return self

            modal_wrap = modal_wraps.first
            if not self._dismiss_modal_once(modal_wrap):
                self.page.keyboard.press("Escape")

            try:
                modal_wrap.wait_for(state="hidden", timeout=3000)
            except PlaywrightTimeoutError:
                self.page.keyboard.press("Escape")
                try:
                    modal_wrap.wait_for(state="hidden", timeout=3000)
                except PlaywrightTimeoutError:
                    logger.warning("[导航] 可见弹窗未完全关闭，继续尝试关闭下一个弹窗")

        remaining = self.page.locator(".ant-modal-wrap:visible")
        if remaining.count() == 0:
            return self

        try:
            remaining_text = _normalize_text(remaining.first.inner_text(timeout=1000))[:200]
        except Exception:
            remaining_text = "<unreadable>"
        raise AssertionError(f"可见弹窗仍遮挡控制台导航: {remaining_text}")
        return self

    def _dismiss_modal_once(self, modal_wrap: Locator) -> bool:
        candidates = [
            modal_wrap.locator(".ant-modal-close").first,
            modal_wrap.locator(".ant-modal-close-x").first,
            modal_wrap.get_by_role(
                "button",
                name=re.compile(r"^确\s*定$|^关\s*闭$|^取消$|^取消导入$|^知道了$|^我知道了$"),
            ).first,
        ]
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=500)
                candidate.click(timeout=1500)
                return True
            except Exception:
                continue
        return False

    def search_by_keyword(self, keyword: str) -> "DataResourcePage":
        """Search data resources by the shared keyword input."""
        search_input = self.page.get_by_placeholder("请输入搜索内容").first
        search_input.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        search_input.fill(keyword)
        search_input.press("Enter")
        self._wait_for_page_idle()
        return self

    def should_show_no_search_results(self) -> "DataResourcePage":
        """Assert current table search result is empty."""
        self.page.get_by_text("暂无数据", exact=False).first.wait_for(
            state="visible",
            timeout=settings.ACTION_TIMEOUT,
        )
        self.page.wait_for_function(
            """() => Array.from(document.querySelectorAll('.ant-table-row'))
                .filter((row) => !!(row.offsetWidth || row.offsetHeight || row.getClientRects().length))
                .length === 0""",
            timeout=settings.ACTION_TIMEOUT,
        )
        return self

    def open_m03_import(self) -> "DataResourcePage":
        """Open M03 data entity import dialog."""
        return self.open_import_dialog("M03")

    def open_import_dialog(self, import_type: str) -> "DataResourcePage":
        """Open an import dialog by import type, such as M03 or M04."""
        spec = self._import_spec(import_type)
        button = self.page.get_by_role("button", name=re.compile(spec["button_pattern"])).first
        button.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        button.click()
        self._import_dialog(import_type).wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info(f"[导入] 打开{spec['title']}弹窗")
        return self

    def should_show_import_dialog(self, import_type: str) -> "DataResourcePage":
        """Assert the target import dialog is visible."""
        spec = self._import_spec(import_type)
        dialog = self._import_dialog(import_type)
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        if spec["title"] not in dialog.inner_text(timeout=settings.ACTION_TIMEOUT):
            raise AssertionError(f"未看到导入弹窗标题: {spec['title']}")
        return self

    def should_have_import_upload(self) -> "DataResourcePage":
        """Assert the visible import dialog has an upload control."""
        dialog = self._import_dialog()
        dialog.locator("input[type='file']").first.wait_for(state="attached", timeout=settings.ACTION_TIMEOUT)
        self.assertions.any_text_visible(["上传文件", "上传", "选择文件", "点击上传"], timeout=settings.ACTION_TIMEOUT)
        return self

    def download_import_template(self, output_dir: Path, import_type: str) -> Path:
        """Download the current import dialog template and return its saved path."""
        self._import_spec(import_type)
        output_dir.mkdir(parents=True, exist_ok=True)
        dialog = self._import_dialog(import_type)
        download_trigger = self._first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"下载模板|下载模版|获取模板|导出模板|下载|导出")),
                dialog.get_by_role("link", name=re.compile(r"下载模板|下载模版|获取模板|导出模板|下载|导出")),
                dialog.locator("button:has-text('下载模板'), button:has-text('下载模版'), button:has-text('模板'), button:has-text('下载')"),
                dialog.locator("a:has-text('下载模板'), a:has-text('下载模版'), a:has-text('模板'), a:has-text('下载')"),
            ],
            "下载模板按钮",
        )
        with self.page.expect_download(timeout=settings.ACTION_TIMEOUT) as download_info:
            download_trigger.click()
        download = download_info.value
        target = output_dir / download.suggested_filename
        if target.exists():
            target = output_dir / f"{target.stem}_{int(time.time())}{target.suffix}"
        download.save_as(str(target))
        logger.info(f"[导入] 下载{import_type}模板: {target}")
        return target

    def upload_import_file(self, file_path: str) -> "DataResourcePage":
        """Upload a file in the visible import dialog."""
        path = Path(file_path)
        if not path.exists():
            raise AssertionError(f"导入文件不存在: {file_path}")

        dialog = self._import_dialog()
        dialog.locator("input[type='file']").first.set_input_files(str(path))
        self._wait_for_page_idle()
        self.page.get_by_text(path.name, exact=False).first.wait_for(
            state="visible",
            timeout=settings.ACTION_TIMEOUT,
        )
        return self

    def click_validate_table(self) -> "DataResourcePage":
        """Click the table validation button after upload."""
        if self._has_any_text(["列名与模板不符", "列名与模板不一致", "模板不符", "模板不一致"], timeout=1500):
            logger.info("[导入校验] 上传后已自动返回列名错误")
            return self
        if self._has_any_text(["校验失败", "错误行号", "错误 1 行", "错误1行"], timeout=1500):
            logger.info("[导入校验] 上传后已自动返回业务校验错误")
            return self
        if self._has_any_text(["校验通过", "可导入"], timeout=1500):
            logger.info("[导入校验] 上传后已自动返回校验通过")
            return self

        dialog = self._import_dialog()
        button = self._first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"校验表格")),
                dialog.get_by_role("button", name=re.compile(r"校验")),
                dialog.locator("button:has-text('校验表格')"),
                dialog.locator("button:has-text('校验')"),
            ],
            "校验表格按钮",
        )
        button.click()
        self._wait_for_page_idle()
        return self

    def should_show_column_mismatch_error(self) -> "DataResourcePage":
        """Assert the import dialog shows a template column mismatch error."""
        self.assertions.any_text_visible(
            ["列名与模板不符", "列名与模板不一致", "模板不符", "模板不一致"],
            timeout=settings.ACTION_TIMEOUT,
        )
        return self

    def should_show_import_errors(self, expected_texts: list[str]) -> "DataResourcePage":
        """Assert all expected error snippets are visible in the import dialog text."""
        deadline = time.monotonic() + (settings.ACTION_TIMEOUT / 1000)
        last_text = ""
        while time.monotonic() < deadline:
            last_text = self.import_dialog_text()
            normalized = _normalize_text(last_text)
            if all(expected in last_text or _normalize_text(expected) in normalized for expected in expected_texts):
                return self
            self.page.wait_for_timeout(500)

        missing = [
            expected
            for expected in expected_texts
            if expected not in last_text and _normalize_text(expected) not in _normalize_text(last_text)
        ]
        raise AssertionError(f"导入弹窗未出现预期错误文本: {missing}; 当前文本: {last_text}")

    def import_dialog_text(self) -> str:
        """Return visible import dialog text for UI-only evidence assertions."""
        dialog = self._import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        return dialog.inner_text(timeout=settings.ACTION_TIMEOUT)

    def should_not_allow_import(self) -> "DataResourcePage":
        """Assert exact import action is absent or disabled in the visible import dialog."""
        dialog = self._import_dialog()
        buttons = dialog.get_by_role("button", name=re.compile(r"^导入$"))
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if button.is_visible() and not button.is_disabled():
                raise AssertionError("校验失败后仍存在可点击的导入按钮")
        return self

    def should_allow_import_after_validation(self) -> "DataResourcePage":
        """Assert validation passed and the final import action is available without clicking it."""
        self.assertions.any_text_visible(["校验通过", "可导入"], timeout=settings.ACTION_TIMEOUT)
        dialog = self._import_dialog()
        button = self._first_visible(
            [
                dialog.locator("button.import_btn"),
                dialog.get_by_role("button", name=re.compile(r"^导\s*入$")),
            ],
            "校验通过后的导入按钮",
        )
        if button.is_disabled():
            raise AssertionError("校验通过后导入按钮仍不可用")
        return self

    def close_import_dialog(self) -> "DataResourcePage":
        """Close the visible import dialog."""
        dialog = self._import_dialog()
        button = self._first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"^关\s*闭$|^关闭$")),
                dialog.locator(".ant-modal-close, .ant-modal-close-x"),
                dialog.get_by_role("button", name=re.compile(r"^取消$")),
            ],
            "关闭导入弹窗",
        )
        button.click()
        dialog.wait_for(state="hidden", timeout=settings.ACTION_TIMEOUT)
        return self

    def _import_dialog(self, import_type: str | None = None) -> Locator:
        dialogs = self.page.locator(".ant-modal-content:visible")
        if import_type:
            spec = self._import_spec(import_type)
            dialogs = dialogs.filter(has_text=spec["title"])
        else:
            dialogs = dialogs.filter(has_text=re.compile(r"导入数据分层清单|导入数据实体清单|导入数据属性清单"))
        return dialogs.first

    def _import_spec(self, import_type: str) -> dict[str, str]:
        normalized = import_type.upper()
        if normalized not in _IMPORT_DIALOGS:
            raise AssertionError(f"不支持的导入类型: {import_type}")
        return _IMPORT_DIALOGS[normalized]

    def _click_exact_text(self, text: str) -> None:
        locator = self._first_visible(
            [
                self.page.get_by_text(text, exact=True),
                self.page.locator(f"a:has-text('{text}')"),
                self.page.locator(f"button:has-text('{text}')"),
            ],
            text,
        )
        locator.click()

    def _first_visible(self, candidates: list[Locator], description: str) -> Locator:
        for candidate in candidates:
            try:
                candidate.first.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
                return candidate.first
            except PlaywrightTimeoutError:
                continue
        raise AssertionError(f"{description} 不可见")

    def _has_any_text(self, texts: list[str], timeout: int = 1000) -> bool:
        for text in texts:
            try:
                self.page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)
                return True
            except PlaywrightTimeoutError:
                continue
        return False

    def _wait_for_page_idle(self) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)
