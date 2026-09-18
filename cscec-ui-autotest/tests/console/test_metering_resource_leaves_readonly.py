"""Batch M tenant-resource metering leaf coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.metering_statistics_page import (
    RESOURCE_LEAVES,
    MeteringResourceLeaf,
    MeteringStatisticsPage,
)


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.smoke
@pytest.mark.prod_mandatory
@pytest.mark.regression
@pytest.mark.domain_split
class TestMeteringResourceLeavesReadonly:
    """Validate every tenant-resource leaf through its real menu path."""

    @pytest.mark.parametrize(
        "leaf",
        RESOURCE_LEAVES,
        ids=lambda leaf: leaf.case_id,
    )
    def test_metering_resource_leaf(
        self,
        logged_in_page,
        leaf: MeteringResourceLeaf,
    ) -> None:
        """Require business-success data and a rendered identity or true empty state."""
        health = BrowserHealthMonitor(
            logged_in_page,
            f"{leaf.title}只读探查",
        ).start()
        try:
            MeteringStatisticsPage(logged_in_page).inspect_resource_leaf(leaf)
        finally:
            health.stop()
        health.assert_healthy()
