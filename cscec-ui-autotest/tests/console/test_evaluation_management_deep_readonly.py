"""Batch K deep read-only evaluation coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.evaluation_management_page import EvaluationManagementPage


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.smoke
@pytest.mark.prod_mandatory
@pytest.mark.regression
@pytest.mark.domain_split
class TestEvaluationManagementDeepReadonly:
    """Validate evaluation rows and details without invoking write actions."""

    def test_first_evaluation_detail(self, logged_in_page) -> None:
        """Bind a queried evaluation row to its read-only detail dialog."""
        health = BrowserHealthMonitor(
            logged_in_page,
            "评价数据首条详情",
        ).start()
        try:
            EvaluationManagementPage(
                logged_in_page
            ).inspect_first_evaluation_detail()
        finally:
            health.stop()
        health.assert_healthy()
