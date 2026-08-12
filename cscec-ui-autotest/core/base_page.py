"""Base page object composition root."""

from playwright.sync_api import Page

from core.antd import AntDesignHelper
from core.assertions import AssertionHelper
from core.elements import ElementHelper
from core.navigation import NavigationHelper


class BasePage:
    """Minimal base class that wires focused helpers into page objects."""

    PAGE_NAME: str = "Unnamed page"
    PAGE_URL: str = ""
    PAGE_URL_PATTERN: str = ""

    def __init__(self, page: Page):
        self.page = page
        self.nav = NavigationHelper(page)
        self.elements = ElementHelper(page)
        self.assertions = AssertionHelper(page)
        self.antd = AntDesignHelper(page)
