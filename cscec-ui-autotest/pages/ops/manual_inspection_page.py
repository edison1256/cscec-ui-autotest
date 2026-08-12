"""
人工巡检页 — 运维巡检模块

封装巡检相关的所有操作：
- 导航到巡检页面
- 选择巡检项目
- 填写巡检结果
- 上传巡检文件
- 保存巡检记录
"""

from playwright.sync_api import Page

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("manual_inspection_page")


class ManualInspectionPage(BasePage):
    """人工巡检页"""

    PAGE_NAME = "人工巡检"
    PAGE_URL_PATTERN = "inspection|manual"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航 ──

    def navigate_from_menu(self) -> "ManualInspectionPage":
        """从菜单导航到人工巡检页面"""
        self.elements.click_candidates(
            [
                ("text", "运维巡检"),
                ("css", "a[href*='inspection']"),
            ],
            description="运维巡检菜单",
        )
        self.nav.wait_ready()

        self.elements.click_candidates(
            [
                ("text", "人工巡检"),
                ("css", "a[href*='manual']"),
            ],
            description="人工巡检子菜单",
        )
        self.nav.wait_ready()
        return self

    # ── 巡检操作 ──

    def select_inspection_project(self, project_name: str) -> "ManualInspectionPage":
        """选择巡检项目"""
        # 点击项目下拉框
        dropdown = self.elements.find_candidates(
            [
                ("css", ".ant-select-selector"),
                ("css", "input[placeholder*='项目']"),
            ],
            description="项目下拉框",
        )
        if dropdown:
            self.antd.select_dropdown(dropdown, project_name)
        return self

    def check_all_normal(self) -> "ManualInspectionPage":
        """勾选所有巡检项为【正常】"""
        checkboxes = self.page.locator(".ant-checkbox-wrapper")
        count = checkboxes.count()
        for i in range(count):
            cb = checkboxes.nth(i)
            if not cb.locator("input[type='checkbox']").is_checked():
                cb.click()
        logger.info(f"[巡检] 勾选了 {count} 个正常项")
        return self

    def fill_inspection_remark(self, remark: str) -> "ManualInspectionPage":
        """填写巡检备注"""
        textarea = self.elements.find_candidates(
            [
                ("css", "textarea"),
                ("placeholder", "请输入备注"),
            ],
            description="备注输入框",
        )
        if textarea:
            textarea.fill(remark)
        return self

    def upload_inspection_file(self, file_path: str) -> "ManualInspectionPage":
        """上传巡检附件"""
        self.elements.upload_file(
            button_candidates=[
                ("css", ".ant-upload button"),
                ("text", "上传文件"),
                ("css", "input[type='file']"),
            ],
            file_path=file_path,
        )
        return self

    def save_inspection(self) -> "ManualInspectionPage":
        """保存巡检记录"""
        self.antd.click_save_button()
        self.antd.click_confirm_if_present()
        self.nav.wait_ready()
        logger.info("[巡检] 保存完成")
        return self

    # ── 完整流程 ──

    def do_inspection(
        self,
        project_name: str,
        remark: str = "",
        file_path: str = "",
    ) -> "ManualInspectionPage":
        """
        执行完整巡检流程

        Args:
            project_name: 巡检项目名称
            remark: 备注内容
            file_path: 附件路径
        """
        self.select_inspection_project(project_name)
        self.check_all_normal()
        if remark:
            self.fill_inspection_remark(remark)
        if file_path:
            self.upload_inspection_file(file_path)
        self.save_inspection()
        return self

    # ── Assertions ──

    def should_be_on_inspection_page(self) -> "ManualInspectionPage":
        """断言在巡检页面"""
        current_url = self.page.url.lower()
        assert "inspection" in current_url or "manual" in current_url, \
            f"期望在巡检页面，当前 URL: {self.page.url}"
        self.assertions.any_text_visible(["人工巡检", "巡检项目", "巡检记录"])
        logger.info("[断言] 当前在人工巡检页")
        return self

    def should_save_succeed(self) -> "ManualInspectionPage":
        """断言保存成功"""
        success_loc = self.elements.find_candidates(
            [
                ("text", "保存成功"),
                ("css", ".ant-message-success"),
            ],
            description="保存成功提示",
            timeout=5000,
        )
        assert success_loc is not None, "未检测到保存成功提示"
        logger.info("[断言] 巡检保存成功")
        return self
