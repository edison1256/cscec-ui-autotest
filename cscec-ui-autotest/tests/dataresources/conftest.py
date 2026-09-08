"""Fixtures for data resource management tests."""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.dataresources.data_resource_page import DataResourcePage
from pages.portal.portal_home_page import PortalHomePage


@pytest.fixture(scope="function")
def data_resources(logged_in_page):
    """Open console in a new page and navigate to data resource management."""
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()

    data_resource_page = DataResourcePage(console_page)
    try:
        data_resource_page.open_from_console_home()
    except EntryNotExposed as exc:
        if not console_page.is_closed():
            console_page.close()
        pytest.skip(str(exc))
    yield data_resource_page

    if not console_page.is_closed():
        console_page.close()


@pytest.fixture(scope="function")
def data_layer_settings(logged_in_page):
    """Open console in a new page and navigate to data layer settings."""
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()

    data_resource_page = DataResourcePage(console_page)
    try:
        data_resource_page.open_layer_settings_from_console_home()
    except EntryNotExposed as exc:
        if not console_page.is_closed():
            console_page.close()
        pytest.skip(str(exc))
    yield data_resource_page

    if not console_page.is_closed():
        console_page.close()
