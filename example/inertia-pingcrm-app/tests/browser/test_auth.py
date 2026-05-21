import re
import pytest
from playwright.sync_api import Page, expect

# Seeded credentials (databases/seeds/database_seeder.py)
EMAIL = "johndoe@example.com"
PASSWORD = "secret"


@pytest.fixture
def logged_in_page(page: Page) -> Page:
    """Return a page already logged in as the seed user."""
    page.goto("/login")
    page.locator("#email").fill(EMAIL)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url(re.compile(r"/$"))
    return page


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------


def test_login_page_renders(page: Page):
    page.goto("/login")
    expect(page).to_have_title(re.compile("Login"))
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator('input[type="password"]')).to_be_visible()
    expect(page.get_by_role("button", name="Login")).to_be_visible()


def test_login_prefills_demo_credentials(page: Page):
    """The seed user's credentials are pre-filled in the login form."""
    page.goto("/login")
    expect(page.locator("#email")).to_have_value(EMAIL)
    expect(page.locator('input[type="password"]')).to_have_value(PASSWORD)


# ---------------------------------------------------------------------------
# Authentication flows
# ---------------------------------------------------------------------------


def test_valid_login_redirects_to_dashboard(page: Page):
    page.goto("/login")
    page.locator("#email").fill(EMAIL)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    expect(page).to_have_url(re.compile(r"/$"))
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_invalid_login_shows_error(page: Page):
    page.goto("/login")
    page.locator("#email").fill("nobody@example.com")
    page.locator('input[type="password"]').fill("wrong")
    page.get_by_role("button", name="Login").click()
    expect(page).to_have_url(re.compile(r"/login"))
    expect(
        page.get_by_text("These credentials do not match our records.")
    ).to_be_visible()


def test_protected_route_redirects_unauthenticated_user(page: Page):
    page.goto("/")
    expect(page).to_have_url(re.compile(r"/login"))


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def test_logout_returns_to_login(logged_in_page: Page):
    page = logged_in_page
    # Open the user dropdown (shows "John" / "John Doe" depending on viewport)
    page.get_by_text("John").first.click()
    page.get_by_role("button", name="Logout").click()
    expect(page).to_have_url(re.compile(r"/login"))


def test_after_logout_protected_routes_require_login(logged_in_page: Page):
    page = logged_in_page
    page.get_by_text("John").first.click()
    page.get_by_role("button", name="Logout").click()
    page.goto("/")
    expect(page).to_have_url(re.compile(r"/login"))
