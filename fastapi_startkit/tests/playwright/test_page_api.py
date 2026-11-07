import asyncio
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import pytest_asyncio

pytest.importorskip("playwright")

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from fastapi_startkit.playwright import BrowserTestCase, Page, browser_session, visit
from fastapi_startkit.playwright.assertions import port_of

ELEMENTS = """
<!doctype html>
<title>Elements — Dashboard</title>
<!-- source-marker -->
<div id="greeting">Hello Ada</div>
<div id="empty">   </div>
<ul><li class="item">One</li><li class="item">Two</li><li class="item">Three</li></ul>
<p id="hidden" hidden>Hidden</p>
<a href="/forms">Docs</a>
<a href="/secret" hidden>Secret link</a>
<button data-testid="save" aria-label="Save draft" data-id="42" class="btn btn-primary" disabled>Save</button>
<button id="go">Go</button>
<div id="later"></div>
<button id="reveal" onclick="setTimeout(() => {
    document.querySelector('#later').innerHTML = '<span class=item>Four</span>';
    document.title = 'Elements — Updated';
    window.answer = 43;
}, 200)">Reveal</button>
<script>window.answer = 42;</script>
"""

FORMS = """
<!doctype html>
<title>Forms</title>
<form action="/submitted" method="get">
    <label><input type="checkbox" name="remember" checked> Remember me</label>
    <label><input type="checkbox" name="news"> Newsletter</label>
    <label><input type="checkbox" id="partial"> Some</label>
    <input type="radio" name="plan" value="free"><input type="radio" name="plan" value="pro" checked>
    <input type="radio" name="size" value="s"><input type="radio" name="size" value="m">
    <label for="country">Country</label>
    <select id="country" name="country"><option value="us">US</option><option value="np" selected>Nepal</option></select>
    <select name="tags" multiple>
        <option value="a" selected>A</option><option value="b" selected>B</option><option value="c">C</option>
    </select>
    <label for="name">Name</label><input id="name" name="name" value="Ada">
    <input name="locked" value="fixed" disabled>
    <input type="file" name="avatar" onchange="document.querySelector('#file-name').textContent = this.files[0].name">
    <p id="file-name"></p>
    <input name="notes">
    <button type="button" id="slow" onclick="this.disabled = true; setTimeout(() => {
        this.disabled = false;
        document.querySelector('#status').textContent = 'Slow done';
    }, 200)">Slow</button>
    <p id="status"></p>
    <button type="submit">Send</button>
</form>
<script>document.querySelector('#partial').indeterminate = true;</script>
"""

INTERACT = """
<!doctype html>
<title>Interact</title>
<div id="menu" onmouseenter="document.querySelector('#status').textContent = 'Hovered'">Menu</div>
<div id="source" draggable="true" ondragstart="event.dataTransfer.setData('text', 'x')">Drag me</div>
<div id="target" style="width: 100px; height: 100px" ondragover="event.preventDefault()"
    ondrop="event.preventDefault(); document.querySelector('#status').textContent = 'Dropped'">Drop here</div>
<p id="status"></p>
<button id="later" onclick="setTimeout(() => document.querySelector('#status').textContent = 'Arrived', 200)">Later</button>
<iframe id="editor" srcdoc="<input name='inside'><p>Inside text</p>"></iframe>
"""

NOISY = """
<!doctype html>
<title>Noisy</title>
<script>console.log("booted")</script>
<script>throw new Error("Boom")</script>
"""

QUIET = "<!doctype html><title>Quiet</title><p>Nothing to report</p>"

APP = FastAPI()
APP.get("/elements", response_class=HTMLResponse)(lambda: ELEMENTS)
APP.get("/forms", response_class=HTMLResponse)(lambda: FORMS)
APP.get("/interact", response_class=HTMLResponse)(lambda: INTERACT)
APP.get("/noisy", response_class=HTMLResponse)(lambda: NOISY)
APP.get("/quiet", response_class=HTMLResponse)(lambda: QUIET)


@APP.get("/submitted", response_class=HTMLResponse)
def submitted(request: Request) -> str:
    return f"<h1>Submitted {request.url.query}</h1>"


def served() -> tuple[str, int | None]:
    parts = urlsplit(browser_session.server.url)
    return parts.hostname or "", parts.port


URL = "/elements?tab=info&empty=#section-2"

FAILURES = {
    "title_contains": (
        lambda: visit("/elements").assert_title_contains("Settings"),
        'Expected the title to contain "Settings", but it was "Elements — Dashboard".',
    ),
    "see_in": (
        lambda: visit("/elements").assert_see_in("#greeting", "Grace"),
        'Expected to see "Grace" in "#greeting" on /elements.',
    ),
    "dont_see_in": (
        lambda: visit("/elements").assert_dont_see_in("#greeting", "Ada"),
        'Expected not to see "Ada" in "#greeting" on /elements.',
    ),
    "see_anything_in": (
        lambda: visit("/elements").assert_see_anything_in("#empty"),
        'Expected to see text in "#empty" on /elements.',
    ),
    "see_nothing_in": (
        lambda: visit("/elements").assert_see_nothing_in("#greeting"),
        'Expected "#greeting" to be empty on /elements.',
    ),
    "see_link": (
        lambda: visit("/elements").assert_see_link("Secret link"),
        'Expected to see the link "Secret link" on /elements.',
    ),
    "dont_see_link": (
        lambda: visit("/elements").assert_dont_see_link("Docs"),
        'Expected not to see the link "Docs" on /elements.',
    ),
    "source_has": (
        lambda: visit("/elements").assert_source_has("<!-- absent -->"),
        'Expected the source of /elements to contain "<!-- absent -->".',
    ),
    "source_missing": (
        lambda: visit("/elements").assert_source_missing("<!-- source-marker -->"),
        'Expected the source of /elements not to contain "<!-- source-marker -->".',
    ),
    "script": (
        lambda: visit("/elements").assert_script("window.answer", 7),
        "Expected the script `window.answer` to return 7 on /elements, but it returned 42.",
    ),
    "count": (
        lambda: visit("/elements").assert_count(".item", 5),
        'Expected 5 elements matching ".item" on /elements, but found 3.',
    ),
    "visible": (
        lambda: visit("/elements").assert_visible("#hidden"),
        'Expected "#hidden" to be visible on /elements.',
    ),
    "present": (
        lambda: visit("/elements").assert_present("#nope"),
        'Expected "#nope" to be present on /elements.',
    ),
    "not_present": (
        lambda: visit("/elements").assert_not_present("#hidden"),
        'Expected "#hidden" not to be present on /elements.',
    ),
    "missing": (
        lambda: visit("/elements").assert_missing("#greeting"),
        'Expected "#greeting" to be missing or hidden on /elements.',
    ),
    "attribute": (
        lambda: visit("/elements").assert_attribute("@save", "class", "btn"),
        'Expected "@save" to have class="btn" on /elements.',
    ),
    "attribute_missing": (
        lambda: visit("/elements").assert_attribute_missing("@save", "disabled"),
        'Expected "@save" not to have the attribute "disabled" on /elements.',
    ),
    "attribute_missing_without_element": (
        lambda: visit("/elements").assert_attribute_missing("#nope", "disabled"),
        'Expected "#nope" not to have the attribute "disabled" on /elements.',
    ),
    "attribute_contains": (
        lambda: visit("/elements").assert_attribute_contains("@save", "class", "secondary"),
        'Expected the "class" of "@save" to contain "secondary" on /elements.',
    ),
    "attribute_doesnt_contain": (
        lambda: visit("/elements").assert_attribute_doesnt_contain("@save", "class", "primary"),
        'Expected the "class" of "@save" not to contain "primary" on /elements.',
    ),
    "attribute_doesnt_contain_without_attribute": (
        lambda: visit("/elements").assert_attribute_doesnt_contain("#go", "class", "primary"),
        'Expected the "class" of "#go" not to contain "primary" on /elements.',
    ),
    "aria_attribute": (
        lambda: visit("/elements").assert_aria_attribute("@save", "label", "Delete"),
        'Expected "@save" to have aria-label="Delete" on /elements.',
    ),
    "data_attribute": (
        lambda: visit("/elements").assert_data_attribute("@save", "id", "7"),
        'Expected "@save" to have data-id="7" on /elements.',
    ),
    "checked": (lambda: visit("/forms").assert_checked("news"), 'Expected "news" to be checked on /forms.'),
    "not_checked": (
        lambda: visit("/forms").assert_not_checked("remember"),
        'Expected "remember" not to be checked on /forms.',
    ),
    "indeterminate": (
        lambda: visit("/forms").assert_indeterminate("news"),
        'Expected "news" to be indeterminate on /forms.',
    ),
    "radio_selected": (
        lambda: visit("/forms").assert_radio_selected("plan", "free"),
        'Expected the radio "plan" to have "free" selected on /forms.',
    ),
    "radio_not_selected": (
        lambda: visit("/forms").assert_radio_not_selected("plan", "pro"),
        'Expected the radio "plan" not to have "pro" selected on /forms.',
    ),
    "radio_has_no_selection": (
        lambda: visit("/forms").assert_radio_not_selected("plan"),
        'Expected the radio "plan" not to have a selection on /forms.',
    ),
    "selected": (
        lambda: visit("/forms").assert_selected("country", "us"),
        'Expected "us" to be selected in "country" on /forms.',
    ),
    "not_selected": (
        lambda: visit("/forms").assert_not_selected("tags", "a"),
        'Expected "a" not to be selected in "tags" on /forms.',
    ),
    "not_selected_without_field": (
        lambda: visit("/forms").assert_not_selected("nope", "a"),
        'Expected "a" not to be selected in "nope" on /forms.',
    ),
    "value": (
        lambda: visit("/forms").assert_value("name", "Grace"),
        'Expected "name" to have the value "Grace" on /forms.',
    ),
    "value_is_not": (
        lambda: visit("/forms").assert_value_is_not("name", "Ada"),
        'Expected "name" not to have the value "Ada" on /forms.',
    ),
    "enabled": (lambda: visit("/forms").assert_enabled("locked"), 'Expected "locked" to be enabled on /forms.'),
    "disabled": (lambda: visit("/forms").assert_disabled("name"), 'Expected "name" to be disabled on /forms.'),
    "button_enabled": (
        lambda: visit("/elements").assert_button_enabled("Save draft"),
        'Expected the button "Save draft" to be enabled on /elements.',
    ),
    "button_disabled": (
        lambda: visit("/elements").assert_button_disabled("Go"),
        'Expected the button "Go" to be disabled on /elements.',
    ),
    "scheme_is": (
        lambda: visit(URL).assert_scheme_is("https"),
        'Expected the scheme to be "https", but the URL was "http://',
    ),
    "scheme_is_not": (
        lambda: visit(URL).assert_scheme_is_not("http"),
        'Expected the scheme not to be "http", but the URL was "http://',
    ),
    "host_is": (
        lambda: visit(URL).assert_host_is("example.com"),
        'Expected the host to be "example.com", but the URL was',
    ),
    "host_is_not": (
        lambda: visit(URL).assert_host_is_not(served()[0]),
        "Expected the host not to be",
    ),
    "port_is": (lambda: visit(URL).assert_port_is(1), 'Expected the port to be "1", but the URL was'),
    "port_is_not": (lambda: visit(URL).assert_port_is_not(served()[1] or 80), "Expected the port not to be"),
    "path_is_not": (
        lambda: visit(URL).assert_path_is_not("/elements"),
        'Expected the path not to be "/elements", but the URL was',
    ),
    "path_begins_with": (
        lambda: visit(URL).assert_path_begins_with("/admin"),
        'Expected the path to begin with "/admin"',
    ),
    "path_ends_with": (lambda: visit(URL).assert_path_ends_with("/nope"), 'Expected the path to end with "/nope"'),
    "path_contains": (lambda: visit(URL).assert_path_contains("xyz"), 'Expected the path to contain "xyz"'),
    "query_string_has_value": (
        lambda: visit(URL).assert_query_string_has("tab", "other"),
        'Expected the query string to have "tab" set to "other"',
    ),
    "query_string_has": (
        lambda: visit(URL).assert_query_string_has("page"),
        'Expected the query string to have "page", but the URL was',
    ),
    "query_string_missing": (
        lambda: visit(URL).assert_query_string_missing("tab"),
        'Expected the query string not to have "tab"',
    ),
    "fragment_is": (lambda: visit(URL).assert_fragment_is("top"), 'Expected the fragment to be "top"'),
    "fragment_is_not": (
        lambda: visit(URL).assert_fragment_is_not("section-2"),
        'Expected the fragment not to be "section-2"',
    ),
    "fragment_begins_with": (
        lambda: visit(URL).assert_fragment_begins_with("intro"),
        'Expected the fragment to begin with "intro"',
    ),
    "no_console_logs": (
        lambda: visit("/noisy").assert_no_console_logs(),
        "Expected no console logs on /noisy, but found:\n  - booted",
    ),
    "no_javascript_errors": (
        lambda: visit("/noisy").assert_no_javascript_errors(),
        "Expected no JavaScript errors on /noisy, but found:\n  - Boom",
    ),
    "no_smoke": (
        lambda: visit("/noisy").assert_no_smoke(),
        "Expected no console logs on /noisy, but found:\n  - booted",
    ),
}


def test_port_of_falls_back_to_the_scheme_default():
    assert port_of(urlsplit("https://example.com/")) == 443
    assert port_of(urlsplit("http://example.com/")) == 80
    assert port_of(urlsplit("http://example.com:8080/")) == 8080
    assert port_of(urlsplit("ftp://example.com/")) is None


class TestPageApi(BrowserTestCase):
    def get_application(self):
        return APP

    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def requires_chromium(self):
        if not Path((await browser_session.driver()).chromium.executable_path).exists():
            pytest.skip("Chromium is not installed; run `playwright install chromium`.")

    @pytest.fixture
    def short_timeout(self, monkeypatch):
        monkeypatch.setattr(browser_session, "timeout", 300)

    async def test_title_and_text_assertions_pass(self):
        await (
            visit("/elements")
            .assert_title("Elements — Dashboard")
            .assert_title_contains("Dashboard")
            .assert_see("Hello Ada")
            .assert_dont_see("Hidden")
            .assert_see_in("ul", "Two")
            .assert_dont_see_in("ul", "Five")
            .assert_see_anything_in("#greeting")
            .assert_see_nothing_in("#empty")
            .assert_see_link("Docs")
            .assert_dont_see_link("Secret link")
            .assert_dont_see_link("docs")
        )

    async def test_source_and_script_assertions_pass(self):
        await (
            visit("/elements")
            .assert_source_has("<!-- source-marker -->")
            .assert_source_missing("<!-- absent -->")
            .assert_script("window.answer", 42)
            .assert_script("document.querySelectorAll('.item').length === 3")
        )

    async def test_element_and_attribute_assertions_pass(self):
        await (
            visit("/elements")
            .assert_count(".item", 3)
            .assert_visible("#greeting")
            .assert_present("#hidden")
            .assert_not_present("#nope")
            .assert_missing("#hidden")
            .assert_missing("#nope")
            .assert_attribute("@save", "class", "btn btn-primary")
            .assert_attribute_missing("#go", "disabled")
            .assert_attribute_contains("@save", "class", "primary")
            .assert_attribute_doesnt_contain("@save", "class", "secondary")
            .assert_aria_attribute("@save", "label", "Save draft")
            .assert_data_attribute("@save", "id", "42")
            .assert_button_disabled("Save draft")
            .assert_button_enabled("Go")
        )

    async def test_assertions_retry_until_the_page_changes(self):
        await (
            visit("/elements")
            .click("Reveal")
            .assert_count(".item", 4)
            .assert_title_contains("Updated")
            .assert_script("window.answer", 43)
            .assert_see_in("#later", "Four")
        )

    async def test_form_state_assertions_pass(self):
        await (
            visit("/forms")
            .assert_checked("remember")
            .assert_not_checked("news")
            .assert_indeterminate("partial")
            .assert_radio_selected("plan", "pro")
            .assert_radio_not_selected("plan", "free")
            .assert_radio_not_selected("size")
            .assert_selected("country", "np")
            .assert_not_selected("country", "us")
            .assert_selected("tags", "a")
            .assert_selected("tags", "b")
            .assert_not_selected("tags", "c")
            .assert_value("name", "Ada")
            .assert_value_is_not("name", "Grace")
            .assert_enabled("name")
            .assert_disabled("locked")
        )

    async def test_url_assertions_pass(self):
        host, port = served()
        await (
            visit(URL)
            .assert_url_is("/elements")
            .assert_scheme_is("http")
            .assert_scheme_is_not("https")
            .assert_host_is(host)
            .assert_host_is_not("example.com")
            .assert_port_is(port or 80)
            .assert_port_is_not(1)
            .assert_path_is("/elements")
            .assert_path_is_not("/forms")
            .assert_path_begins_with("/ele")
            .assert_path_ends_with("ments")
            .assert_path_contains("lem")
            .assert_query_string_has("tab")
            .assert_query_string_has("tab", "info")
            .assert_query_string_has("empty", "")
            .assert_query_string_missing("page")
            .assert_fragment_is("section-2")
            .assert_fragment_is_not("top")
            .assert_fragment_begins_with("section")
        )

    async def test_console_and_errors_are_recorded(self):
        page = await visit("/noisy")

        assert page.console_logs == ["booted"]
        assert page.javascript_errors == ["Boom"]
        await visit("/quiet").assert_no_console_logs().assert_no_javascript_errors().assert_no_smoke()

    @pytest.mark.usefixtures("short_timeout")
    @pytest.mark.parametrize(("chain", "message"), FAILURES.values(), ids=FAILURES.keys())
    async def test_failed_assertions_explain_what_was_expected(self, chain, message):
        with pytest.raises(AssertionError, match=re.escape(message)):
            await chain()

    async def test_typing_appending_keys_and_clearing(self):
        await (
            visit("/forms")
            .type("notes", "hello")
            .assert_value("notes", "hello")
            .append("notes", " world")
            .assert_value("notes", "hello world")
            .keys("notes", ["{ControlOrMeta}", "a"], "{Backspace}", "typed")
            .assert_value("notes", "typed")
            .clear("notes")
            .assert_value("notes", "")
            .type_slowly("notes", "ab", delay=5)
            .assert_value("notes", "ab")
        )

    async def test_checkboxes_radios_and_multiple_selects(self):
        await (
            visit("/forms")
            .check("news")
            .uncheck("remember")
            .radio("size", "m")
            .select("tags", ["c"])
            .assert_checked("news")
            .assert_not_checked("remember")
            .assert_radio_selected("size", "m")
            .assert_selected("tags", "c")
            .assert_not_selected("tags", "a")
        )

    async def test_attach_sets_the_file_input(self, tmp_path):
        avatar = tmp_path / "avatar.png"
        avatar.write_bytes(b"png")

        await visit("/forms").attach("avatar", str(avatar)).assert_see_in("#file-name", "avatar.png")

    async def test_press_and_wait_for_waits_until_the_button_is_enabled(self):
        await (
            visit("/forms")
            .press_and_wait_for("Slow")
            .assert_button_enabled("Slow")
            .assert_see_in("#status", "Slow done")
        )

    async def test_submit_sends_the_focused_form(self):
        await (
            visit("/forms")
            .fill("name", "Grace")
            .submit()
            .assert_path_is("/submitted")
            .assert_query_string_has("name", "Grace")
            .assert_query_string_missing("locked")
        )

    @pytest.mark.usefixtures("short_timeout")
    async def test_submit_without_a_form_fails(self):
        with pytest.raises(AssertionError, match="Unable to submit a form on /quiet: there is no form."):
            await visit("/quiet").submit()

    async def test_hover_drag_wait_for_text_and_resize(self):
        page = await (
            visit("/interact")
            .hover("#menu")
            .assert_see_in("#status", "Hovered")
            .drag("#source", "#target")
            .assert_see_in("#status", "Dropped")
            .click("#later")
            .wait_for_text("Arrived")
            .resize(500, 400)
            .wait(0.01)
        )

        assert await page.script("window.innerWidth") == 500

    async def test_within_frame_scopes_lookups_to_the_frame(self):
        await (
            visit("/interact")
            .within_frame(
                "#editor",
                lambda frame: frame.fill("inside", "hi").assert_value("inside", "hi").assert_see("Inside text"),
            )
            .assert_dont_see("Inside text")
            .assert_path_is("/interact")
        )

    async def test_wait_for_key_resumes_after_a_key_press(self):
        page = await visit("/quiet")
        waiting = asyncio.ensure_future(page.wait_for_key().assert_see("Nothing to report"))

        while not waiting.done():
            await page.playwright.keyboard.press("a")
            await asyncio.sleep(0.05)

        assert await waiting is page

    async def test_readers_return_values(self):
        elements = visit("/elements")

        assert await elements.text("#greeting") == "Hello Ada"
        assert await elements.attribute("@save", "data-id") == "42"
        assert await elements.attribute("#go", "data-id") is None
        assert "source-marker" in await elements.content()
        assert await elements.script("(a) => a * 2", 21) == 42
        assert await visit("/forms").value("name") == "Ada"

    @pytest.mark.usefixtures("short_timeout")
    async def test_readers_report_missing_elements(self):
        with pytest.raises(AssertionError, match='Unable to read the text of "#nope" on /elements.'):
            await visit("/elements").text("#nope")

    async def test_context_options_reach_the_page(self):
        page = await visit("/quiet").with_timezone("America/New_York").with_locale("fr-FR").with_user_agent("Googlebot")

        assert await page.script("Intl.DateTimeFormat().resolvedOptions().timeZone") == "America/New_York"
        assert await page.script("navigator.language") == "fr-FR"
        assert await page.script("navigator.userAgent") == "Googlebot"

    async def test_an_explicit_user_agent_wins_over_the_device(self):
        page = await visit("/quiet").on().mobile().with_user_agent("Googlebot")

        assert await page.script("navigator.userAgent") == "Googlebot"

    async def test_context_options_cannot_change_after_opening(self):
        page: Page = await visit("/quiet")

        with pytest.raises(RuntimeError, match="Choose the device and browser before interacting with the page."):
            page.with_locale("fr-FR")
