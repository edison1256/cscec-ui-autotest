"""Local-browser regression tests for page health and login-form detection."""

from __future__ import annotations

from html import escape

import pytest
from playwright.sync_api import Page, Route, expect

from core.assertions import AssertionHelper


@pytest.mark.parametrize(
    "markup",
    [
        '<h1>Order details</h1><p>用户名: sample 账号: sample 密码: ******</p>',
        '<form>账号<input readonly value="sample">密码'
        '<input type="password" readonly value="sample"><button>登录</button></form>',
        '<form>账号<input value="sample">密码'
        '<input type="password" disabled><button>登录</button></form>',
        '<p>Order details</p><form hidden><input type="password">'
        '<button>登录</button></form>',
        '<a href="#">登录</a><form><h1>Change password</h1>'
        '<input type="password"><button>Save</button></form>',
        '<h1>Order details</h1><input type="password" style="display:none">'
        '<button>登录</button>',
        '<h1>Change password</h1><input type="password"><button>Save</button>',
    ],
    ids=[
        "credential-text", "readonly-credentials", "disabled-password",
        "hidden-form", "login-link-outside-business-form", "hidden-password",
        "password-change",
    ],
)
def test_business_content_is_not_a_login_form(
    fresh_page: Page, markup: str,
) -> None:
    """Allow credential details and inactive widgets without weakening errors."""
    fresh_page.set_content(markup)
    helper = AssertionHelper(fresh_page)
    assert helper.page_not_blank_or_error() is helper


@pytest.mark.parametrize(
    "login_control",
    [
        '<button>登录</button>',
        '<button disabled>登 录</button>',
        '<input type="submit" value="Sign in">',
        '<a href="#">Log in</a>',
        '<div id="pwdLoginButton">登录</div>',
    ],
    ids=["button", "initially-disabled", "submit", "link", "existing-iam-control"],
)
def test_visible_login_controls_fail(
    fresh_page: Page, login_control: str,
) -> None:
    """Reject actual login forms even before their submit button is enabled."""
    fresh_page.set_content(
        '<form><label>Account<input autocomplete="username"></label>'
        '<label>Password<input type="password"></label>'
        f'{login_control}</form>'
    )
    with pytest.raises(AssertionError, match="visible login form"):
        AssertionHelper(fresh_page).page_not_blank_or_error()


@pytest.mark.parametrize("hidden", [False, True], ids=["visible", "hidden"])
def test_iframe_login_visibility(fresh_page: Page, hidden: bool) -> None:
    """Inspect visible login iframes but ignore background authentication widgets."""
    form = '<form><input type="password"><button>登录</button></form>'
    visibility = "hidden" if hidden else ""
    source = escape(form, quote=True)
    fresh_page.set_content(
        '<h1>Portal</h1>'
        f'<iframe id="auth" {visibility} srcdoc="{source}"></iframe>'
    )
    expect(
        fresh_page.frame_locator("#auth").get_by_role(
            "button", include_hidden=True,
        )
    ).to_have_count(1)
    if hidden:
        AssertionHelper(fresh_page).page_not_blank_or_error()
    else:
        with pytest.raises(AssertionError, match="visible login form"):
            AssertionHelper(fresh_page).page_not_blank_or_error()


def test_login_without_form_element_fails(fresh_page: Page) -> None:
    """Support legacy login widgets that do not use a form element."""
    fresh_page.set_content(
        '<h1>Sign in</h1><input type="password"><button>登录</button>'
    )
    with pytest.raises(AssertionError, match="visible login form"):
        AssertionHelper(fresh_page).page_not_blank_or_error()


def test_controls_from_different_frames_do_not_combine(fresh_page: Page) -> None:
    """Do not combine navigation login links with embedded business inputs."""
    source = escape('<input type="password">', quote=True)
    fresh_page.set_content(
        '<h1>Settings</h1><a href="#">登录</a>'
        f'<iframe id="settings" srcdoc="{source}"></iframe>'
    )
    expect(
        fresh_page.frame_locator("#settings").locator('input[type="password"]')
    ).to_be_visible()
    AssertionHelper(fresh_page).page_not_blank_or_error()


def test_hidden_ancestor_iframe_is_ignored(fresh_page: Page) -> None:
    """An inner login frame must not override a hidden outer frame."""
    login = escape('<input type="password"><button>登录</button>', quote=True)
    inner = escape(f'<iframe id="inner" srcdoc="{login}"></iframe>', quote=True)
    fresh_page.set_content(
        '<h1>Portal</h1>'
        f'<iframe id="outer" hidden srcdoc="{inner}"></iframe>'
    )
    expect(
        fresh_page.frame_locator("#outer").frame_locator("#inner")
        .get_by_role("button", include_hidden=True)
    ).to_have_count(1)
    AssertionHelper(fresh_page).page_not_blank_or_error()


@pytest.mark.parametrize("indicator", ["404 Not Found", "系统异常", "加载失败"])
def test_error_pages_still_fail(fresh_page: Page, indicator: str) -> None:
    """Retain the existing error-page gate after changing login detection."""
    fresh_page.set_content(f"<h1>{indicator}</h1>")
    with pytest.raises(AssertionError, match="error indicator"):
        AssertionHelper(fresh_page).page_not_blank_or_error()


def test_blank_page_still_fails(fresh_page: Page) -> None:
    """Do not accept a page containing no business text."""
    fresh_page.set_content("<body></body>")
    with pytest.raises(AssertionError, match="Page body is blank"):
        AssertionHelper(fresh_page).page_not_blank_or_error()


@pytest.mark.parametrize(
    "url",
    ["https://iam.example.invalid/cas", "https://example.invalid/login"],
)
def test_login_redirect_still_fails(fresh_page: Page, url: str) -> None:
    """Retain URL-based rejection without sending traffic to a real host."""
    def serve_login(route: Route) -> None:
        route.fulfill(
            status=200, content_type="text/html", body="<h1>Sign in</h1>",
        )

    fresh_page.route("**/*", serve_login)
    fresh_page.goto(url)
    with pytest.raises(AssertionError, match="login-like URL"):
        AssertionHelper(fresh_page).page_not_blank_or_error()
