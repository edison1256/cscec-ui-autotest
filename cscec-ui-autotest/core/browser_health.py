"""Collect browser-side failures produced by a scoped UI interaction."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import ConsoleMessage, Error, Page, Response


@dataclass(frozen=True)
class BrowserHealthIssue:
    """A browser-side failure captured while an interaction is running."""

    category: str
    detail: str


class BrowserHealthMonitor:
    """Capture runtime, console, and critical HTTP failures for one action."""

    def __init__(self, page: Page, action_name: str) -> None:
        self.page = page
        self.action_name = action_name
        self.issues: list[BrowserHealthIssue] = []
        self._started = False

    def start(self) -> "BrowserHealthMonitor":
        """Attach listeners before the target interaction starts."""
        if not self._started:
            self.page.on("console", self._on_console)
            self.page.on("pageerror", self._on_page_error)
            self.page.on("response", self._on_response)
            self._started = True
        return self

    def stop(self) -> "BrowserHealthMonitor":
        """Detach listeners while preserving all captured issues."""
        if self._started:
            self.page.remove_listener("console", self._on_console)
            self.page.remove_listener("pageerror", self._on_page_error)
            self.page.remove_listener("response", self._on_response)
            self._started = False
        return self

    def assert_healthy(self) -> "BrowserHealthMonitor":
        """Fail with compact evidence when the monitored action was unhealthy."""
        if self.issues:
            evidence = "\n".join(
                f"- {issue.category}: {issue.detail[:1200]}" for issue in self.issues[:10]
            )
            raise AssertionError(f"{self.action_name} 触发浏览器端异常:\n{evidence}")
        return self

    def _on_console(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            self.issues.append(BrowserHealthIssue("console.error", message.text))

    def _on_page_error(self, error: Error) -> None:
        self.issues.append(BrowserHealthIssue("pageerror", str(error)))

    def _on_response(self, response: Response) -> None:
        if response.status == 404 or response.status >= 500:
            self.issues.append(
                BrowserHealthIssue("http", f"{response.status} {response.url}")
            )
