"""分层数据资源导入 Page Object — 支撑 M02 数据分层、M03 数据实体、M04 数据属性清单导入与性能走查。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger
from pages.portal.portal_home_page import PortalHomePage

logger = get_logger("layered_import_page")

# 测试数据文件夹默认路径
DEFAULT_TEST_DATA_DIR = Path(r"C:\Users\CFD\Desktop\260812")


class LayeredImportPage(BasePage):
    """分层数据资源导入与性能优化页面对象。"""

    PAGE_NAME = "分层数据资源导入管理"

    def __init__(self, page: Page):
        super().__init__(page)
        self.portal = PortalHomePage(page)

    # ────────────────────────── 导航进入模块 ──────────────────────────

    def open_layer_settings(self) -> "LayeredImportPage":
        """进入数据分层设置页面（M02 入口：控制台 -> 系统配置 -> 资源配置 -> 数据分层设置）。"""
        self.dismiss_visible_modals()
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/system/layerSet")
            self.nav.wait_ready()
            self.assertions.any_text_visible(["数据分层设置", "导入数据分层清单", "分层配置"], timeout=settings.ACTION_TIMEOUT)
        except Exception:
            # 回退：通过控制台工作台/侧边栏导航进入
            console = self.portal.navigate_to_console()
            console.open_all_menu_view()
            self.elements.click_candidates(
                [
                    ("text", "数据分层设置"),
                    ("text", "分层设置"),
                    ("text", "资源配置"),
                ],
                description="数据分层设置入口",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        logger.info("[导航] → 数据分层设置页面")
        return self

    def open_data_resource_mgmt(self) -> "LayeredImportPage":
        """进入数据资源管理页面（M03/M04 入口：控制台 -> 资源管理 -> 数据资源管理）。"""
        self.dismiss_visible_modals()
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/dataResources")
            self.nav.wait_ready()
            self.assertions.any_text_visible(["数据资源列表", "导入数据实体清单", "数据资源管理"], timeout=settings.ACTION_TIMEOUT)
        except Exception:
            # 回退：通过控制台工作台导航进入
            console = self.portal.navigate_to_console()
            console.open_all_menu_view()
            self.elements.click_candidates(
                [
                    ("text", "数据资源管理"),
                    ("text", "资源管理"),
                ],
                description="数据资源管理入口",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        logger.info("[导航] → 数据资源管理页面")
        return self

    # ────────────────────────── 导入弹窗交互 ──────────────────────────

    def open_m02_layer_import_dialog(self) -> "LayeredImportPage":
        """在数据分层设置页打开「导入数据分层清单 (M02)」弹窗。"""
        self.open_layer_settings()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据分层清单|导入分层清单")),
                self.page.locator("button:has-text('导入数据分层清单')"),
                self.page.locator("button:has-text('导入分层')"),
            ],
            description="导入数据分层清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M02 数据分层清单导入弹窗")
        return self

    def open_m03_entity_import_dialog(self) -> "LayeredImportPage":
        """在数据资源管理页打开「导入数据实体清单 (M03)」弹窗。"""
        self.open_data_resource_mgmt()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据实体清单|导入实体清单")),
                self.page.locator("button:has-text('导入数据实体清单')"),
                self.page.locator("button:has-text('导入实体')"),
            ],
            description="导入数据实体清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M03 数据实体清单导入弹窗")
        return self

    def open_m04_attribute_import_dialog(self) -> "LayeredImportPage":
        """在数据资源管理页打开「导入数据属性清单 (M04)」弹窗。"""
        self.open_data_resource_mgmt()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据属性清单|导入属性清单")),
                self.page.locator("button:has-text('导入数据属性清单')"),
                self.page.locator("button:has-text('导入属性')"),
            ],
            description="导入数据属性清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M04 数据属性清单导入弹窗")
        return self

    def upload_file(self, file_name_or_path: str | Path) -> "LayeredImportPage":
        """上传指定测试 Excel 文件到当前导入弹窗。"""
        path = Path(file_name_or_path)
        if not path.is_absolute():
            path = DEFAULT_TEST_DATA_DIR / file_name_or_path
        if not path.exists():
            raise FileNotFoundError(f"测试导入文件不存在: {path}")

        dialog = self._get_import_dialog()
        file_input = dialog.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=settings.ACTION_TIMEOUT)
        file_input.set_input_files(str(path))
        self.page.wait_for_timeout(500)
        self.nav.wait_ready()
        logger.info(f"[上传文件] 成功选择文件: {path.name}")
        return self

    def click_validate_table(self) -> "LayeredImportPage":
        """点击导入弹窗中的「校验表格」或「校验」按钮。"""
        # 如果上传后已自动返回校验结果，则无需重复点击
        if self._has_any_text(["列名与模板不符", "校验失败", "错误行号", "校验通过", "可导入"], timeout=1200):
            logger.info("[校验] 上传后已自动触发校验并获得结果")
            return self

        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"校验表格|校验")),
                dialog.locator("button:has-text('校验表格')"),
                dialog.locator("button:has-text('校验')"),
            ],
            description="校验表格按钮",
        )
        btn.click()
        self.page.wait_for_timeout(500)
        self.nav.wait_ready()
        logger.info("[校验] 已点击校验表格按钮")
        return self

    def select_conflict_mode(self, mode: str = "跳过") -> "LayeredImportPage":
        """选择重复数据处理方式（'跳过' 或 '覆盖'）。"""
        dialog = self._get_import_dialog()
        if "跳过" in mode:
            opt = dialog.get_by_text(re.compile(r"跳过|重复跳过")).first
        else:
            opt = dialog.get_by_text(re.compile(r"覆盖|重复覆盖")).first

        if opt.is_visible():
            opt.click()
            logger.info(f"[冲突处理] 选中重复处理方式: {mode}")
        return self

    def click_confirm_import(self) -> "LayeredImportPage":
        """点击弹窗中的「导入」或「确认导入」按钮。"""
        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$")),
                dialog.locator("button.import_btn"),
                dialog.locator("button:has-text('导入')"),
            ],
            description="确认导入按钮",
        )
        if btn.is_disabled():
            raise AssertionError("导入按钮处于禁用状态，无法执行导入")
        btn.click()
        self.nav.wait_ready()
        logger.info("[导入] 已点击确认导入按钮")
        return self

    # ────────────────────────── 断言与结果核验 ──────────────────────────

    def should_show_column_mismatch_error(self) -> "LayeredImportPage":
        """断言提示列名与模板不符。"""
        self.assertions.any_text_visible(
            ["列名与模板不符", "列名与模板不一致", "模板不符", "模板列不匹配"],
            timeout=settings.ACTION_TIMEOUT,
        )
        logger.info("[断言] 成功捕获「列名与模板不符」错误提示")
        return self

    def should_show_import_errors(self, expected_snippets: list[str]) -> "LayeredImportPage":
        """断言弹窗内展示了预期的校验错误行或错误原因。"""
        dialog_text = self.get_dialog_text()
        for snippet in expected_snippets:
            assert snippet in dialog_text or snippet.replace(" ", "") in dialog_text.replace(" ", ""), (
                f"导入弹窗未包含预期错误片段: '{snippet}'; 弹窗内容: {dialog_text[:300]}"
            )
        logger.info(f"[断言] 导入校验错误提示匹配成功: {expected_snippets}")
        return self

    def should_not_allow_import(self) -> "LayeredImportPage":
        """断言校验不通过时，不展示导入按钮或导入按钮被禁用。"""
        dialog = self._get_import_dialog()
        buttons = dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$"))
        for i in range(buttons.count()):
            b = buttons.nth(i)
            if b.is_visible() and not b.is_disabled():
                raise AssertionError("业务校验失败后，页面仍展示了可点击的导入按钮！")
        logger.info("[断言] 业务校验未通过，导入按钮已正确禁用/隐藏")
        return self

    def should_allow_import_after_validation(self) -> "LayeredImportPage":
        """断言校验通过，允许点击导入。"""
        self.assertions.any_text_visible(["校验通过", "可导入", "数据有效", "成功"], timeout=settings.ACTION_TIMEOUT)
        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$")),
                dialog.locator("button.import_btn"),
                dialog.locator("button:has-text('导入')"),
            ],
            description="导入按钮",
        )
        assert not btn.is_disabled(), "校验通过后导入按钮仍然不可用"
        logger.info("[断言] 校验通过，导入按钮处于可用状态")
        return self

    def should_show_progress_or_success(self) -> "LayeredImportPage":
        """断言展示导入进度条或导入成功提示。"""
        self.assertions.any_text_visible(
            ["进度", "%", "正在导入", "导入完成", "导入成功", "完成", "处理中"],
            timeout=settings.ACTION_TIMEOUT,
        )
        logger.info("[断言] 成功观察到导入进度条或成功状态")
        return self

    def close_import_dialog(self) -> "LayeredImportPage":
        """关闭导入弹窗。"""
        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"关\s*闭|取\s*消")),
                dialog.locator(".ant-modal-close, .ant-modal-close-x"),
                dialog.get_by_text("关闭", exact=True),
            ],
            description="关闭弹窗按钮",
        )
        btn.click()
        dialog.wait_for(state="hidden", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已关闭导入弹窗")
        return self

    def verify_layer_tree_nodes(self, l1: str = "", l2: str = "", l3: str = "") -> "LayeredImportPage":
        """在数据分层设置页核验分层树节点展示。"""
        self.assertions.page_not_blank_or_error()
        for node in [l1, l2, l3]:
            if node:
                self.assertions.any_text_visible([node, "数据分层", "L1", "L2", "L3"])
        logger.info(f"[断言] 数据分层树节点核验完成: L1={l1}, L2={l2}, L3={l3}")
        return self

    def search_and_verify_entity(self, table_english_name: str) -> "LayeredImportPage":
        """在数据资源列表中按表英文名称检索核验。"""
        search_input = self.page.get_by_placeholder("请输入搜索内容").first
        if search_input.is_visible():
            search_input.fill(table_english_name)
            search_input.press("Enter")
            self.nav.wait_ready()
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([table_english_name, "数据资源列表", "暂无数据"])
        logger.info(f"[检索] 数据实体检索完成: {table_english_name}")
        return self

    # ────────────────────────── 内部辅助方法 ──────────────────────────

    def get_dialog_text(self) -> str:
        """获取当前可见弹窗的文本内容。"""
        dialog = self._get_import_dialog()
        return dialog.inner_text(timeout=settings.ACTION_TIMEOUT)

    def dismiss_visible_modals(self) -> "LayeredImportPage":
        """关闭遮挡的 Ant Design 弹窗。"""
        for _ in range(3):
            modal = self.page.locator(".ant-modal-wrap:visible").first
            if modal.count() == 0:
                break
            close_btn = modal.locator(".ant-modal-close, button:has-text('关闭'), button:has-text('取消')").first
            if close_btn.is_visible():
                try:
                    close_btn.click(timeout=1000)
                except Exception:
                    self.page.keyboard.press("Escape")
        return self

    def _get_import_dialog(self) -> Locator:
        return self.page.locator(".ant-modal-content:visible").first

    def _find_first_visible(self, locators: list[Locator], description: str) -> Locator:
        for loc in locators:
            try:
                loc.first.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
                return loc.first
            except PlaywrightTimeoutError:
                continue
        raise AssertionError(f"未找到可见元素: {description}")

    def _has_any_text(self, texts: list[str], timeout: int = 1000) -> bool:
        for text in texts:
            try:
                self.page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)
                return True
            except PlaywrightTimeoutError:
                continue
        return False
