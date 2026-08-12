"""Ant Design component helpers used by current page objects."""

from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Locator, Page

from core.elements import ElementHelper
from core.logger import get_logger


logger = get_logger("antd")


class AntDesignHelper:
    """Focused helpers for Ant Design forms, tables, modals, and messages."""

    def __init__(self, page: Page):
        self.page = page
        self.elements = ElementHelper(page)

    def select_dropdown(self, dropdown: Locator, option_text: str) -> "AntDesignHelper":
        dropdown.click()
        option = self.page.locator(".ant-select-dropdown:visible .ant-select-item").filter(
            has_text=option_text
        )
        option.first.click()
        logger.info(f"[Select] {option_text}")
        return self

    def click_query_button(self) -> Optional[Locator]:
        return self.elements.click_candidates(
            [
                ("css", ".ant-btn-primary"),
                ("role", "button[name='查询']"),
                ("text", "查询"),
            ],
            description="query button",
        )

    def click_save_button(self) -> Optional[Locator]:
        return self.elements.click_candidates(
            [
                ("role", "button[name='保存']"),
                ("text", "保存"),
                ("css", ".ant-btn-primary"),
            ],
            description="save button",
        )

    def click_confirm_if_present(self, timeout: int = 3000) -> bool:
        try:
            button = self.page.locator(".ant-modal-confirm-btns .ant-btn-primary")
            button.wait_for(state="visible", timeout=timeout)
            button.click()
            logger.info("[Modal] confirmed")
            return True
        except Exception:
            return False

    def handle_modal(self, action: str = "confirm", timeout: int = 5000) -> bool:
        try:
            modal = self.page.locator(".ant-modal-content:visible")
            modal.wait_for(state="visible", timeout=timeout)
            if action == "confirm":
                button = modal.locator(".ant-btn-primary, button:has-text('确定'), button:has-text('确认')")
            else:
                button = modal.locator(".ant-btn-default, button:has-text('取消')")
            button.first.click()
            logger.info(f"[Modal] {action}")
            return True
        except Exception:
            return False

    def close_modal(self) -> bool:
        try:
            modal = self.page.locator(".ant-modal-content:visible")
            modal.locator(".ant-modal-close, .ant-modal-close-x").first.click()
            logger.info("[Modal] closed")
            return True
        except Exception:
            return False

    def get_modal_text(self) -> str:
        return self.page.locator(".ant-modal-content:visible").inner_text()

    def wait_for_message(self, msg_type: str = "success", timeout: int = 5000) -> bool:
        try:
            selector = f".ant-message-{msg_type}, .ant-notification-{msg_type}"
            self.page.wait_for_selector(selector, timeout=timeout)
            logger.debug(f"[Message] {msg_type}")
            return True
        except Exception:
            return False

    def get_toast_message(self) -> Optional[str]:
        try:
            message = self.page.locator(".ant-message:visible, .ant-notification-notice-message:visible")
            return message.inner_text() if message.is_visible() else None
        except Exception:
            return None

    def click_action_in_row(self, row_idx: int, action_name: str) -> "AntDesignHelper":
        row = self.page.locator(".ant-table-row").nth(row_idx)
        row.locator(f"a:has-text('{action_name}'), button:has-text('{action_name}')").first.click()
        logger.info(f"[Table] row {row_idx}: {action_name}")
        return self

    def get_table_row_count(self) -> int:
        return self.page.locator(".ant-table-row").count()

    def get_cell_text(self, row_idx: int, col_idx: int) -> str:
        return self.page.locator(".ant-table-row").nth(row_idx).locator("td").nth(col_idx).inner_text()

    def get_table_data(self) -> list[dict]:
        header_cells = self.page.locator(".ant-table-thead th")
        headers = [header_cells.nth(i).inner_text().strip() for i in range(header_cells.count())]

        rows_data = []
        rows = self.page.locator(".ant-table-row")
        for row_idx in range(rows.count()):
            row = rows.nth(row_idx)
            cells = row.locator("td")
            row_data = {}
            for col_idx in range(min(cells.count(), len(headers))):
                row_data[headers[col_idx]] = cells.nth(col_idx).inner_text().strip()
            rows_data.append(row_data)
        return rows_data

    def find_row_by_text(self, text: str) -> Optional[int]:
        rows = self.page.locator(".ant-table-row")
        for row_idx in range(rows.count()):
            if text in rows.nth(row_idx).inner_text():
                return row_idx
        return None

    def click_row_by_text(self, text: str, action_name: str) -> bool:
        row_idx = self.find_row_by_text(text)
        if row_idx is None:
            return False
        self.click_action_in_row(row_idx, action_name)
        return True

    def sort_table(self, column_name: str) -> "AntDesignHelper":
        header = self.page.locator(f".ant-table-thead th:has-text('{column_name}')")
        if header.count() > 0:
            header.first.click()
            logger.info(f"[Table] sort: {column_name}")
        return self

    def get_table_pagination_info(self) -> dict:
        pagination = self.page.locator(".ant-pagination")
        if pagination.count() == 0:
            return {"current": 1, "total": 1, "has_next": False}

        try:
            current = pagination.locator(".ant-pagination-item-active").inner_text()
            total_items = pagination.locator(".ant-pagination-total-text").inner_text()
            return {
                "current": int(current),
                "total": total_items,
                "has_next": pagination.locator(
                    ".ant-pagination-next:not(.ant-pagination-disabled)"
                ).count()
                > 0,
            }
        except Exception:
            return {"current": 1, "total": 1, "has_next": False}

    def go_to_page(self, page_num: int) -> "AntDesignHelper":
        button = self.page.locator(".ant-pagination").locator(f".ant-pagination-item:has-text('{page_num}')")
        if button.count() > 0:
            button.first.click()
        return self

    def fill_input(self, label_or_locator: str, value: str, clear_first: bool = True) -> "AntDesignHelper":
        field = self.page.locator(f".ant-form-item-label:has-text('{label_or_locator}')")
        if field.count() > 0:
            field = self.page.locator(
                f".ant-form-item:has(.ant-form-item-label:has-text('{label_or_locator}')) input, "
                f".ant-form-item:has(.ant-form-item-label:has-text('{label_or_locator}')) textarea"
            )
        else:
            field = self.page.locator(
                f"input[placeholder*='{label_or_locator}'], textarea[placeholder*='{label_or_locator}']"
            )

        if field.count() > 0:
            if clear_first:
                field.first.fill("")
            field.first.fill(value)
            logger.info(f"[Input] {label_or_locator}")
        return self

    def check_checkbox(self, label: str, checked: bool = True) -> "AntDesignHelper":
        checkbox = self.page.locator(f".ant-checkbox-wrapper:has-text('{label}')")
        if checkbox.count() > 0:
            current = checkbox.locator("input").is_checked()
            if current != checked:
                checkbox.first.click()
        return self

    def select_radio(self, label: str) -> "AntDesignHelper":
        radio = self.page.locator(f".ant-radio-wrapper:has-text('{label}')")
        if radio.count() > 0:
            radio.first.click()
        return self

    def select_date(self, picker: Locator, date_str: str) -> "AntDesignHelper":
        picker.click()
        panel = self.page.locator(".ant-picker-dropdown:visible .ant-picker-panel")
        panel.wait_for(state="visible", timeout=5000)

        match = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
        if match:
            day_int = int(match.group(3))
            button = panel.locator(
                ".ant-picker-cell.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
                f"[title='{date_str}']"
            )
            if button.count() == 0:
                button = panel.locator(
                    ".ant-picker-cell.ant-picker-cell-in-view:not(.ant-picker-cell-disabled)"
                    f":has-text('{day_int}')"
                )
            button.first.click()
        return self

    def select_date_range(self, picker: Locator, start_date: str, end_date: str) -> "AntDesignHelper":
        picker.click()
        panel = self.page.locator(".ant-picker-dropdown:visible .ant-picker-panel")
        panel.wait_for(state="visible", timeout=5000)
        for date_str in [start_date, end_date]:
            button = panel.locator(f".ant-picker-cell[title='{date_str}']")
            if button.count() > 0:
                button.first.click()
        return self
