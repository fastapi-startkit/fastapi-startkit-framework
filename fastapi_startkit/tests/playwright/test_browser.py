import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

pytest.importorskip("playwright")

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from fastapi_startkit.playwright import BrowserSession, BrowserTestCase, LiveServer, Page, browser_session, visit
from fastapi_startkit.playwright.plugin import calls_debug, pytest_collection_modifyitems, pytest_runtest_makereport
from fastapi_startkit.playwright.server import load_app
from fastapi_startkit.playwright.session import CALL_REPORT, slugify

HOME = """
<!doctype html>
<title>Home</title>
<h1>Welcome home</h1>
<a href="/form">Open the form</a>
<button id="reveal" onclick="setTimeout(() => {
    document.querySelector('#later').textContent = 'Shown later';
    history.pushState({}, '', '/revealed?step=2');
}, 200)">Reveal</button>
<p id="later"></p>
<p hidden>Secret text</p>
<script>const leaked = "Script text";</script>
"""

FORM = """
<!doctype html>
<title>Form</title>
<form action="/submitted" method="get">
    <label for="email">Email address</label>
    <input id="email" name="email">
    <input name="nickname">
    <input id="city">
    <input placeholder="Search everything">
    <label><input type="checkbox" name="terms"> Accept terms</label>
    <label for="plan">Plan</label>
    <select id="plan" name="plan"><option value="free">Free</option><option value="pro">Pro</option></select>
    <button type="submit">Send it</button>
</form>
"""

KEYS = """
<!doctype html>
<title>Keys</title>
<button onclick="document.querySelector('#log').textContent += event.shiftKey ? 'shift ' : 'plain '">Log</button>
<p id="log"></p>
<iframe id="editor" srcdoc="<input name='inside'>"></iframe>
"""

APP = FastAPI()
APP.get("/", response_class=HTMLResponse)(lambda: HOME)
APP.get("/form", response_class=HTMLResponse)(lambda: FORM)
APP.get("/keys", response_class=HTMLResponse)(lambda: KEYS)
APP.get("/submitted", response_class=HTMLResponse)(lambda email="", plan="": f"<h1>Got {email} on {plan}</h1>")

OTHER_APP = FastAPI()
OTHER_APP.get("/", response_class=HTMLResponse)(lambda: "<h1>Served from get_application</h1>")


async def installed(name: str) -> bool:
    return Path(getattr(await browser_session.driver(), name).executable_path).exists()


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[16:24]
    return int.from_bytes(header[:4], "big"), int.from_bytes(header[4:], "big")


@pytest.fixture(scope="module")
def screenshot_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("screenshots")


class TestPage(BrowserTestCase):
    def get_application(self):
        return APP

    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def requires_chromium(self, monkeypatch, screenshot_dir):
        if not await installed("chromium"):
            pytest.skip("Chromium is not installed; run `playwright install chromium`.")
        monkeypatch.setattr(browser_session, "screenshot_dir", screenshot_dir)

    @pytest.fixture
    def short_timeout(self, monkeypatch):
        monkeypatch.setattr(browser_session, "timeout", 300)

    async def test_visit_is_lazy_until_awaited(self):
        page = visit("/").assert_see("Welcome home")

        assert not page.opened
        assert page.pending
        assert await page is page
        assert page.opened
        assert not page.pending
        assert page.path == "/"
        assert page.url == browser_session.server.url + "/"

    async def test_playwright_needs_an_awaited_page(self):
        with pytest.raises(RuntimeError, match=r'Await visit\("/"\) before using page.playwright\.'):
            visit("/").playwright

    async def test_assertions_wait_for_client_side_changes(self):
        await (
            visit("/")
            .click("Reveal")
            .assert_see("Shown later")
            .assert_url_is("/revealed")
            .assert_path_is("/revealed")
            .assert_title("Home")
        )

    async def test_assert_see_ignores_hidden_and_script_text(self):
        await visit("/").assert_dont_see("Secret text").assert_dont_see("Script text")

    async def test_click_follows_links_by_their_text(self):
        await visit("/").click("Open the form").assert_path_is("/form").assert_title("Form")

    async def test_fill_finds_fields_by_label_name_id_placeholder_and_selector(self):
        await (
            visit("/form")
            .fill("Email address", "ada@example.com")
            .fill("nickname", "ada")
            .fill("city", "London")
            .fill("Search everything", "query")
            .fill("#email", "grace@example.com")
            .assert_value("email", "grace@example.com")
            .assert_value("nickname", "ada")
            .assert_value("city", "London")
            .assert_value("Search everything", "query")
        )

    async def test_steps_run_in_the_order_they_were_chained(self):
        page = visit("/form").fill("nickname", "first").fill("nickname", "second")

        assert await page.value("nickname") == "second"

    async def test_readers_run_pending_steps_first(self):
        page = visit("/form").fill("city", "Paris")

        assert await page.value("city") == "Paris"
        assert await visit("/").text("h1") == "Welcome home"
        assert await visit("/").attribute("#reveal", "id") == "reveal"
        assert await visit("/").script("1 + 1") == 2
        assert "<h1>Welcome home</h1>" in await visit("/").content()

    async def test_a_page_can_be_awaited_again_with_more_steps(self):
        page = await visit("/form").fill("nickname", "ada")

        await page.fill("city", "London").assert_value("nickname", "ada").assert_value("city", "London")

    async def test_check_uncheck_and_select(self):
        page = await visit("/form").check("Accept terms").select("Plan", "pro").assert_value("plan", "pro")

        assert await page.playwright.is_checked("[name=terms]")
        await page.uncheck("terms")
        assert not await page.playwright.is_checked("[name=terms]")

    async def test_click_submit_presses_the_submit_button(self):
        await (
            visit("/form")
            .fill("email", "ada@example.com")
            .select("plan", "pro")
            .click("submit")
            .assert_see("Got ada@example.com on pro")
            .assert_url_is(browser_session.server.url + "/submitted")
        )

    async def test_navigate_and_selectors_with_quotes(self):
        await visit("/").navigate("/form").fill('[name="nickname"]', 'say "hi"').assert_value("nickname", 'say "hi"')

    async def test_with_key_down_runs_its_steps_while_the_key_is_held(self):
        page = visit("/keys").with_key_down("Shift", lambda page: page.click("Log")).click("Log")

        assert await page.text("#log") == "shift plain"

    async def test_scoped_callbacks_may_be_async(self):
        async def fill_inside(page):
            await page.fill("inside", "typed in the frame")

        page = await visit("/keys").within_frame("#editor", fill_inside)

        assert await page.playwright.frame_locator("#editor").locator("[name=inside]").input_value() == (
            "typed in the frame"
        )

    async def test_a_failing_step_drops_the_rest_of_the_chain(self, short_timeout):
        page = visit("/form").click("Nowhere").fill("nickname", "never")

        with pytest.raises(AssertionError, match=r'Unable to click "Nowhere" on /form\.'):
            await page

        assert not page.pending
        assert await page.value("nickname") == ""

    async def test_missing_elements_raise_an_assertion_error(self, short_timeout):
        with pytest.raises(AssertionError, match=r'Unable to fill "nothing" on /\.'):
            await visit("/").fill("nothing", "x")
        with pytest.raises(AssertionError, match=r'Unable to read the text of "#nothing" on /\.'):
            await visit("/").text("#nothing")

    @pytest.mark.parametrize(
        ("assertion", "message"),
        [
            (lambda page: page.assert_see("Absent"), r'Expected to see "Absent" on /\.'),
            (lambda page: page.assert_dont_see("Welcome home"), r'Expected not to see "Welcome home" on /\.'),
            (
                lambda page: page.assert_url_is("/elsewhere"),
                r'Expected the URL to be ".*/elsewhere", but it was ".*/"\.',
            ),
            (lambda page: page.assert_path_is("/elsewhere"), r'Expected the path to be "/elsewhere", but it was "/"\.'),
            (lambda page: page.assert_title("Other"), r'Expected the title to be "Other", but it was "Home"\.'),
            (lambda page: page.assert_value("nothing", "x"), r'Expected "nothing" to have the value "x" on /\.'),
        ],
    )
    async def test_failed_assertions_explain_what_was_expected(self, short_timeout, assertion, message):
        with pytest.raises(AssertionError, match=message):
            await assertion(visit("/"))

    async def test_devices_set_the_viewport(self):
        mobile = await visit("/").on().mobile()
        tablet = await visit("/").on().tablet()
        named = await visit("/").on().device("Pixel 7")
        desktop = await visit("/").on().desktop()

        assert mobile.playwright.viewport_size == {"width": 390, "height": 664}
        assert tablet.playwright.viewport_size == {"width": 810, "height": 1080}
        assert named.playwright.viewport_size["width"] == 412
        assert desktop.playwright.viewport_size == {"width": 1280, "height": 720}

    async def test_mobile_firefox_drops_the_unsupported_mobile_flag(self):
        if not await installed("firefox"):
            pytest.skip("Firefox is not installed; run `playwright install firefox`.")

        page = await visit("/").on().mobile().firefox().assert_see("Welcome home")

        assert page.playwright.context.browser.browser_type.name == "firefox"
        assert page.playwright.viewport_size == {"width": 390, "height": 664}
        assert await page.script("'ontouchstart' in window")

    async def test_unknown_browser_and_device_are_rejected(self):
        with pytest.raises(ValueError, match='Unknown browser "opera"'):
            visit("/").browser("opera")
        with pytest.raises(ValueError, match='Unknown device "Toaster"'):
            await visit("/").on().device("Toaster")

    async def test_configuring_an_opened_page_raises(self):
        page = await visit("/").chromium()

        with pytest.raises(RuntimeError, match="Choose the device and browser before interacting"):
            page.webkit()

    async def tall_page(self) -> Page:
        page = await visit("/")
        await page.script("document.body.style.height = '3000px'")
        return page

    async def test_screenshot_captures_the_viewport_named_after_the_test(self, request):
        await (await self.tall_page()).screenshot()

        path = browser_session.screenshot_dir / f"{slugify(request.node.nodeid)}.png"
        assert png_size(path) == (1280, 720)

    async def test_screenshot_can_capture_the_full_page(self):
        await (await self.tall_page()).screenshot(full_page=True, filename="full")

        width, height = png_size(browser_session.screenshot_dir / "full.png")
        assert width == 1280
        assert height > 3000

    async def test_screenshot_accepts_a_custom_filename(self):
        await visit("/").screenshot(filename="custom name").screenshot(filename="already.png")

        assert (browser_session.screenshot_dir / "custom-name.png").exists()
        assert (browser_session.screenshot_dir / "already.png").exists()

    async def test_screenshot_outside_a_test_is_named_after_the_path(self, monkeypatch):
        monkeypatch.setattr(browser_session, "test_name", None)

        await visit("/form").screenshot()

        assert (browser_session.screenshot_dir / "form.png").exists()

    async def test_failure_screenshots_cover_every_open_page(self):
        first = await visit("/")
        await visit("/form")
        visit("/never-opened")

        paths = await browser_session.screenshot_pages("tests/test_x.py::test_y[1]")

        assert [path.name for path in paths] == ["tests-test_x.py-test_y-1.png", "tests-test_x.py-test_y-1-2.png"]
        assert all(path.exists() for path in paths)
        await first.close()
        await first.close()

    async def test_debug_pauses_every_opened_page(self, monkeypatch):
        paused = []
        first = await visit("/")
        second = await visit("/form")
        visit("/never-opened")

        async def pause_at(path):
            paused.append(path)

        monkeypatch.setattr(first.playwright, "pause", lambda: pause_at("/"))
        monkeypatch.setattr(second.playwright, "pause", lambda: pause_at("/form"))

        await browser_session.pause_pages()

        assert paused == ["/", "/form"]

    async def test_debug_pauses_the_page_and_keeps_the_chain(self, monkeypatch):
        page = await visit("/")
        paused = []

        async def pause():
            paused.append(page.path)

        monkeypatch.setattr(page.playwright, "pause", pause)

        assert await Page.debug(page).assert_see("Welcome home") is page
        assert paused == ["/"]

    async def test_unawaited_chains_are_reported(self):
        visit("/")
        pending = visit("/form").fill("nickname", "never")

        assert browser_session.unawaited_pages() == [pending]
        assert pending.describe() == 'visit("/form")'
        await pending.close()
        assert browser_session.unawaited_pages() == []

    async def test_pages_from_earlier_tests_are_closed(self):
        assert browser_session.pages == []


class TestApplicationSelection(BrowserTestCase):
    def get_application(self):
        return OTHER_APP

    async def test_get_application_selects_the_served_app(self):
        assert browser_session.app is OTHER_APP
        assert browser_session.server.app is OTHER_APP
        await visit("/").assert_see("Served from get_application")


class TestLiveServer(BrowserTestCase):
    def get_application(self):
        return APP

    async def test_serves_an_application_on_the_running_loop_and_stops(self):
        import httpx

        app = FastAPI()
        app.get("/ping")(lambda: {"pong": True})
        server = await LiveServer(app).start()

        assert server.running
        async with httpx.AsyncClient() as client:
            assert (await client.get(server.url + "/ping")).json() == {"pong": True}
        await server.stop()
        assert not server.running

    async def test_reports_an_application_that_cannot_start(self):
        async def broken(scope, receive, send):
            if scope["type"] == "lifespan":
                await receive()
                await send({"type": "lifespan.startup.failed", "message": "boom"})

        with pytest.raises(RuntimeError, match="stopped before it started"):
            await LiveServer(broken).start()

    async def test_reports_an_application_that_starts_too_slowly(self):
        async def slow(scope, receive, send):
            if scope["type"] == "lifespan":
                await receive()
                await asyncio.sleep(1)

        with pytest.raises(RuntimeError, match=r"did not start within 0.05s"):
            await LiveServer(slow, startup_timeout=0.05).start()

    async def test_a_session_without_an_application_refuses_to_serve(self):
        with pytest.raises(RuntimeError, match="Extend fastapi_startkit.playwright.BrowserTestCase"):
            await BrowserSession().serve()

    async def test_the_server_is_unavailable_until_served(self):
        with pytest.raises(RuntimeError, match="The application server is not running."):
            BrowserSession().server


def test_load_app_accepts_import_paths_and_applications():
    class Application:
        fastapi = "the fastapi instance"

    assert load_app(Application()) == "the fastapi instance"
    assert load_app("json:dumps").__name__ == "dumps"


def test_makereport_records_the_call_report_on_the_item():
    item = SimpleNamespace(stash={})
    reports = [SimpleNamespace(when=when) for when in ("setup", "call", "teardown")]

    for report in reports:
        hook = pytest_runtest_makereport(item, None)
        next(hook)
        with pytest.raises(StopIteration):
            hook.send(SimpleNamespace(get_result=lambda report=report: report))

    assert item.stash[CALL_REPORT] is reports[1]


def debugging_test():
    visit("/").debug()


def logging_test():
    logger = SimpleNamespace(debug=print)
    logger.debug("not a browser debug")


def plain_test():
    visit("/")


def test_calls_debug_finds_zero_argument_debug_calls():
    assert calls_debug(debugging_test)
    assert not calls_debug(logging_test)
    assert not calls_debug(plain_test)
    assert not calls_debug(None)
    assert not calls_debug(eval("lambda: 1"))


def test_collection_keeps_only_debugging_tests_and_shows_the_browser(monkeypatch):
    configured = []
    deselected = []
    monkeypatch.setattr(browser_session, "configure", lambda **options: configured.append(options))
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=lambda items: deselected.extend(items)))
    debugging, plain = SimpleNamespace(function=debugging_test), SimpleNamespace(function=plain_test)
    items = [plain, debugging]

    pytest_collection_modifyitems(config, items)

    assert items == [debugging]
    assert deselected == [plain]
    assert configured == [{"headed": True}]


def test_collection_without_debug_calls_is_untouched(monkeypatch):
    configured = []
    monkeypatch.setattr(browser_session, "configure", lambda **options: configured.append(options))
    items = [SimpleNamespace(function=plain_test), SimpleNamespace(function=logging_test)]

    pytest_collection_modifyitems(SimpleNamespace(), list(items))

    assert configured == []
