from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import FrameLocator, Locator, Page

    Root = Page | FrameLocator

SELECTOR_PREFIXES = ("#", ".", "[", "//", "css=", "xpath=", "text=")
FORM_CONTROLS = ("input", "textarea", "select")


def is_selector(target: str) -> bool:
    return target.startswith(SELECTOR_PREFIXES)


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def clickable(page: "Root", target: str) -> "Locator":
    if is_selector(target):
        return page.locator(target)

    value = quote(target)
    return (
        page.get_by_role("button", name=target)
        .or_(page.get_by_role("link", name=target))
        .or_(page.locator(f"[id={value}], [name={value}], button[type={value}], input[type={value}]"))
    )


def field(page: "Root", target: str) -> "Locator":
    if is_selector(target):
        return page.locator(target)

    value = quote(target)
    controls = ", ".join(f"{tag}[name={value}], {tag}[id={value}]" for tag in FORM_CONTROLS)
    return page.get_by_label(target).or_(page.locator(controls)).or_(page.get_by_placeholder(target))


def element(page: "Root", target: str) -> "Locator":
    if target.startswith("@"):
        return page.locator(f"[data-testid={quote(target[1:])}]")
    return page.locator(target)


def radio(page: "Root", name: str, value: str | None = None) -> "Locator":
    selector = f"input[type=radio][name={quote(name)}]"
    return page.locator(selector + (f"[value={quote(value)}]" if value is not None else ""))
